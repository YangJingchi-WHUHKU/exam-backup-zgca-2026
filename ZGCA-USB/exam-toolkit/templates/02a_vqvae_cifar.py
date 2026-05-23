"""
VQ-VAE 编解码器 + 训练（对标 2026 冬 T2 步骤 1）
==================================================

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. DATA_PATH         - CIFAR-10 数据目录（题目给的 /vepfs-readonly/problem2/...）
  2. OUT_DIR           - 一般 /vepfs/problem2/
  3. NUM_EMBEDDINGS    - codebook 大小（题面给的 512 别动）

依赖:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      torch torchvision

显存预算 (A100 80G):
  hidden=128, batch=128 → ~5 GB；batch=256 仍很轻松

运行:
  python 02a_vqvae_cifar.py
  python 02a_vqvae_cifar.py --epochs 30 --batch 256

设计要点（README 必写）:
  - Encoder 32→16→8 三层降采样 + residual stack
  - Decoder 8→16→32 ConvTranspose2d 上采样 + residual stack（必须实现）
  - VectorQuantizer 使用 straight-through estimator
  - Loss = MSE(recon) + ||sg[ze]-zq||² + β·||ze-sg[zq]||²，β=0.25
  - 防 codebook collapse: 较大的 commitment β 帮助编码器靠近 codebook

输出:
  OUT_DIR/checkpoints/vqvae.pt  - 给 02b prior 训练用
"""

import argparse
import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

# _common.trainer 在同级
import sys
sys.path.insert(0, str(Path(__file__).parent))
from _common.trainer import Trainer, TrainConfig  # noqa: E402


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
DATA_PATH = os.environ.get("DATA_PATH", "/vepfs-readonly/problem2/cifar10")
OUT_DIR = os.environ.get("OUT_DIR", "/vepfs/problem2")

HIDDEN_DIM = 128
EMBEDDING_DIM = 64
NUM_EMBEDDINGS = 512
COMMITMENT_BETA = 0.25
LR = 1e-3
BATCH_SIZE = 128
EPOCHS = 20


# ============================================================
# 2) BUILDING BLOCKS
# ============================================================
class ResidualBlock(nn.Module):
    """Conv2d → ReLU → Conv2d → + residual。VQ-VAE 论文标准块。"""

    def __init__(self, in_ch: int, hidden_ch: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.ReLU(inplace=True),
            nn.Conv2d(in_ch, hidden_ch, kernel_size=3, padding=1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden_ch, in_ch, kernel_size=1, bias=False),
        )

    def forward(self, x):
        return x + self.block(x)


class ResidualStack(nn.Module):
    def __init__(self, in_ch: int, hidden_ch: int, num_blocks: int = 2):
        super().__init__()
        self.layers = nn.ModuleList([
            ResidualBlock(in_ch, hidden_ch) for _ in range(num_blocks)
        ])
        self.out_relu = nn.ReLU(inplace=True)

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        return self.out_relu(x)


class Encoder(nn.Module):
    """32×32 → 16×16 → 8×8。最后接 residual stack。"""

    def __init__(self, in_ch: int = 3, hidden_dim: int = HIDDEN_DIM, embedding_dim: int = EMBEDDING_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, hidden_dim // 2, kernel_size=4, stride=2, padding=1),   # 32→16
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden_dim // 2, hidden_dim, kernel_size=4, stride=2, padding=1),  # 16→8
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            ResidualStack(hidden_dim, hidden_dim // 2, num_blocks=2),
            nn.Conv2d(hidden_dim, embedding_dim, kernel_size=1),
        )

    def forward(self, x):
        return self.net(x)  # (B, embedding_dim, 8, 8)


class Decoder(nn.Module):
    """8×8 → 16×16 → 32×32。题面要求"自行补全"的部分。"""

    def __init__(self, out_ch: int = 3, hidden_dim: int = HIDDEN_DIM, embedding_dim: int = EMBEDDING_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(embedding_dim, hidden_dim, kernel_size=3, padding=1),
            ResidualStack(hidden_dim, hidden_dim // 2, num_blocks=2),
            nn.ConvTranspose2d(hidden_dim, hidden_dim // 2, kernel_size=4, stride=2, padding=1),  # 8→16
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(hidden_dim // 2, out_ch, kernel_size=4, stride=2, padding=1),  # 16→32
            # 最后不加 Tanh / Sigmoid，让 loss 直接 MSE 到 [0,1]-normalized 图
        )

    def forward(self, z_q):
        return self.net(z_q)


class VectorQuantizer(nn.Module):
    """
    三步:
      (1) 计算每个 ze 向量到 codebook 所有向量的距离
      (2) argmin 找最近邻索引
      (3) straight-through estimator: 前向取 zq, 反向 grad 直接传给 ze
    """

    def __init__(self, num_embeddings: int = NUM_EMBEDDINGS,
                 embedding_dim: int = EMBEDDING_DIM,
                 beta: float = COMMITMENT_BETA):
        super().__init__()
        self.num_embeddings = num_embeddings
        self.embedding_dim = embedding_dim
        self.beta = beta
        self.embedding = nn.Embedding(num_embeddings, embedding_dim)
        # 初始化关系到 codebook 是否 collapse
        self.embedding.weight.data.uniform_(-1.0 / num_embeddings, 1.0 / num_embeddings)

    def forward(self, ze: torch.Tensor):
        # ze: (B, D, H, W) → (B, H, W, D) → flatten
        B, D, H, W = ze.shape
        ze_perm = ze.permute(0, 2, 3, 1).contiguous()
        flat = ze_perm.view(-1, D)  # (B*H*W, D)

        # (1) 距离: ||ze||² + ||e||² - 2·ze·eᵀ
        d2 = (
            flat.pow(2).sum(dim=1, keepdim=True)
            + self.embedding.weight.pow(2).sum(dim=1)
            - 2 * flat @ self.embedding.weight.t()
        )
        # (2) argmin
        indices = torch.argmin(d2, dim=1)  # (B*H*W,)
        zq_flat = self.embedding(indices)
        zq = zq_flat.view(B, H, W, D).permute(0, 3, 1, 2).contiguous()

        # codebook loss + commitment loss
        codebook_loss = F.mse_loss(zq, ze.detach())
        commitment_loss = F.mse_loss(ze, zq.detach())
        vq_loss = codebook_loss + self.beta * commitment_loss

        # (3) straight-through
        zq_st = ze + (zq - ze).detach()
        indices_2d = indices.view(B, H, W)
        return zq_st, vq_loss, indices_2d

    @torch.no_grad()
    def get_indices(self, ze: torch.Tensor) -> torch.Tensor:
        """便捷: 仅返回离散 token 索引（02b prior 训练时用）"""
        B, D, H, W = ze.shape
        flat = ze.permute(0, 2, 3, 1).contiguous().view(-1, D)
        d2 = (
            flat.pow(2).sum(dim=1, keepdim=True)
            + self.embedding.weight.pow(2).sum(dim=1)
            - 2 * flat @ self.embedding.weight.t()
        )
        return torch.argmin(d2, dim=1).view(B, H, W)

    @torch.no_grad()
    def indices_to_vectors(self, indices: torch.Tensor) -> torch.Tensor:
        """B×H×W token 索引 → B×D×H×W 量化向量。"""
        B, H, W = indices.shape
        vecs = self.embedding(indices.view(-1))            # (B*H*W, D)
        return vecs.view(B, H, W, -1).permute(0, 3, 1, 2).contiguous()


# ============================================================
# 3) FULL MODEL
# ============================================================
class VQVAE(nn.Module):
    def __init__(self, hidden_dim: int = HIDDEN_DIM,
                 embedding_dim: int = EMBEDDING_DIM,
                 num_embeddings: int = NUM_EMBEDDINGS,
                 beta: float = COMMITMENT_BETA):
        super().__init__()
        self.encoder = Encoder(3, hidden_dim, embedding_dim)
        self.quantizer = VectorQuantizer(num_embeddings, embedding_dim, beta)
        self.decoder = Decoder(3, hidden_dim, embedding_dim)

    def forward(self, x):
        ze = self.encoder(x)
        zq, vq_loss, indices = self.quantizer(ze)
        x_recon = self.decoder(zq)
        return x_recon, vq_loss, indices

    @torch.no_grad()
    def encode_indices(self, x: torch.Tensor) -> torch.Tensor:
        return self.quantizer.get_indices(self.encoder(x))

    @torch.no_grad()
    def decode_indices(self, indices: torch.Tensor) -> torch.Tensor:
        zq = self.quantizer.indices_to_vectors(indices)
        return self.decoder(zq)


# ============================================================
# 4) TRAIN (复用 _common.trainer)
# ============================================================
def compute_loss(model: VQVAE, batch):
    imgs, _ = batch
    imgs = imgs.to(next(model.parameters()).device)
    x_recon, vq_loss, _ = model(imgs)
    recon_loss = F.mse_loss(x_recon, imgs)
    loss = recon_loss + vq_loss
    return loss, x_recon


@torch.no_grad()
def eval_fn(model: VQVAE, val_loader: DataLoader, device: str):
    model.eval()
    total, n = 0.0, 0
    for imgs, _ in val_loader:
        imgs = imgs.to(device)
        x_recon, _, _ = model(imgs)
        total += F.mse_loss(x_recon, imgs, reduction="sum").item()
        n += imgs.numel()
    # metric 越小越好 → 返回负数让 trainer "higher better" 仍然有效
    mse = total / max(n, 1)
    return {"metric": -mse, "recon_mse": mse}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_path", default=DATA_PATH)
    parser.add_argument("--out_dir", default=OUT_DIR)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    parser.add_argument("--lr", type=float, default=LR)
    args = parser.parse_args()

    Path(args.out_dir, "checkpoints").mkdir(parents=True, exist_ok=True)

    # CIFAR-10 加载
    tfm = transforms.Compose([
        transforms.ToTensor(),  # [0,1]
    ])
    train_set = datasets.CIFAR10(args.data_path, train=True, download=False, transform=tfm)
    val_set = datasets.CIFAR10(args.data_path, train=False, download=False, transform=tfm)
    train_loader = DataLoader(train_set, batch_size=args.batch, shuffle=True,
                              num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_set, batch_size=args.batch, shuffle=False,
                            num_workers=2, pin_memory=True)

    model = VQVAE()
    cfg = TrainConfig(
        out_dir=str(Path(args.out_dir) / "checkpoints"),
        epochs=args.epochs,
        lr=args.lr,
        weight_decay=0.0,        # VQ-VAE 不需要 wd
        amp=True,
        metric_higher_better=True,
    )
    trainer = Trainer(model, train_loader, val_loader, compute_loss, eval_fn, cfg)
    trainer.fit()

    # 题目要求的 ckpt 路径
    final_path = Path(args.out_dir) / "checkpoints" / "vqvae.pt"
    torch.save(model.state_dict(), final_path)
    print(f"[OK] vqvae state_dict → {final_path}")


if __name__ == "__main__":
    main()

"""
Transformer 自回归 Prior + 图像补全（对标 2026 冬 T2 步骤 2+3）
================================================================

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. VQVAE_CKPT        - 02a 训出来的 vqvae.pt
  2. DATA_PATH         - CIFAR-10 数据
  3. OUT_DIR           - 一般 /vepfs/problem2/

依赖:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      torch torchvision

显存预算 (A100 80G):
  6 层 / 256 hidden / batch=128 → ~10 GB
  8 层 / 512 hidden / batch=128 → ~18 GB

运行:
  python 02b_vqvae_prior_transformer.py --do_train
  python 02b_vqvae_prior_transformer.py --do_sample --n_sample 1024
  python 02b_vqvae_prior_transformer.py --do_complete

设计要点（README 必写）:
  - VQ-VAE 冻结，只训 Transformer
  - 序列前加 <BOS>，索引 = NUM_EMBEDDINGS（占用 codebook 末尾）
  - causal mask 用 torch.triu(..., diagonal=1).bool()
  - 采样必须 torch.multinomial + temperature/Top-K，**严禁 argmax**（FID 灾难）
  - complete_image: 上半图编码 → 取前 32 token → 加 <BOS> → AR 补 32 token →
    decode → **上半部分必须用原图替换回去**（关键扣分点）

输出:
  OUT_DIR/checkpoints/vqvae_prior.pt
  OUT_DIR/samples/*.png（采样可视化，可选）
"""

import argparse
import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets, transforms

sys.path.insert(0, str(Path(__file__).parent))
from _common.trainer import Trainer, TrainConfig  # noqa: E402

# 02a 文件以数字开头不能直接 import，用 importlib 桥接
import importlib.util as _ilu  # noqa: E402
_spec = _ilu.spec_from_file_location(
    "vqvae_cifar_mod", str(Path(__file__).parent / "02a_vqvae_cifar.py"))
_vqvae_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_vqvae_mod)
VQVAE = _vqvae_mod.VQVAE
NUM_EMBEDDINGS = _vqvae_mod.NUM_EMBEDDINGS


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
VQVAE_CKPT = os.environ.get("VQVAE_CKPT", "/vepfs/problem2/checkpoints/vqvae.pt")
DATA_PATH = os.environ.get("DATA_PATH", "/vepfs-readonly/problem2/cifar10")
OUT_DIR = os.environ.get("OUT_DIR", "/vepfs/problem2")

# Token 序列: 8*8 = 64 token + 1 BOS = 65 总长
SEQ_LEN_IMG = 64
TOKEN_GRID = 8
VOCAB_SIZE = NUM_EMBEDDINGS + 1   # codebook + <BOS>
BOS_ID = NUM_EMBEDDINGS

# Transformer 默认超参（中等档：A100 上很轻松）
N_LAYERS = 6
N_HEADS = 8
HIDDEN = 384
DROPOUT = 0.1

LR = 3e-4
BATCH_SIZE = 128
EPOCHS = 30

# 采样
TEMPERATURE = 1.0
TOP_K = 50


# ============================================================
# 2) MODEL: Decoder-only Transformer
# ============================================================
class TransformerPrior(nn.Module):
    """
    Decoder-only Transformer，预测下一个 codebook token。
    输入序列: [<BOS>, t_0, t_1, ..., t_62]   (长度 64)
    监督目标: [t_0, t_1, ..., t_63]            (长度 64)
    """

    def __init__(self, vocab_size: int = VOCAB_SIZE,
                 seq_len: int = SEQ_LEN_IMG,
                 hidden: int = HIDDEN,
                 n_layers: int = N_LAYERS,
                 n_heads: int = N_HEADS,
                 dropout: float = DROPOUT):
        super().__init__()
        self.token_emb = nn.Embedding(vocab_size, hidden)
        # 可学习的位置嵌入：序列输入长度 = seq_len（含 BOS 时为 seq_len）
        self.pos_emb = nn.Parameter(torch.zeros(1, seq_len, hidden))
        nn.init.trunc_normal_(self.pos_emb, std=0.02)

        layer = nn.TransformerEncoderLayer(
            d_model=hidden, nhead=n_heads,
            dim_feedforward=hidden * 4, dropout=dropout,
            batch_first=True, norm_first=True, activation="gelu",
        )
        self.blocks = nn.TransformerEncoder(layer, num_layers=n_layers)
        self.ln_f = nn.LayerNorm(hidden)
        self.head = nn.Linear(hidden, vocab_size, bias=False)
        # 经典做法: 共享 token_emb 与 head 权重（更省参，收敛更稳）
        self.head.weight = self.token_emb.weight

        self.seq_len = seq_len

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, L) Long. 返回 (B, L, vocab_size)."""
        B, L = x.shape
        assert L <= self.seq_len, f"seq too long: {L} > {self.seq_len}"
        h = self.token_emb(x) + self.pos_emb[:, :L]
        # causal mask: (L, L), upper triangle = True 表示禁止注意
        mask = torch.triu(torch.ones(L, L, device=x.device, dtype=torch.bool), diagonal=1)
        h = self.blocks(h, mask=mask)
        h = self.ln_f(h)
        return self.head(h)


# ============================================================
# 3) TOKEN DATASET: 把整个 CIFAR-10 编码成 token 序列后缓存
# ============================================================
class TokenDataset(Dataset):
    """提前用 VQ-VAE encode 整个数据集，避免每个 step 重复 encode。"""

    def __init__(self, base_loader: DataLoader, vqvae: VQVAE, device: str):
        vqvae.eval()
        all_tokens = []
        with torch.no_grad():
            for imgs, _ in base_loader:
                imgs = imgs.to(device)
                idx = vqvae.encode_indices(imgs)   # (B, 8, 8)
                all_tokens.append(idx.view(idx.size(0), -1).cpu())  # (B, 64)
        self.tokens = torch.cat(all_tokens, dim=0)  # (N, 64)

    def __len__(self):
        return self.tokens.size(0)

    def __getitem__(self, i):
        return self.tokens[i]


def collate_with_bos(batch):
    """前置 BOS，输入 = [BOS, t_0..t_62]，目标 = [t_0..t_63]。"""
    toks = torch.stack(batch, dim=0)             # (B, 64)
    B = toks.size(0)
    bos = torch.full((B, 1), BOS_ID, dtype=torch.long)
    inp = torch.cat([bos, toks[:, :-1]], dim=1)  # (B, 64)
    tgt = toks                                   # (B, 64)
    return inp, tgt


# ============================================================
# 4) TRAIN
# ============================================================
def compute_loss(model: TransformerPrior, batch):
    inp, tgt = batch
    device = next(model.parameters()).device
    inp, tgt = inp.to(device), tgt.to(device)
    logits = model(inp)                          # (B, 64, V)
    loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), tgt.reshape(-1))
    return loss, logits


@torch.no_grad()
def eval_fn(model: TransformerPrior, val_loader: DataLoader, device: str):
    model.eval()
    total, n = 0.0, 0
    for inp, tgt in val_loader:
        inp, tgt = inp.to(device), tgt.to(device)
        logits = model(inp)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)),
                               tgt.reshape(-1), reduction="sum")
        total += loss.item()
        n += tgt.numel()
    ce = total / max(n, 1)
    ppl = float(torch.exp(torch.tensor(ce)).item())
    return {"metric": -ce, "ce": ce, "ppl": ppl}


# ============================================================
# 5) SAMPLING / COMPLETION
# ============================================================
@torch.no_grad()
def sample_tokens(model: TransformerPrior, n_sample: int, device: str,
                  prefix: torch.Tensor = None,
                  temperature: float = TEMPERATURE, top_k: int = TOP_K) -> torch.Tensor:
    """
    自回归采样 n_sample 条序列。
    prefix: (n_sample, P) — 已知前缀（不含 BOS）；如果 None 则只用 BOS 起步。
    返回: (n_sample, 64) — 完整 token 序列（不含 BOS）。
    """
    model.eval()
    bos = torch.full((n_sample, 1), BOS_ID, dtype=torch.long, device=device)
    if prefix is not None:
        seq = torch.cat([bos, prefix.to(device)], dim=1)
    else:
        seq = bos

    while seq.size(1) - 1 < SEQ_LEN_IMG:
        logits = model(seq)[:, -1, :]            # (B, V)
        # 屏蔽 BOS 不再生成（采样真实 codebook token）
        logits[:, BOS_ID] = -1e9
        logits = logits / max(temperature, 1e-5)
        if top_k is not None and top_k > 0:
            v, _ = torch.topk(logits, top_k)
            logits[logits < v[:, [-1]]] = -1e9
        probs = F.softmax(logits, dim=-1)
        # 关键: multinomial 而非 argmax
        nxt = torch.multinomial(probs, num_samples=1)   # (B, 1)
        seq = torch.cat([seq, nxt], dim=1)

    return seq[:, 1:]   # 去掉 BOS


@torch.no_grad()
def complete_image(vqvae: VQVAE, prior: TransformerPrior,
                   upper_half: torch.Tensor, device: str,
                   temperature: float = TEMPERATURE, top_k: int = TOP_K) -> torch.Tensor:
    """
    upper_half: (B, 3, 16, 32) — 原图上半部分。
    返回: (B, 3, 32, 32) — 完整图，**上半部分必须用原图替换回去**。
    """
    vqvae.eval()
    prior.eval()
    B = upper_half.size(0)

    # 1) pad 成全图（下半补 0，仅为了走 encoder 拿到上半的 token）
    pad_lower = torch.zeros(B, 3, 16, 32, device=device)
    full_pad = torch.cat([upper_half, pad_lower], dim=2)   # (B, 3, 32, 32)

    # 2) encode → (B, 8, 8) token，取前 4 行（32 token）作为已知前缀
    tokens_pad = vqvae.encode_indices(full_pad)            # (B, 8, 8)
    known_prefix = tokens_pad[:, :4, :].reshape(B, -1)     # (B, 32)

    # 3) 用 prior 自回归补全后 32 token
    full_tokens = sample_tokens(prior, B, device,
                                prefix=known_prefix,
                                temperature=temperature, top_k=top_k)   # (B, 64)
    full_tokens = full_tokens.view(B, TOKEN_GRID, TOKEN_GRID)

    # 4) decode 整张图
    img_recon = vqvae.decode_indices(full_tokens).clamp(0, 1)

    # 5) **上半部分用原图覆盖**——关键扣分点
    img_recon[:, :, :16, :] = upper_half
    return img_recon


# ============================================================
# 6) MAIN
# ============================================================
def load_vqvae(ckpt_path: str, device: str) -> VQVAE:
    model = VQVAE().to(device)
    state = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(state)
    model.eval()
    for p in model.parameters():
        p.requires_grad = False
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vqvae_ckpt", default=VQVAE_CKPT)
    parser.add_argument("--data_path", default=DATA_PATH)
    parser.add_argument("--out_dir", default=OUT_DIR)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    parser.add_argument("--lr", type=float, default=LR)
    parser.add_argument("--do_train", action="store_true")
    parser.add_argument("--do_sample", action="store_true")
    parser.add_argument("--do_complete", action="store_true")
    parser.add_argument("--n_sample", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--top_k", type=int, default=TOP_K)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    Path(args.out_dir, "checkpoints").mkdir(parents=True, exist_ok=True)
    Path(args.out_dir, "samples").mkdir(parents=True, exist_ok=True)

    vqvae = load_vqvae(args.vqvae_ckpt, device)
    prior = TransformerPrior().to(device)

    # ============ TRAIN ============
    if args.do_train:
        tfm = transforms.Compose([transforms.ToTensor()])
        train_set = datasets.CIFAR10(args.data_path, train=True, download=False, transform=tfm)
        val_set = datasets.CIFAR10(args.data_path, train=False, download=False, transform=tfm)

        # 提前编码成 token，省时间
        token_loader_train = DataLoader(train_set, batch_size=256, num_workers=4)
        token_loader_val = DataLoader(val_set, batch_size=256, num_workers=2)
        train_tokens = TokenDataset(token_loader_train, vqvae, device)
        val_tokens = TokenDataset(token_loader_val, vqvae, device)

        train_loader = DataLoader(train_tokens, batch_size=args.batch, shuffle=True,
                                  collate_fn=collate_with_bos, num_workers=2)
        val_loader = DataLoader(val_tokens, batch_size=args.batch, shuffle=False,
                                collate_fn=collate_with_bos, num_workers=2)

        cfg = TrainConfig(
            out_dir=str(Path(args.out_dir) / "checkpoints"),
            epochs=args.epochs,
            lr=args.lr,
            amp=True,
            metric_higher_better=True,
        )
        trainer = Trainer(prior, train_loader, val_loader, compute_loss, eval_fn, cfg)
        trainer.fit()
        final_path = Path(args.out_dir) / "checkpoints" / "vqvae_prior.pt"
        torch.save(prior.state_dict(), final_path)
        print(f"[OK] prior → {final_path}")
    else:
        # 加载 prior
        p = Path(args.out_dir) / "checkpoints" / "vqvae_prior.pt"
        if p.exists():
            prior.load_state_dict(torch.load(p, map_location=device))
            print(f"[load] {p}")

    # ============ SAMPLE ============
    if args.do_sample:
        from torchvision.utils import save_image
        tokens = sample_tokens(prior, args.n_sample, device,
                               temperature=args.temperature, top_k=args.top_k)
        imgs = vqvae.decode_indices(tokens.view(-1, TOKEN_GRID, TOKEN_GRID)).clamp(0, 1)
        out_path = Path(args.out_dir) / "samples" / "uncond_samples.png"
        save_image(imgs[:64], str(out_path), nrow=8)
        print(f"[OK] uncond samples → {out_path}")

    # ============ COMPLETE ============
    if args.do_complete:
        # 从 CIFAR test 集前 64 张取上半部分做演示
        from torchvision.utils import save_image
        tfm = transforms.Compose([transforms.ToTensor()])
        test_set = datasets.CIFAR10(args.data_path, train=False, download=False, transform=tfm)
        imgs = torch.stack([test_set[i][0] for i in range(64)], dim=0).to(device)
        upper = imgs[:, :, :16, :]
        completed = complete_image(vqvae, prior, upper, device,
                                   temperature=args.temperature, top_k=args.top_k)
        save_image(completed, str(Path(args.out_dir) / "samples" / "completed.png"), nrow=8)
        save_image(imgs, str(Path(args.out_dir) / "samples" / "gt.png"), nrow=8)
        print("[OK] completions saved.")


if __name__ == "__main__":
    main()

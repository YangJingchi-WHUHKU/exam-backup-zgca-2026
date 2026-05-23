"""
ESM 蛋白质溶解性二分类微调 - 2024 秋真题同款
================================================

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. CKPT_PATH     - ESM checkpoint, 默认 /vepfs/problem2/ESM-checkpoint/esm2_t6_8M_UR50D.pt
  2. ESM_REPO      - 题目给的 esm 仓库（如果环境没装 esm，sys.path.insert）
  3. LMDB_PATH     - lmdb 数据集路径
  4. DATASET_LOAD  - 用题目给的 ProteinSolubilityLMBDataset.load 替换 mock
  5. OUT_JSON      - 提交路径，默认 /vepfs/problem2/test_result.json
  6. NAME          - 改成你自己的中文名（提交 JSON 的 name 字段）

依赖（现场 pip install）:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple fair-esm lmdb
  # esm 通常题目环境已装；装不上时:
  # pip install -e /vepfs-readonly/problem2/esm

显存预算 (A100 80G):
  ESM-100M  (esm2_t6_8M)    + 冻结 backbone + batch=16 → ~ 4 GB
  ESM-650M  (esm2_t33_650M) + 冻结 backbone + batch=8  → ~12 GB
  ESM-3B    (esm2_t36_3B)   + 冻结 backbone + batch=4  → ~30 GB

运行:
  python 03_protein_esm_finetune.py --do_train --do_predict
  python 03_protein_esm_finetune.py --ckpt /vepfs/problem2/ESM-checkpoint/esm2_t6_8M_UR50D.pt
"""

import argparse
import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

# 让 _common.* 能从任何 cwd import（考场上通常从 templates/ 直接跑）
sys.path.insert(0, str(Path(__file__).parent))
from _common.trainer import Trainer, TrainConfig  # noqa: E402
from _common.submit_json import write_protein_submission, validate_protein_submission  # noqa: E402


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
CKPT_PATH = os.environ.get("CKPT_PATH", "/vepfs/problem2/ESM-checkpoint/esm2_t6_8M_UR50D.pt")
ESM_REPO = os.environ.get("ESM_REPO", "/vepfs-readonly/problem2/esm")
LMDB_PATH = os.environ.get("LMDB_PATH", "/vepfs-readonly/problem2/solubility_mutetest.lmdb")
OUT_JSON = os.environ.get("OUT_JSON", "/vepfs/problem2/test_result.json")
NAME = os.environ.get("NAME", "yangjingchi")

# 不同规模 ESM ckpt 的层数（很容易写错——题面默认给 30 是中等规模的，100M 实际是 6）
ESM_LAYERS_HINT = {
    "esm2_t6_8M_UR50D": 6,        # 100M 这一档
    "esm2_t12_35M_UR50D": 12,
    "esm2_t30_150M_UR50D": 30,
    "esm2_t33_650M_UR50D": 33,
    "esm2_t36_3B_UR50D": 36,
    "esm2_t48_15B_UR50D": 48,
}


# ============================================================
# 2) ESM LOADING
# ============================================================
def load_esm(ckpt_path: str):
    """题面强制用 load_model_and_alphabet_core，不能用 from_pretrained"""
    if os.path.isdir(ESM_REPO) and ESM_REPO not in sys.path:
        sys.path.insert(0, ESM_REPO)
    import esm  # noqa: E402

    data = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model_name = Path(ckpt_path).stem
    esm_model, alphabet = esm.pretrained.load_model_and_alphabet_core(model_name, data, None)
    batch_converter = alphabet.get_batch_converter()

    # 动态确定 repr_layers——别用题面默认的 30
    n_layers = ESM_LAYERS_HINT.get(model_name)
    if n_layers is None:
        # ESM-2 的层数 = transformer 块数
        n_layers = len(esm_model.layers)
    hidden_dim = esm_model.embed_dim
    print(f"[esm] {model_name} | layers={n_layers} | hidden={hidden_dim}")
    return esm_model, alphabet, batch_converter, n_layers, hidden_dim


# ============================================================
# 3) DATASET - CHANGE_ME: 换成题面给的接口
# ============================================================
def DATASET_LOAD():
    """用题面给的 ProteinSolubilityLMBDataset.load(lmdb_path) 替换这里"""
    try:
        from solubilitydataset import ProteinSolubilityLMBDataset
        return ProteinSolubilityLMBDataset.load(LMDB_PATH)
    except ImportError:
        print(f"[WARN] solubilitydataset 未找到，用 mock 数据走通 pipeline")
        return _MockDataset.make_split()


class _MockDataset(Dataset):
    """打通流程用的兜底，考场上必须换成真数据集"""
    def __init__(self, items):
        self.items = items

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        return self.items[idx]

    @classmethod
    def make_split(cls):
        import random
        random.seed(42)
        aa = "ACDEFGHIKLMNPQRSTVWY"
        def rand_seq(): return "".join(random.choices(aa, k=random.randint(50, 200)))
        train = [(rand_seq(), random.randint(0, 1)) for _ in range(64)]
        valid = [(rand_seq(), random.randint(0, 1)) for _ in range(16)]
        test = [(f"protein_{i:03d}", rand_seq(), 0) for i in range(8)]  # test 有 name
        return cls(train), cls(valid), cls(test)


# ============================================================
# 4) MODEL: 冻结 ESM + 分类头
# ============================================================
class ProteinClassifier(nn.Module):
    def __init__(self, esm_model, n_layers: int, hidden_dim: int,
                 num_classes: int = 2, pad_idx: int = 1):
        super().__init__()
        self.esm = esm_model
        # 冻结 backbone 节省显存
        for p in self.esm.parameters():
            p.requires_grad = False
        self.esm.eval()

        self.n_layers = n_layers
        self.pad_idx = pad_idx
        self.head = nn.Sequential(
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, batch_tokens):
        # backbone 走 no_grad 减显存
        with torch.no_grad():
            out = self.esm(batch_tokens, repr_layers=[self.n_layers], return_contacts=False)
        hidden = out["representations"][self.n_layers]  # [B, L, D]
        # mask 掉 padding 再 mean pool（不能直接 .mean(1)，padding 会污染）
        mask = (batch_tokens != self.pad_idx).unsqueeze(-1).float()
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
        return self.head(pooled)


# ============================================================
# 5) COLLATE
# ============================================================
def make_collate(batch_converter, is_test: bool = False):
    def collate(batch):
        if is_test:
            # test: (name, seq, dummy_label)
            names = [b[0] for b in batch]
            seqs = [b[1] for b in batch]
            labels = torch.zeros(len(batch), dtype=torch.long)
            formatted = list(zip(names, seqs))
        else:
            # train/valid: (seq, label)
            seqs = [b[0] for b in batch]
            labels = torch.tensor([int(b[1]) for b in batch], dtype=torch.long)
            names = [f"prot_{i}" for i in range(len(batch))]
            formatted = list(zip(names, seqs))
        _, _, tokens = batch_converter(formatted)
        return {"tokens": tokens, "labels": labels, "names": names, "seqs": seqs}
    return collate


# ============================================================
# 6) TRAIN
# ============================================================
def compute_loss_fn(model, batch):
    tokens = batch["tokens"].to(next(model.parameters()).device)
    labels = batch["labels"].to(tokens.device)
    logits = model(tokens)
    loss = nn.functional.cross_entropy(logits, labels)
    return loss, logits


def eval_accuracy(model, loader, device):
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for batch in loader:
            tokens = batch["tokens"].to(device)
            labels = batch["labels"].to(device)
            logits = model(tokens)
            preds = logits.argmax(-1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
    return {"metric": correct / max(1, total), "accuracy": correct / max(1, total)}


# ============================================================
# 7) PREDICT
# ============================================================
@torch.no_grad()
def predict(model, test_loader, device):
    model.eval()
    items = []
    for batch in test_loader:
        tokens = batch["tokens"].to(device)
        logits = model(tokens)
        preds = logits.argmax(-1).cpu().tolist()
        for name, seq, p in zip(batch["names"], batch["seqs"], preds):
            items.append((name, seq, int(p)))
    return items


# ============================================================
# 8) MAIN
# ============================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt", default=CKPT_PATH)
    p.add_argument("--lmdb", default=LMDB_PATH)
    p.add_argument("--out_json", default=OUT_JSON)
    p.add_argument("--out_dir", default="/vepfs/problem2/ckpts")
    p.add_argument("--name", default=NAME)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--do_train", action="store_true")
    p.add_argument("--do_predict", action="store_true")
    args = p.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    esm_model, alphabet, batch_converter, n_layers, hidden_dim = load_esm(args.ckpt)
    esm_model = esm_model.to(device)

    model = ProteinClassifier(esm_model, n_layers, hidden_dim,
                              num_classes=2, pad_idx=alphabet.padding_idx)

    ds_train, ds_valid, ds_test = DATASET_LOAD()
    train_loader = DataLoader(ds_train, batch_size=args.batch, shuffle=True,
                              collate_fn=make_collate(batch_converter, is_test=False))
    val_loader = DataLoader(ds_valid, batch_size=args.batch, shuffle=False,
                            collate_fn=make_collate(batch_converter, is_test=False))
    test_loader = DataLoader(ds_test, batch_size=args.batch, shuffle=False,
                             collate_fn=make_collate(batch_converter, is_test=True))

    if args.do_train:
        cfg = TrainConfig(
            out_dir=args.out_dir, epochs=args.epochs, lr=args.lr,
            warmup_ratio=0.05, scheduler="cosine",
            amp=True, amp_dtype="bf16", grad_clip=1.0,
            log_every=20, metric_higher_better=True,
        )
        Trainer(model, train_loader, val_loader,
                compute_loss=compute_loss_fn, eval_fn=eval_accuracy,
                cfg=cfg, device=device).fit()

    if args.do_predict:
        items = predict(model, test_loader, device)
        write_protein_submission(args.out_json, args.name, items)
        validate_protein_submission(args.out_json)


if __name__ == "__main__":
    main()

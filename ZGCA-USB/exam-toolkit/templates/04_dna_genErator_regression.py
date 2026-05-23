"""
GENErator-v2 DNA Enhancer 活性双头回归 - 2026 冬 T3 真题同款
==============================================================

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. MODEL_PATH     - GENErator ckpt 路径
                      默认 /vepfs-readonly/problem3/hf_downloads/GENErator_v2_eukaryote
  2. DATASET_PATH   - DeepSTARR_enhancer2 数据集路径
                      默认 /vepfs-readonly/problem3/hf_downloads/DeepSTARR_enhancer2
  3. DATASET_LOAD   - 如果题目给的不是 HF datasets 标准格式，改这个函数
  4. OUT_CSV        - 提交 csv 路径
  5. MAX_LEN_TOKENS - 6-mer tokenizer 的 max length（实际 nt 长度 = 这个 × 6）

依赖（现场 pip install）:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      transformers datasets accelerate scipy

显存预算 (A100 80G):
  GENErator-v2 1.2B + 冻结 backbone + batch=8  + max_len=512 → ~16 GB
  GENErator-v2 1.2B + 冻结 backbone + batch=16 + max_len=512 → ~24 GB
  GENErator-v2 1.2B + 全量微调      + batch=4  + max_len=512 → ~55 GB（边界）

运行:
  python 04_dna_genErator_regression.py --do_train --do_predict
  python 04_dna_genErator_regression.py --epochs 5 --batch 8 --lr 3e-5
"""

import argparse
import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoConfig, AutoModel, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from _common.trainer import Trainer, TrainConfig  # noqa: E402
from _common.submit_csv import write_regression_csv, validate_csv  # noqa: E402


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
MODEL_PATH = os.environ.get(
    "MODEL_PATH",
    "/vepfs-readonly/problem3/hf_downloads/GENErator_v2_eukaryote",
)
DATASET_PATH = os.environ.get(
    "DATASET_PATH",
    "/vepfs-readonly/problem3/hf_downloads/DeepSTARR_enhancer2",
)
OUT_CSV = os.environ.get("OUT_CSV", "/vepfs/problem3/test_output.csv")
OUT_DIR = os.environ.get("OUT_DIR", "/vepfs/problem3/ckpts")

# 6-mer 强约束：实际 nt 长度必须是 6 的倍数，否则 tokenizer 产生 <oov>
KMER = 6


# ============================================================
# 2) DATASET - CHANGE_ME 如果不是 HF datasets 格式
# ============================================================
def DATASET_LOAD():
    """题面用 HF datasets。如果是别的格式（jsonl / parquet）改这里"""
    from datasets import load_from_disk, load_dataset
    try:
        ds = load_from_disk(DATASET_PATH)
    except Exception:
        ds = load_dataset(DATASET_PATH)
    return ds["train"], ds["validation"], ds["test"]


class DNARegressionDataset(Dataset):
    """包一层，统一接口；同时做 6-mer 长度对齐"""
    def __init__(self, hf_split, max_nt: int):
        self.split = hf_split
        # 必须是 6 的倍数；这里做安全截断 + 右 pad
        self.max_nt = (max_nt // KMER) * KMER

    def __len__(self):
        return len(self.split)

    def __getitem__(self, idx):
        ex = self.split[int(idx)]
        seq = ex["sequence"].upper()
        # 右截断到 6 的倍数；不足的留给 tokenizer 的 padding（pad token 是合法 token，不会变 OOV）
        if len(seq) > self.max_nt:
            seq = seq[: self.max_nt]
        else:
            # 余数裁掉，避免最后一段不足 6 的产生 OOV
            keep = (len(seq) // KMER) * KMER
            seq = seq[:keep]
        label = ex.get("label", [0.0, 0.0])
        return {"sequence": seq, "label": torch.tensor(label, dtype=torch.float32)}


# ============================================================
# 3) TOKENIZER & MODEL
# ============================================================
def build_tokenizer(model_path: str):
    """题面给定设置：padding_side=right, truncation_side=right, pad=eos"""
    tok = AutoTokenizer.from_pretrained(
        model_path, trust_remote_code=True,
        padding_side="right", truncation_side="right",
    )
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    return tok


class DNARegressor(nn.Module):
    def __init__(self, backbone, hidden_dim: int, out_dim: int = 2, freeze: bool = True):
        super().__init__()
        self.backbone = backbone
        if freeze:
            for p in self.backbone.parameters():
                p.requires_grad = False
            self.backbone.eval()
        self._frozen = freeze
        self.head = nn.Sequential(
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, out_dim),
        )

    def forward(self, input_ids, attention_mask):
        # 冻结时省一份梯度
        ctx = torch.no_grad() if self._frozen else torch.enable_grad()
        with ctx:
            out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        hidden = out.last_hidden_state  # [B, L, D]
        # attention_mask 加权 mean pooling——直接 .mean(1) 会被 padding 污染
        mask = attention_mask.unsqueeze(-1).float()
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
        return self.head(pooled)


# ============================================================
# 4) COLLATE
# ============================================================
def make_collate(tokenizer, max_len_tokens: int):
    def collate(batch):
        seqs = [b["sequence"] for b in batch]
        labels = torch.stack([b["label"] for b in batch], dim=0)
        enc = tokenizer(
            seqs,
            padding="longest",
            truncation=True,
            max_length=max_len_tokens,
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"],
            "attention_mask": enc["attention_mask"],
            "labels": labels,
        }
    return collate


# ============================================================
# 5) TRAIN / EVAL
# ============================================================
def compute_loss_fn(model, batch):
    device = next(model.parameters()).device
    input_ids = batch["input_ids"].to(device)
    attn = batch["attention_mask"].to(device)
    labels = batch["labels"].to(device)
    preds = model(input_ids, attn)
    loss = nn.functional.mse_loss(preds, labels)
    return loss, preds


def pearson(x: torch.Tensor, y: torch.Tensor) -> float:
    """手写 Pearson，避免依赖 scipy（题目环境不保证）"""
    x = x - x.mean()
    y = y - y.mean()
    denom = (x.norm() * y.norm()).clamp(min=1e-8)
    return float((x * y).sum() / denom)


def eval_pearson(model, loader, device):
    model.eval()
    preds_all, labels_all = [], []
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attn = batch["attention_mask"].to(device)
            preds = model(input_ids, attn).cpu()
            preds_all.append(preds)
            labels_all.append(batch["labels"])
    preds = torch.cat(preds_all, dim=0)
    labels = torch.cat(labels_all, dim=0)
    r1 = pearson(preds[:, 0], labels[:, 0])
    r2 = pearson(preds[:, 1], labels[:, 1])
    return {"metric": (r1 + r2) / 2, "pearson_dev": r1, "pearson_hk": r2}


# ============================================================
# 6) PREDICT
# ============================================================
@torch.no_grad()
def predict(model, test_loader, device):
    model.eval()
    rows = []
    for batch in test_loader:
        input_ids = batch["input_ids"].to(device)
        attn = batch["attention_mask"].to(device)
        preds = model(input_ids, attn).cpu().tolist()
        rows.extend(preds)
    return rows


# ============================================================
# 7) MAIN
# ============================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model_path", default=MODEL_PATH)
    p.add_argument("--dataset_path", default=DATASET_PATH)
    p.add_argument("--out_csv", default=OUT_CSV)
    p.add_argument("--out_dir", default=OUT_DIR)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--lr", type=float, default=3e-5)
    p.add_argument("--max_nt", type=int, default=3072,
                   help="实际 nt 长度上限；必须是 6 的倍数")
    p.add_argument("--max_len_tokens", type=int, default=512,
                   help="tokenizer max_length；6-mer 后大概 nt/6")
    p.add_argument("--no_freeze", action="store_true", help="不冻结 backbone（慢且费显存）")
    p.add_argument("--do_train", action="store_true")
    p.add_argument("--do_predict", action="store_true")
    args = p.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    tokenizer = build_tokenizer(args.model_path)
    config = AutoConfig.from_pretrained(args.model_path, trust_remote_code=True)
    backbone = AutoModel.from_pretrained(
        args.model_path, trust_remote_code=True,
        torch_dtype=torch.bfloat16,  # 1.2B 用 bf16 节省显存
    )
    hidden_dim = getattr(config, "hidden_size", None) or backbone.config.hidden_size
    model = DNARegressor(backbone, hidden_dim, out_dim=2, freeze=(not args.no_freeze))

    ds_train_raw, ds_val_raw, ds_test_raw = DATASET_LOAD()
    max_nt = (args.max_nt // KMER) * KMER
    ds_train = DNARegressionDataset(ds_train_raw, max_nt=max_nt)
    ds_val = DNARegressionDataset(ds_val_raw, max_nt=max_nt)
    ds_test = DNARegressionDataset(ds_test_raw, max_nt=max_nt)

    collate = make_collate(tokenizer, args.max_len_tokens)
    train_loader = DataLoader(ds_train, batch_size=args.batch, shuffle=True, collate_fn=collate)
    val_loader = DataLoader(ds_val, batch_size=args.batch, shuffle=False, collate_fn=collate)
    test_loader = DataLoader(ds_test, batch_size=args.batch, shuffle=False, collate_fn=collate)

    if args.do_train:
        cfg = TrainConfig(
            out_dir=args.out_dir, epochs=args.epochs, lr=args.lr,
            warmup_ratio=0.05, scheduler="linear",
            amp=True, amp_dtype="bf16", grad_clip=1.0,
            log_every=50, metric_higher_better=True,
        )
        Trainer(model, train_loader, val_loader,
                compute_loss=compute_loss_fn, eval_fn=eval_pearson,
                cfg=cfg, device=device).fit()

    if args.do_predict:
        rows = predict(model, test_loader, device)
        write_regression_csv(args.out_csv, rows, header=("label1", "label2"))
        validate_csv(args.out_csv, expected_n=len(ds_test), expected_cols=2)


if __name__ == "__main__":
    main()

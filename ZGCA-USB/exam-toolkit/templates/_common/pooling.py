"""
序列池化工具 - 蛋白 / DNA / 文本通用
=====================================

约定输入：
  hidden          : [B, L, D]  (transformer 输出的 last_hidden_state)
  attention_mask  : [B, L]     (1=valid, 0=pad)

返回：[B, D]
"""

from __future__ import annotations

import torch


def mean_pool(hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """Mask-aware mean pool。pad token 不参与平均。"""
    mask = attention_mask.unsqueeze(-1).to(hidden.dtype)         # [B, L, 1]
    summed = (hidden * mask).sum(dim=1)                          # [B, D]
    denom = mask.sum(dim=1).clamp(min=1e-9)                      # [B, 1]
    return summed / denom


def cls_pool(hidden: torch.Tensor) -> torch.Tensor:
    """取第 0 个 token (BERT [CLS] / ESM <cls>)。"""
    return hidden[:, 0]


def last_token_pool(hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """取最后一个非 pad token。Decoder-only LLM 常用。"""
    # 找每行最后一个 1 的位置
    seq_len = attention_mask.sum(dim=1) - 1                      # [B]
    seq_len = seq_len.clamp(min=0).long()
    idx = torch.arange(hidden.size(0), device=hidden.device)
    return hidden[idx, seq_len]


def max_pool(hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """Mask-aware max pool。pad 位置置 -inf 防止干扰。"""
    mask = attention_mask.unsqueeze(-1).bool()                   # [B, L, 1]
    h = hidden.masked_fill(~mask, float("-inf"))
    return h.max(dim=1).values


def weighted_pool(hidden: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    """自定义权重池化。weights: [B, L]，会自动归一化。"""
    w = weights.unsqueeze(-1).to(hidden.dtype)                   # [B, L, 1]
    w = w / w.sum(dim=1, keepdim=True).clamp(min=1e-9)
    return (hidden * w).sum(dim=1)


# ---------- 自检 ----------
if __name__ == "__main__":
    B, L, D = 2, 5, 4
    h = torch.randn(B, L, D)
    m = torch.tensor([[1, 1, 1, 0, 0],
                      [1, 1, 1, 1, 1]])
    print("mean:", mean_pool(h, m).shape)
    print("cls:", cls_pool(h).shape)
    print("last:", last_token_pool(h, m).shape)
    print("max:", max_pool(h, m).shape)
    print("weighted:", weighted_pool(h, m.float()).shape)

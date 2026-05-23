"""
通用评测指标 - 所有题共用
=========================

纯函数，无副作用。输入接受 numpy / torch 都行，内部统一转 numpy。
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np


# ---------- 共用 helper ----------
def _to_np(x) -> np.ndarray:
    """torch.Tensor / list / numpy → numpy（不在 GPU 上 detach 会报错，统一搬 CPU）"""
    if hasattr(x, "detach"):
        x = x.detach().cpu().numpy()
    return np.asarray(x)


# ---------- 分类 ----------
def accuracy(preds, labels) -> float:
    p, y = _to_np(preds), _to_np(labels)
    if p.ndim > 1:
        p = p.argmax(axis=-1)
    return float((p == y).mean())


def top_k_accuracy(logits, labels, k: int = 5) -> float:
    """logits: [N, C], labels: [N]"""
    logits = _to_np(logits)
    labels = _to_np(labels)
    topk = np.argpartition(-logits, kth=k - 1, axis=-1)[:, :k]
    correct = (topk == labels[:, None]).any(axis=-1)
    return float(correct.mean())


# ---------- 回归 ----------
def mse(preds, labels) -> float:
    p, y = _to_np(preds), _to_np(labels)
    return float(np.mean((p - y) ** 2))


def rmse(preds, labels) -> float:
    return math.sqrt(mse(preds, labels))


def mae(preds, labels) -> float:
    p, y = _to_np(preds), _to_np(labels)
    return float(np.mean(np.abs(p - y)))


def pearson_corr(preds, labels) -> float:
    """手写 Pearson 相关系数，不依赖 scipy。"""
    p, y = _to_np(preds).astype(np.float64), _to_np(labels).astype(np.float64)
    p = p - p.mean()
    y = y - y.mean()
    denom = math.sqrt((p * p).sum() * (y * y).sum())
    if denom < 1e-12:
        return 0.0
    return float((p * y).sum() / denom)


def spearman_corr(preds, labels) -> float:
    """Spearman = Pearson on ranks。用 scipy 优先，没装就手写 rank。"""
    try:
        from scipy.stats import spearmanr
        return float(spearmanr(_to_np(preds), _to_np(labels)).correlation)
    except ImportError:
        p, y = _to_np(preds), _to_np(labels)
        p_rank = np.argsort(np.argsort(p))
        y_rank = np.argsort(np.argsort(y))
        return pearson_corr(p_rank, y_rank)


# ---------- 点云 / 几何 ----------
def chamfer_distance(X, Y) -> float:
    """对称 Chamfer。X, Y: [N, D] / [M, D]，返回单一标量。

    naive O(N*M)，N/M 上千就够用；上万建议 torch 实现或 sklearn 的 BallTree。
    """
    X, Y = _to_np(X).astype(np.float32), _to_np(Y).astype(np.float32)
    # pairwise squared dist via (a - b)^2 = a^2 + b^2 - 2ab
    xx = (X * X).sum(axis=1, keepdims=True)        # [N, 1]
    yy = (Y * Y).sum(axis=1, keepdims=True).T      # [1, M]
    d = xx + yy - 2.0 * X @ Y.T                    # [N, M]
    np.maximum(d, 0.0, out=d)
    d_xy = d.min(axis=1).mean()
    d_yx = d.min(axis=0).mean()
    return float(d_xy + d_yx)


# ---------- 生成 ----------
def fid_score(real_features: np.ndarray, fake_features: np.ndarray,
              eps: float = 1e-6) -> float:
    """
    FID 用预提取的 Inception/CLIP 特征向量算（[N, D]）。
    模板里不下载 Inception，要求调用方先把图片 → 特征向量。

    FID = ||mu_r - mu_f||^2 + Tr(Sigma_r + Sigma_f - 2*sqrt(Sigma_r @ Sigma_f))
    """
    rf, ff = _to_np(real_features), _to_np(fake_features)
    mu_r, mu_f = rf.mean(axis=0), ff.mean(axis=0)
    cov_r = np.cov(rf, rowvar=False)
    cov_f = np.cov(ff, rowvar=False)
    diff = mu_r - mu_f

    # 矩阵平方根，避免依赖 scipy.linalg.sqrtm 时的退路
    try:
        from scipy.linalg import sqrtm
        covmean = sqrtm(cov_r @ cov_f + eps * np.eye(cov_r.shape[0]))
        if np.iscomplexobj(covmean):
            covmean = covmean.real
    except ImportError:
        # 退而求其次：用特征分解近似
        prod = cov_r @ cov_f + eps * np.eye(cov_r.shape[0])
        w, v = np.linalg.eigh((prod + prod.T) / 2)
        w = np.maximum(w, 0.0)
        covmean = (v * np.sqrt(w)) @ v.T

    fid = diff @ diff + np.trace(cov_r + cov_f - 2.0 * covmean)
    return float(fid)


# ---------- 简易自检 ----------
if __name__ == "__main__":
    preds = np.array([0.1, 0.9, 0.3, 0.7])
    labels = np.array([0.0, 1.0, 0.0, 1.0])
    print("mse:", mse(preds, labels))
    print("pearson:", pearson_corr(preds, labels))
    print("spearman:", spearman_corr(preds, labels))

    logits = np.random.randn(5, 10)
    y = np.random.randint(0, 10, size=5)
    print("acc:", accuracy(logits, y))
    print("top5:", top_k_accuracy(logits, y, k=5))

    X = np.random.randn(50, 3)
    Y = np.random.randn(60, 3)
    print("chamfer:", chamfer_distance(X, Y))

    rf = np.random.randn(100, 64)
    ff = np.random.randn(100, 64) + 0.1
    print("fid:", fid_score(rf, ff))

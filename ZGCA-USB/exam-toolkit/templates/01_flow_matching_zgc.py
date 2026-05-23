"""
Flow Matching: Z → G → C 2D 点云演变（对标 2026 冬 T1）
========================================================

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. OUT_DIR           - 一般 /vepfs/problem1/
  2. make_letter_*()   - 如果题目给了三个分布的官方采样器，替换这三个函数
  3. BATCH_SIZE/ITER   - 训不动时调

依赖（A100 80G 上几乎肯定已装好）:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      torch numpy matplotlib

显存预算 (A100 80G):
  MLP 仅几 MB，纯 CPU 都能跑；BATCH_SIZE=512 训练 < 1 GB

运行:
  python 01_flow_matching_zgc.py
  python 01_flow_matching_zgc.py --iter 5000 --batch 512

设计要点（README 必写）:
  - 单模型 v_θ(x, t) 覆盖 t∈[0,2]（题面 +8 分关键）
  - Tanh 激活：平滑几何变换比 ReLU 更稳
  - 阶段一 t∈[0,1] 走 Z→G，阶段二 t∈[1,2] 走 G→C，同 batch 混合训练
  - Euler 法 20 步采样（dt=0.1），从 t=0 积分到 t=2

提交（按题面要求）:
  results/zgc.jpg            - 4×4 网格图
  results/zgc.json           - {start, mid, end} 点云
  results/zgc_chamfer.json   - CD 评估
"""

import argparse
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 服务器环境必须
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
OUT_DIR = os.environ.get("OUT_DIR", "/vepfs/problem1")

BATCH_SIZE = 512
ITERATIONS = 5000
LR = 1e-3
N_SAMPLE = 2000
HIDDEN = 128
N_EULER_STEPS = 20    # dt = 2 / 20 = 0.1


# ============================================================
# 2) 字形点云（如题面给了官方采样器就替换这三个）
# ============================================================
# 用一组锚点近似字母轮廓 + 在线段上均匀采样，再加微小噪声扰动
def _sample_polyline(anchors: np.ndarray, n: int, jitter: float = 0.015) -> np.ndarray:
    """沿一组锚点形成的折线均匀采样 n 个点。anchors: (K, 2)"""
    seg_lens = np.linalg.norm(np.diff(anchors, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg_lens)])
    total = cum[-1]
    ts = np.random.uniform(0, total, size=n)
    pts = np.empty((n, 2), dtype=np.float32)
    for i, t in enumerate(ts):
        idx = int(np.searchsorted(cum, t, side="right") - 1)
        idx = max(0, min(idx, len(anchors) - 2))
        local = (t - cum[idx]) / max(seg_lens[idx], 1e-8)
        pts[i] = anchors[idx] + local * (anchors[idx + 1] - anchors[idx])
    pts += np.random.randn(*pts.shape).astype(np.float32) * jitter
    return pts


def make_letter_Z(n: int) -> np.ndarray:
    """字母 Z：上横 → 对角线 → 下横"""
    anchors = np.array([
        [-1.0,  1.0], [1.0,  1.0],     # 上横
        [1.0,  1.0], [-1.0, -1.0],     # 对角线
        [-1.0, -1.0], [1.0, -1.0],     # 下横
    ], dtype=np.float32)
    return _sample_polyline(anchors, n)


def make_letter_G(n: int) -> np.ndarray:
    """字母 G：圆弧 + 中间小横（用极坐标近似）"""
    # 大圆弧（缺口在右侧），范围约 30° → 330°
    theta_arc = np.random.uniform(np.deg2rad(30), np.deg2rad(330), size=int(n * 0.8))
    arc = np.stack([np.cos(theta_arc), np.sin(theta_arc)], axis=1).astype(np.float32)
    # 中间横（G 的内勾）
    bar_x = np.random.uniform(0.0, 1.0, size=n - len(arc))
    bar_y = np.zeros_like(bar_x)
    bar = np.stack([bar_x, bar_y], axis=1).astype(np.float32)
    pts = np.concatenate([arc, bar], axis=0)
    pts += np.random.randn(*pts.shape).astype(np.float32) * 0.015
    np.random.shuffle(pts)
    return pts


def make_letter_C(n: int) -> np.ndarray:
    """字母 C：单段圆弧（开口朝右）"""
    theta = np.random.uniform(np.deg2rad(45), np.deg2rad(315), size=n)
    pts = np.stack([np.cos(theta), np.sin(theta)], axis=1).astype(np.float32)
    pts += np.random.randn(*pts.shape).astype(np.float32) * 0.015
    return pts


# ============================================================
# 3) MODEL: 单模型速度场 v_θ(x, t)
# ============================================================
class FlowMatchingNet(nn.Module):
    """输入 (x, y, t)，输出速度 (vx, vy)。Tanh 适合平滑几何变换。"""

    def __init__(self, in_dim: int = 2, hidden: int = HIDDEN):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim + 1, hidden),
            nn.Tanh(),
            nn.Linear(hidden, hidden),
            nn.Tanh(),
            nn.Linear(hidden, hidden),
            nn.Tanh(),
            nn.Linear(hidden, in_dim),
        )

    def forward(self, x: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        if t.dim() == 1:
            t = t.unsqueeze(-1)
        return self.net(torch.cat([x, t], dim=-1))


# ============================================================
# 4) TRAIN: 两阶段混合一个 batch
# ============================================================
def train(model: nn.Module, device: str, iterations: int, batch_size: int, lr: float):
    optim = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    for it in range(1, iterations + 1):
        # 每个 iter 都新采一批，避免过拟合到固定锚点
        xz = torch.from_numpy(make_letter_Z(batch_size)).to(device)
        xg = torch.from_numpy(make_letter_G(batch_size)).to(device)
        xc = torch.from_numpy(make_letter_C(batch_size)).to(device)

        # 阶段一: t ∈ [0,1], 线性插值 Z→G, 目标速度 = G - Z
        t1 = torch.rand(batch_size, 1, device=device)
        x_t1 = (1 - t1) * xz + t1 * xg
        v_target1 = xg - xz
        v_pred1 = model(x_t1, t1)
        loss1 = ((v_pred1 - v_target1) ** 2).mean()

        # 阶段二: t ∈ [1,2], τ = t-1, 线性插值 G→C, 目标速度 = C - G
        tau = torch.rand(batch_size, 1, device=device)
        t2 = tau + 1.0   # 落到 [1,2]
        x_t2 = (1 - tau) * xg + tau * xc
        v_target2 = xc - xg
        v_pred2 = model(x_t2, t2)
        loss2 = ((v_pred2 - v_target2) ** 2).mean()

        loss = loss1 + loss2
        optim.zero_grad()
        loss.backward()
        optim.step()

        if it % 200 == 0 or it == 1:
            print(f"[iter {it:5d}] loss={loss.item():.4f}  (l1={loss1.item():.4f} l2={loss2.item():.4f})")


# ============================================================
# 5) SAMPLE: Euler 20 步, t=0 → t=2
# ============================================================
@torch.no_grad()
def sample(model: nn.Module, device: str, n_sample: int, n_steps: int = N_EULER_STEPS):
    """返回 (n_steps+1, N, 2) 的轨迹，前后端点分别接近 Z 和 C。"""
    model.eval()
    x = torch.from_numpy(make_letter_Z(n_sample)).to(device)
    dt = 2.0 / n_steps
    trajectory = [x.cpu().numpy()]
    for k in range(n_steps):
        t = torch.full((x.shape[0], 1), k * dt, device=device)
        v = model(x, t)
        x = x + v * dt
        trajectory.append(x.cpu().numpy())
    return np.stack(trajectory, axis=0)  # (T+1, N, 2)


# ============================================================
# 6) EVAL: Chamfer Distance（手写）
# ============================================================
def chamfer_distance(a: np.ndarray, b: np.ndarray) -> float:
    """CD(X,Y) = mean_x min_y ||x-y||² + mean_y min_x ||y-x||²"""
    # 小规模 (N=2000) 全矩阵无压力
    a_t = torch.from_numpy(a).float()
    b_t = torch.from_numpy(b).float()
    # (N, M)
    d2 = torch.cdist(a_t, b_t, p=2) ** 2
    cd = d2.min(dim=1).values.mean().item() + d2.min(dim=0).values.mean().item()
    return cd


# ============================================================
# 7) VISUALIZE: 4×4 网格图
# ============================================================
def plot_grid(trajectory: np.ndarray, out_path: str):
    """trajectory: (T+1, N, 2) — 选 16 个时间步铺到 4×4。"""
    T_plus_1 = trajectory.shape[0]
    idxs = np.linspace(0, T_plus_1 - 1, 16).astype(int)
    fig, axes = plt.subplots(4, 4, figsize=(12, 12))
    for ax, i in zip(axes.flatten(), idxs):
        pts = trajectory[i]
        ax.scatter(pts[:, 0], pts[:, 1], s=2, alpha=0.6)
        ax.set_title(f"t={i * (2.0 / (T_plus_1 - 1)):.2f}")
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.set_aspect("equal")
        ax.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=100)
    plt.close()


# ============================================================
# 8) MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iter", type=int, default=ITERATIONS)
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    parser.add_argument("--lr", type=float, default=LR)
    parser.add_argument("--n_sample", type=int, default=N_SAMPLE)
    parser.add_argument("--out_dir", default=OUT_DIR)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    out = Path(args.out_dir)
    (out / "results").mkdir(parents=True, exist_ok=True)

    model = FlowMatchingNet().to(device)
    train(model, device, args.iter, args.batch, args.lr)

    trajectory = sample(model, device, args.n_sample)  # (T+1, N, 2)
    start = trajectory[0]
    mid = trajectory[len(trajectory) // 2]   # t≈1.0
    end = trajectory[-1]

    # 评估
    z_ref = make_letter_Z(args.n_sample)
    g_ref = make_letter_G(args.n_sample)
    c_ref = make_letter_C(args.n_sample)
    cd_results = {
        "start_vs_Z": chamfer_distance(start, z_ref),
        "mid_vs_G": chamfer_distance(mid, g_ref),
        "end_vs_C": chamfer_distance(end, c_ref),
    }
    print("[CD]", json.dumps(cd_results, indent=2))

    # 写文件
    plot_grid(trajectory, str(out / "results" / "zgc.jpg"))
    with open(out / "results" / "zgc.json", "w") as f:
        json.dump({
            "start": start.tolist(),
            "mid": mid.tolist(),
            "end": end.tolist(),
        }, f)
    with open(out / "results" / "zgc_chamfer.json", "w") as f:
        json.dump(cd_results, f, indent=2)
    print(f"[OK] saved → {out / 'results'}")


if __name__ == "__main__":
    main()

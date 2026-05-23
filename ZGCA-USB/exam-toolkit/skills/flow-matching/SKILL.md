---
name: flow-matching
description: 用 Flow Matching 训练连续时间速度场，做 2D 点云 / 分布插值生成。当题面出现 "Flow Matching / 速度场 / 流匹配 / Z→G→C / 2D 点云 / Chamfer Distance / 字形演变 / 欧拉法采样 / 分布插值" 时触发。对应 2026 冬 T1 原题。
---

# Flow Matching: 2D 点云分布演变

## 何时触发

题面有以下任一关键词：
- Flow Matching / 流匹配 / 速度场 / velocity field
- Z→G→C / 字形 / 2D 点云 / 分布插值
- Chamfer Distance / CD 评估
- 欧拉法 / Euler 采样 / ODE 积分
- "在 t∈[0,2] 时间域" / "单模型覆盖" / "多阶段流"

## 核心模板

**主模板**: `templates/01_flow_matching_zgc.py`（MLP 速度场 + Euler 采样 + CD 评估，单文件 ~280 行）

## 现场操作步骤

### 1. 装包（A100 上几乎肯定已装好）
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    torch numpy matplotlib
```

### 2. 改 CHANGE_ME（template 顶部）
- `OUT_DIR` ← 一般 `/vepfs/problem1/`
- `make_letter_Z/G/C()` ← 如果题目给了官方分布采样器（题面没给就保留代码内字形）
- 超参一般不改：BATCH_SIZE=512, ITERATIONS=5000, LR=1e-3

### 3. 设计选择

#### (a) 单模型 vs 双模型（**+8 分关键**）
**必须用单模型** v_θ(x, t)，一个 MLP 同时学 t∈[0,1] 的 Z→G 段和 t∈[1,2] 的 G→C 段。
- ❌ 双模型：训两个独立 net，t=1 处拼接 → 题面明确说不给这 8 分
- ✅ 单模型：把 t 作为输入，让网络自己根据 t 路由

#### (b) 激活函数：Tanh vs ReLU
**用 Tanh**。题面解题说明强调："Tanh 比 ReLU 更适合平滑几何变换"。ReLU 会产生角点，CD 会差很多。

#### (c) 训练策略：同 batch 混合
```python
# 阶段一: t ∈ [0,1], x_t = (1-t)·x_Z + t·x_G, 目标 v = x_G - x_Z
# 阶段二: τ ∈ [0,1], t = τ+1, x_t = (1-τ)·x_G + τ·x_C, 目标 v = x_C - x_G
# 同一 batch 都算一次, loss = loss1 + loss2
```
不要拆成两个 epoch 分别训——会让 t=1 附近的速度场不连续。

#### (d) 采样：Euler 20 步
```python
x = x_Z; dt = 0.1
for k in range(20):
    t = k * dt        # 0, 0.1, 0.2, ..., 1.9
    x = x + v_θ(x, t) * dt
# 最终 x ≈ C 形分布
```
步数太少 (≤10) 会丢精度，太多 (≥50) 收益不再增长且更慢。

### 4. Chamfer Distance 公式

```
CD(X, Y) = 1/N · Σᵢ minⱼ ||xᵢ-yⱼ||²   +   1/M · Σⱼ minᵢ ||yⱼ-xᵢ||²
```
N=M=2000 时用 `torch.cdist` 全矩阵即可（~16 MB），不必 KDTree。

预期分数：
- 优秀: `mid_vs_G` < 0.03, `end_vs_C` < 0.05
- 合格: < 0.10
- 失败: > 0.20（一般是 ReLU 或双模型导致）

### 5. 启动命令

```bash
python templates/01_flow_matching_zgc.py
# 自动写:
#   $OUT_DIR/results/zgc.jpg
#   $OUT_DIR/results/zgc.json        (start/mid/end 三段点云)
#   $OUT_DIR/results/zgc_chamfer.json
```

## 高分要点

1. **单模型** — README 要专门写一段"统一时域建模 (unified time-domain modeling)"的设计解释（+8 分）
2. **Tanh 激活** — README 写"为何 Tanh 比 ReLU 适合平滑几何变换"
3. **混合训练** — 强调同 batch 同时优化两段，保证 t=1 处速度场连续
4. **CD 评估** — 三个数值都贴进 README，自证合格
5. **4×4 网格图** — 必须铺出 16 帧演变过程，证明轨迹平滑

## 常见坑

| 坑 | 现象 | 解决 |
|---|---|---|
| CD 居高不下 | mid/end CD > 0.3 | 检查激活：是否误用 ReLU；步数 < 20 |
| t=1 附近抖动 | 中间帧形状不像 G | 没有混合训练；要在同一 batch 算 loss1+loss2 |
| 图全黑 | matplotlib 不能 savefig | `matplotlib.use("Agg")` |
| 字形不像字母 | 锚点稀疏 | 增加 N_SAMPLE=2000+；jitter ≤ 0.02 |

## 参考资源（toolkit 内）

- `~/Documents/Obsidian Vault/中关村学院备考/04 科研实训指南.md` — 完整题面
- `cheatsheet/Flow-Matching-公式.md` — 速度场/CD 公式速查
- `refs/flow-matching/` — 论文/示例代码

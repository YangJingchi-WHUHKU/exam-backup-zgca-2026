---
name: vqvae-ar
description: 用 VQ-VAE + 自回归 Transformer prior 做图像生成与补全（CIFAR-10 / 32×32 → 8×8 token）。当题面出现 "VQ-VAE / 向量量化 / codebook / 离散 token / 自回归 / Transformer prior / 图像补全 / FID / causal mask" 时触发。对应 2026 冬 T2 原题，分值最高。
---

# VQ-VAE + Transformer 自回归 Prior：图像生成与补全

## 何时触发

题面有以下任一关键词：
- VQ-VAE / VQVAE / 向量量化 / codebook / commitment loss
- 离散 token / token 序列 / 自回归 Transformer / AR prior
- 图像生成 + FID / 图像补全 / image inpainting / upper-half completion
- CIFAR-10 / 32×32 → 8×8 / causal mask
- "三步：编解码 / Prior / 补全"

## 核心模板

| 模板 | 用途 |
|---|---|
| `templates/02a_vqvae_cifar.py` | 步骤 1：VQ-VAE 编解码器 + 训练 |
| `templates/02b_vqvae_prior_transformer.py` | 步骤 2+3：AR Transformer prior + complete_image() |

两个模板**必须按顺序跑**：先训 VQ-VAE 拿到 `vqvae.pt`，再训 prior。

## 现场操作步骤

### 1. 装包
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    torch torchvision
# FID 评测（题目通常自带 test.py 评分，不一定要装）:
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pytorch-fid
```

### 2. 改 CHANGE_ME

`02a_vqvae_cifar.py` 顶部:
- `DATA_PATH` ← CIFAR-10 数据目录
- `OUT_DIR` ← `/vepfs/problem2/`

`02b_vqvae_prior_transformer.py` 顶部:
- `VQVAE_CKPT` ← `OUT_DIR/checkpoints/vqvae.pt`
- `DATA_PATH` / `OUT_DIR` 同上

### 3. 关键设计选择

#### (a) Codebook collapse 防止
- **commitment β = 0.25**（论文推荐，题面也用这个）
- 初始化：`embedding.weight.uniform_(-1/N, 1/N)`（防止初始化导致死码）
- 如果训练中发现 codebook 利用率 < 50%（很多 token 从来没被选中），可以加 EMA codebook 更新（VQ-VAE 2 论文做法）

#### (b) Decoder 必须自行实现
题面明说 `train_vqvae.py` 的 Decoder 留空。模板里已经写好：
```
8×8 → Conv1×1 → ResidualStack → ConvTranspose 8→16 → ConvTranspose 16→32
```

#### (c) Causal mask（步骤 2 核心扣分点）
```python
mask = torch.triu(torch.ones(L, L, device=x.device, dtype=torch.bool), diagonal=1)
# True 表示**禁止**注意，传给 nn.TransformerEncoder(..., mask=mask)
```
模板已正确实现。

#### (d) **采样必须 multinomial，严禁 argmax**（题面明示）
```python
probs = F.softmax(logits / temperature, dim=-1)
next_token = torch.multinomial(probs, num_samples=1)   # ✅
# next_token = logits.argmax(dim=-1)                   # ❌ FID 会爆掉
```
配合 Top-K=50 + temperature=1.0 起步，FID 不行时调 temperature 到 0.8-1.2 之间。

#### (e) complete_image() 关键规则
```python
# 1. upper_half (16×32) → pad 全图 → VQ-VAE encode → (8,8) token
# 2. 取前 4 行 token (前 32 个) 作为已知前缀
# 3. 加 <BOS> → Transformer 自回归补全后 32 token
# 4. decode 整张图
# 5. **上半部分用原图覆盖**（关键扣分点：题面要求"上半部分与原图一致"）
img_recon[:, :, :16, :] = upper_half
```
不加最后这一步，FID 也许差不多，但**视觉评分会扣大头**——上半图会被 VQ-VAE 压缩损耗。

### 4. 超参（题面给的）

| 模块 | 参数 |
|---|---|
| VQ-VAE | `hidden_dim=128, embedding_dim=64, num_embeddings=512, batch=128, lr=1e-3, β=0.25` |
| Prior  | `layers=6-8, heads=8, hidden=256-512, dropout=0.1` |

显存预算 (A100 80G)：
- VQ-VAE：~5 GB（小模型）
- Prior 6 层/384 hidden：~10 GB
- Prior 8 层/512 hidden：~18 GB

### 5. 启动命令

```bash
# 步骤 1: 训 VQ-VAE (~20 epoch, ~30 min)
python templates/02a_vqvae_cifar.py --epochs 20

# 步骤 2: 训 Prior (~30 epoch, ~1.5 h)
python templates/02b_vqvae_prior_transformer.py --do_train --epochs 30

# 步骤 3: 无条件采样 + 图像补全
python templates/02b_vqvae_prior_transformer.py --do_sample --do_complete --n_sample 1024
```

## 高分要点

1. **Decoder 结构清晰** — Conv1×1 → Residual → ConvTranspose 上采样
2. **straight-through estimator** — `zq + (zq - ze).detach()` 让梯度直接传到编码器
3. **采样用 multinomial + Top-K** — README 必写"避免确定性采样导致的 FID 退化"
4. **complete() 上半部分覆盖原图** — README 必写"对未知区域 AR 生成，已知区域原样输出"
5. **训练曲线** — 两个 train.log 都要保留，证明 reconstruction MSE 下降 + Prior CE 下降

## 常见坑

| 坑 | 现象 | 解决 |
|---|---|---|
| Codebook collapse | 大部分 token 没用上 | 调小 commitment β = 0.1；或开 EMA codebook |
| 重建图模糊 | recon MSE 不降 | 检查 encoder 输出通道是否 = `embedding_dim`；epoch 太少 |
| Prior 采样图灾难 | FID > 200 | **检查是否误用了 argmax**；检查 BOS_ID 是否正确 |
| 补全图上半失真 | 上半视觉对不上原图 | 漏了 `img[:, :, :16, :] = upper_half` 这一步 |
| OOM | Prior 训练 OOM | 降 batch 到 64；或降 hidden 到 256 |
| CE 不降 | 训了 5 epoch CE 还在 6.0+ | 检查 causal mask 是否传了；检查 token 范围 [0, NUM_EMBEDDINGS+1) |

## 备选方案

- 如果 02a 没训出来（codebook collapse 严重）：保底交 02a 的 decoder 实现 + 截图说明 collapse 现象，至少拿步骤 1 的分
- 如果 02b 的 Prior 不收敛：先交无条件采样（哪怕 FID 高），至少拿一部分采样分；complete() 用"上半图+下半噪声"占位也比交空白强

## 参考资源（toolkit 内）

- `~/Documents/Obsidian Vault/中关村学院备考/04 科研实训指南.md` — 完整题面 + 评分细则
- `refs/vqvae/` — 原论文 + 参考实现
- `refs/minGPT/` — Karpathy 的 GPT 实现（causal mask 参考）
- `cheatsheet/VQ-VAE-公式.md` — 损失公式速查

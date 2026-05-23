---
name: ddpo-image
description: 用 TRL DDPOTrainer 把扩散模型当成 MDP 做 RL 微调（aesthetic / compressibility / 自定义 reward）。当题面同时出现 "图像 / diffusion / Stable Diffusion" 和 "RL / reward / 奖励 / DPOK / DDPO / 美学 / 压缩度" 时触发。押宝 image + RL 组合题。
---

# DDPO 扩散模型 RL 微调：押宝 Image + RL 组合题

## 何时触发

题面同时出现「图像生成 / 扩散模型」**和**「RL / 奖励」关键词：
- 扩散侧：Stable Diffusion / SD / SDXL / diffusion / 文生图
- RL 侧：DDPO / DPOK / RLHF / reward / aesthetic / compressibility
- 评测指标：美学分 / aesthetic score / 文件大小 / human preference

判断要点：如果**只**是文生图任务（没 reward）→ 用 LoRA fine-tune；如果**只**是 LLM RL → 走 `grpo-rl`；只有"diffusion + reward"才用本 skill。

## 核心模板

**主模板**: `templates/06_ddpo_diffusion.py`（TRL DDPOTrainer + LoRA + 三种 reward 范式）

## 现场操作步骤

### 1. 装包
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    trl peft diffusers accelerate transformers
# 若用 aesthetic reward:
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple open_clip_torch
```

### 2. 改 CHANGE_ME

`06_ddpo_diffusion.py` 顶部:
- `BASE_MODEL_PATH` ← 题目给的 SD ckpt（如 `/vepfs-readonly/problemX/stable-diffusion-v1-5`）
- `REWARD_TYPE` ← `compressibility` | `aesthetic` | `custom`
- `EXTERNAL_REWARD` ← 如果是 custom：把题目的 reward 接口接进 `reward_custom()` 函数体
- `PROMPT_FN()` ← 题目给的 prompt 分布（默认是 8 条示例 prompt）

### 3. Reward 三种范式（按风险排序）

#### (a) compressibility — **最稳，零外部依赖**
```python
reward = -filesize(jpeg(image, quality=95))   # 单位 KB
```
不需要任何外部模型，纯 PIL。题目没指定 reward 时**首选**这个，至少保证训得动。

#### (b) aesthetic — LAION aesthetic predictor
CLIP ViT-L/14 + 一个浅 MLP 打 [1,10] 美学分。**前提：题目允许 pip install 且给了 LAION 权重**。
模板里给了 stub，考场要把 `AES_WEIGHT_PATH` 改成实际路径。
如果题目没给权重就不要用，否则 reward 是随机数。

#### (c) custom — 题目给的 reward 接口
最常见情况：题目给一个 `external_score(image, prompt) -> float` 函数。
直接在 `reward_custom()` 里调用，**注意接口签名**（DDPO 要求返回 `(rewards, info_dict)`）。

#### (d) 多 reward 组合（可选）
```python
reward_fn = make_multi_reward({
    "compressibility": 1.0,
    "aesthetic": 0.5,
})
```
组合时记得归一化各分支的尺度（compressibility 可能是 -50，aesthetic 可能是 5.5）。

### 4. 显存调参（A100 80G）

| 配置 | 显存 |
|---|---|
| SD 1.5 + LoRA r=4 + train_bs=4 + sample_bs=8 | ~28-32 GB |
| SD 1.5 + LoRA r=8 + train_bs=4 + sample_bs=8 | ~32-36 GB |
| SDXL + LoRA r=4 + train_bs=2 + sample_bs=4   | ~55-60 GB |

OOM 顺序：降 `sample_batch_size` → 降 `sample_num_steps`（50→25）→ 降 `train_batch_size`。

### 5. 启动命令

```bash
# 最稳路径：compressibility reward
python templates/06_ddpo_diffusion.py \
    --base_model $BASE_MODEL_PATH \
    --reward_type compressibility \
    --epochs 20 --sample_num_steps 50 \
    --train_batch_size 4 --sample_batch_size 8

# 题目给了 reward model 时：
python templates/06_ddpo_diffusion.py --reward_type custom --epochs 30
```

## 高分要点

1. **LoRA 必开** — 全量微调 SD 在 A100 80G 上勉强能跑，但极易 mode collapse；LoRA 默认开
2. **KL 约束** — DDPO 默认用 PPO ratio clip = 1e-4 隐式约束；不需要额外加 KL term
3. **per_prompt_stat_tracking** — 开 True 让每个 prompt 单独追踪 baseline，方差更小
4. **reward 设计要稳定** — compressibility 永远能给信号；aesthetic 必须有可靠权重才上
5. **README 写清** — 为什么选这个 reward、reward 曲线、采样图对比（base vs 微调后）

## 常见坑

| 坑 | 现象 | 解决 |
|---|---|---|
| OOM | sample 阶段就炸 | 先降 `sample_batch_size` 到 4，再降 `sample_num_steps` |
| reward 不涨 | 50 epoch 后 reward mean 没变 | 检查 reward 是否真的有信号；检查是否 prompt 全是同一个 |
| Mode collapse | 所有图变成纯色块 | LoRA rank 降到 4；epoch 降到 10；加大 PPO clip |
| aesthetic stub 返回 0 | 没加载 LAION 权重 | 改用 compressibility；或手动加载权重 |
| trl 接口报错 | DDPOConfig 字段名变 | 看 `refs/trl/trl/trainer/ddpo_config.py` 当前版本 |

## 备选：DPOK（如果题目用 KL 显式约束）

DPOK 与 DDPO 区别：
- DDPO: PPO 风格 clip 隐式 KL
- DPOK: 显式 KL term + REINFORCE 风格 policy gradient

如果题面明确写 "with explicit KL constraint to reference model"，需要手写 DPOK（TRL 没有 native 实现）。可以从 DDPOTrainer 派生，重写 `_train_one_batch` 加 KL term。优先级低，**只有题目明确点名才上**。

## 参考资源（toolkit 内）

- `refs/ddpo-pytorch/` — DDPO 论文官方实现
- `refs/trl/trl/trainer/ddpo_trainer.py` — TRL 实现
- HF blog: <https://huggingface.co/blog/trl-ddpo>
- `cheatsheet/DDPO-reward-设计.md` — reward 函数模板

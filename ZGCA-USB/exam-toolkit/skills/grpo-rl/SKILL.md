---
name: grpo-rl
description: 用 TRL 的 GRPOTrainer 在 Qwen 小模型上做 RL 微调。当题面出现 "GRPO / DPO / PPO / RLHF / reward / 奖励函数 / 可验证奖励 / policy gradient" 或 "强化学习微调 LLM" 时触发。压轴题首选。
---

# GRPO RL 微调 - 押宝今年压轴

## 何时触发
题面有以下任一关键词：
- GRPO / DPO / PPO / RLHF / RFT
- reward / 奖励函数 / 可验证奖励 / 验证器
- policy / advantage / KL 约束
- "强化学习微调"、"RL 微调"、"对齐"

## 核心模板
**主模板**: `templates/05a_grpo_qwen.py`（TRL GRPOTrainer，QLoRA，A100 80G 友好）
**备选**: `templates/05b_dpo_qwen.py`（如果题目给的是 preference pair）
**备选**: `templates/05c_ppo_qwen.py`（如果题目要求 vanilla PPO）

## 现场操作步骤

### 1. 装包
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    trl peft bitsandbytes accelerate datasets
# 可选加速:
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple vllm
```

### 2. 改 CHANGE_ME（template 顶部）
- `MODEL_PATH` ← 题目给的 ckpt 路径
- `DATASET_LOAD()` ← 题目给的 dataset 接口
- `reward_*` ← **题目要求的奖励函数**（这是评分关键）
- `OUT_DIR` / `SUBMIT_PATH` ← 题目指定的输出位置

### 3. 奖励函数设计模式

按题目类型选模板：

**(a) 可验证答案（数学/分类/格式）**
```python
def reward_correctness(completions, gold, **kw):
    return [1.0 if extract_answer(c) == g else 0.0
            for c, g in zip(completions, gold)]
```

**(b) 格式合规**
```python
def reward_format(completions, **kw):
    return [0.2 if matches_required_format(c) else 0.0 for c in completions]
```

**(c) 长度控制**
```python
def reward_length(completions, **kw):
    return [0.1 if 50 <= len(c.split()) <= 500 else 0.0 for c in completions]
```

**(d) LLM-as-judge / 外部模型打分**（如果题目给了 reward model）
```python
def reward_external(completions, **kw):
    return [reward_model.score(c) for c in completions]
```

**多奖励组合**：把所有 reward func 都传给 GRPOTrainer，会自动加权求和并独立 log。

### 4. 显存调参（A100 80G）

| 模型 | num_gen | batch | grad_accum | 预计显存 |
|---|---|---|---|---|
| Qwen2.5-0.5B | 8 | 4 | 2 | ~12 GB |
| Qwen2.5-1.5B | 8 | 4 | 2 | ~20 GB |
| Qwen2.5-3B | 4 | 2 | 4 | ~35 GB |
| Qwen2.5-7B | 4 | 1 | 8 | ~55 GB |

OOM 时优先降 `num_gen`，再降 `max_completion_length`，最后再降 `batch`。

### 5. 收敛节奏
- DeepSeek 原论文：300+ 步开始见效
- 实际：每 50 步看 reward mean 是否在涨；如果 200 步还在 0 附近，**奖励函数设计有问题**，回去改
- 经验：合格的 GRPO run 应该看到 reward mean 从 0.0~0.2 涨到 0.5~0.8

### 6. 启动命令

```bash
# 训练 + 推理一条龙
python templates/05a_grpo_qwen.py \
    --model_size 1.5B \
    --steps 300 \
    --use_vllm \
    --do_train --do_predict

# 仅推理（用已训好的 LoRA）
python templates/05a_grpo_qwen.py --do_predict
```

## 高分要点

1. **奖励函数要"稀疏但可验证"** - 二元 0/1 比连续 [0,1] 更稳
2. **必须用 KL 约束**（GRPO 默认 beta=0.04）- 不然模型很快 collapse
3. **left padding** - GRPO 生成必须左 padding，模板已设置
4. **保存 train.log** - 必须能看到 reward mean / KL / loss 三条曲线
5. **README 要说明奖励函数设计逻辑** - 这是评分项

## 常见坑

| 坑 | 现象 | 解决 |
|---|---|---|
| OOM | CUDA out of memory | 降 `num_gen` → 降 `max_completion_length` → 降 `batch` |
| reward 不涨 | 200 步后还在 0 附近 | 检查 reward function 是否真的能给出非零信号 |
| 答案胡说 | 输出文本看着对但 boxed 抽不出 | 加 `reward_format` 强制格式 |
| KL 爆炸 | KL > 10 后 loss 发散 | 降 lr → 1e-6，升 beta → 0.1 |
| vLLM 报错 | colocate 模式启动失败 | 降级到 `--no_vllm`（慢但稳） |

## 备选：DPO（如果题目给的是 preference）

如果题目给的是 `(prompt, chosen, rejected)` 三元组数据，**不要用 GRPO**，用 DPO：
```python
from trl import DPOTrainer, DPOConfig
trainer = DPOTrainer(model, args=DPOConfig(beta=0.1, ...), train_dataset=ds, ...)
```
DPO 更简单更稳，不需要写 reward function。

## 参考资源（toolkit 内）

- `refs/trl/` - HF 官方 TRL 源码
- `refs/unsloth-notebooks/` - 含 Qwen3-4B GRPO notebook
- `docs/trl-grpo-trainer.md` - 离线 GRPO API 文档
- `cheatsheet/GRPO-reward-设计.md` - 多种奖励函数模板

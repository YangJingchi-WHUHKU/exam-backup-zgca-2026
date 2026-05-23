# TRL GRPOTrainer 离线参考文档

> ⭐ 没网时 AI 回答 GRPO API 问题靠这一份文档。
> 基于 TRL 0.9+ / 2025 版本。

---

## 一、GRPO 算法概览

**Group Relative Policy Optimization (GRPO)**：DeepSeek 提出的轻量级 PPO 变种。

核心思想：
- 对同一 prompt 采样 G 个回复（"group"）
- 对每个回复计算 reward
- 用 group 内的 reward 均值/方差归一化得到 advantage（不需要 critic 网络）
- 用类似 PPO 的 clipped objective 更新 policy

**与 PPO 的区别**：
| 维度 | PPO | GRPO |
|------|-----|------|
| Critic 网络 | 需要（value function） | 不需要 |
| Advantage 计算 | GAE | Group 内 reward 标准化 |
| 显存占用 | 大（多 1 个网络） | 小 |
| 训练稳定性 | 中等 | 较高（多 sample 平均） |

---

## 二、GRPOConfig 完整参数

```python
from trl import GRPOConfig

config = GRPOConfig(
    # ===== 输出 =====
    output_dir="./grpo-output",                # 保存目录
    logging_dir="./grpo-output/logs",
    overwrite_output_dir=True,

    # ===== 训练基本参数 =====
    num_train_epochs=1,                        # epochs
    max_steps=-1,                              # 总步数（设>0 会覆盖 epochs）
    per_device_train_batch_size=4,             # 每卡 batch（实际是 prompt 数）
    gradient_accumulation_steps=4,             # 累积步数
    gradient_checkpointing=False,              # 省显存（慢）

    # ===== GRPO 核心 =====
    num_generations=8,                         # ⭐ 每个 prompt 采样多少个 (group size)
    max_prompt_length=512,                     # prompt 截断长度
    max_completion_length=512,                 # 生成最大长度
    temperature=0.9,                           # 采样温度
    top_p=1.0,                                 # nucleus sampling
    top_k=50,                                  # top-k sampling
    repetition_penalty=1.0,                    # 重复惩罚

    # ===== 优化器 =====
    learning_rate=5e-6,                        # ⭐ 通常 1e-6 ~ 1e-5
    lr_scheduler_type="cosine",                # "linear" / "cosine" / "constant"
    warmup_ratio=0.1,                          # warmup 占比
    weight_decay=0.0,
    optim="adamw_torch",                       # "adamw_torch" / "adamw_8bit"
    max_grad_norm=1.0,                         # 梯度裁剪

    # ===== 损失 =====
    beta=0.04,                                 # ⭐ KL 系数 (DeepSeek 默认)
    epsilon=0.2,                               # PPO clip 范围
    epsilon_high=0.28,                         # 非对称 clip 上界（GRPO 论文）
    loss_type="bnpo",                          # "bnpo"(默认) / "dr_grpo" / "grpo"

    # ===== vLLM 加速 =====
    use_vllm=True,                             # ⭐ 强烈推荐开
    vllm_mode='colocate',                      # ⭐ 与 trainer 共显存
    vllm_gpu_memory_utilization=0.4,           # vLLM 占用比例
    vllm_dtype='bfloat16',
    vllm_max_model_len=2048,

    # ===== 日志 =====
    logging_steps=10,
    save_steps=100,
    save_total_limit=2,
    report_to="tensorboard",                   # "wandb" / "tensorboard" / "none"
    log_completions=False,                     # 是否 log 生成样本

    # ===== 数据 =====
    dataloader_num_workers=2,
    remove_unused_columns=False,               # ⭐ 务必 False（保留 ground_truth 等字段）

    # ===== 精度 =====
    bf16=True,                                 # A100 推荐
    fp16=False,

    # ===== 评估 =====
    eval_strategy="no",                        # "no" / "steps" / "epoch"
    eval_steps=200,
    per_device_eval_batch_size=4,

    # ===== seed =====
    seed=42,
)
```

---

## 三、GRPOTrainer 接口

```python
from trl import GRPOTrainer

trainer = GRPOTrainer(
    model="Qwen/Qwen2.5-1.5B-Instruct",       # 模型路径 or 已加载的 nn.Module
    reward_funcs=[reward_fn1, reward_fn2],     # ⭐ List[Callable]
    args=config,
    train_dataset=train_ds,                    # 必须有 "prompt" 字段（chat template 之前的 user msg 或 raw text）
    eval_dataset=eval_ds,                      # 可选
    processing_class=tokenizer,                # tokenizer
    callbacks=[],                              # 可选
    peft_config=lora_config,                   # 可选 PEFT 配置
    reward_weights=[1.0, 0.5],                 # 可选，奖励权重
)

# 训练
trainer.train()
# 保存
trainer.save_model("./final-model")
```

---

## 四、reward_funcs 签名

```python
def reward_func(
    completions: List[str],         # 必传：模型生成的文本
    prompts: List[str] = None,      # 可选：原始 prompt
    **kwargs                        # 可选：dataset 中的其他字段会自动传入
) -> List[float]:                   # 返回：每个 completion 的奖励（float）
    ...
```

**自动传入 kwargs 的规则**：
- 如果 `dataset` 有字段 `ground_truth`，且 `reward_func` 签名有 `ground_truth=None`，自动传入
- 字段名必须匹配
- 设 `remove_unused_columns=False` 保留所有字段

**示例**：
```python
def my_reward(completions, prompts=None, ground_truth=None, difficulty=None, **kwargs):
    rewards = []
    for c, gt, d in zip(completions, ground_truth, difficulty):
        score = compute_score(c, gt)
        if d == "hard":
            score *= 1.5     # 难题加权
        rewards.append(score)
    return rewards

# dataset 必须有这些字段
dataset = Dataset.from_list([
    {"prompt": "What is 2+2?", "ground_truth": "4", "difficulty": "easy"},
    {"prompt": "Prove FLT", "ground_truth": "...", "difficulty": "hard"},
])
```

---

## 五、多奖励组合行为

**TRL 自动**：
1. 调用每个 reward_func → 得到 `[List[float], List[float], ...]`
2. 按 `reward_weights`（默认全 1.0）加权求和 → 总 reward
3. 在 log 中**独立显示**每个 reward 的 mean/std
4. 用总 reward 计算 advantage

**log 中的字段**：
```
{
  "reward": 0.65,                              # 加权总和
  "rewards/correctness_reward": 0.50,          # 独立
  "rewards/format_reward": 0.15,               # 独立
  "rewards/length_reward": 0.00,               # 独立
  "completions/mean_length": 234.5,
  "kl": 0.025,
  "policy_loss": -0.12,
  ...
}
```

---

## 六、vLLM Colocate 模式

```python
config = GRPOConfig(
    use_vllm=True,
    vllm_mode='colocate',                  # ⭐ vs 'server'
    vllm_gpu_memory_utilization=0.4,
    vllm_dtype='bfloat16',
    vllm_max_model_len=2048,
)
```

**Colocate vs Server**：
| 模式 | colocate | server |
|------|---------|--------|
| 部署 | trainer 内部启 | 单独 `vllm serve` |
| 显存 | 共享（A100 80G 推荐） | 独立 |
| 模型同步 | 自动（每步更新） | 需手动 reload |
| 适用 | 单机训练 | 多机 / 多 trainer |

⭐ **单卡 A100 80G 一定用 colocate**。

---

## 七、PEFT / LoRA 集成

```python
from peft import LoraConfig

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

trainer = GRPOTrainer(
    model="Qwen/Qwen2.5-7B",
    args=config,
    reward_funcs=[my_reward],
    train_dataset=ds,
    processing_class=tokenizer,
    peft_config=lora_config,           # ⭐ 直接传入
)
```

⭐ **省显存关键**：7B 模型 + LoRA r=16 在 A100 80G 上轻松跑。

---

## 八、数据集格式

```python
from datasets import Dataset

# 最小格式
ds = Dataset.from_list([
    {"prompt": "What is 2+2?"},
    {"prompt": "What is 3+5?"},
])

# 带 ground_truth
ds = Dataset.from_list([
    {"prompt": "What is 2+2?", "ground_truth": "4"},
    {"prompt": "What is 3+5?", "ground_truth": "8"},
])

# 用 chat template
def format_prompt(example):
    messages = [
        {"role": "system", "content": "You are a math assistant."},
        {"role": "user", "content": example["question"]},
    ]
    example["prompt"] = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return example

ds = ds.map(format_prompt)
```

---

## 九、推理 / 评估

```python
# 训练后保存
trainer.save_model("./final")
tokenizer.save_pretrained("./final")

# 加载（LoRA 用 PeftModel）
from peft import PeftModel
base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-7B", torch_dtype=torch.bfloat16, device_map="auto")
model = PeftModel.from_pretrained(base, "./final")
model = model.merge_and_unload()   # 合并 LoRA 到 base

# 推理
inputs = tokenizer("What is 5+7?", return_tensors='pt').to("cuda")
output = model.generate(**inputs, max_new_tokens=100)
print(tokenizer.decode(output[0], skip_special_tokens=True))
```

---

## 十、常见错误与解决

| 错误 | 原因 | 解决 |
|------|------|------|
| `ValueError: reward_funcs must return List[float]` | reward 返回 tensor / np.array | `[float(x) for x in ...]` |
| `RuntimeError: vLLM colocate ... OOM` | vllm 占比过高 | `vllm_gpu_memory_utilization=0.3` |
| reward 全是 0 | reward_func 内部抛异常被吞 | print 检查 + 加 try/except |
| KL 爆炸（> 1.0） | beta 太小 / lr 太大 | beta=0.1, lr=1e-6 |
| 生成全是重复 | repetition_penalty 没设 | `repetition_penalty=1.1` |
| 训练超慢 | 没开 vLLM | `use_vllm=True` |
| `KeyError: ground_truth` | dataset 字段被 remove | `remove_unused_columns=False` |
| `padding_side` warning | tokenizer 是 right padding | `tokenizer.padding_side = 'left'` |
| Loss is NaN | bf16/fp16 数值溢出 | 用 bf16，不用 fp16 |

---

## 十一、完整 minimal example

```python
import torch
from datasets import Dataset
from transformers import AutoTokenizer
from trl import GRPOConfig, GRPOTrainer
from peft import LoraConfig
import re

# ===== 1. 数据 =====
data = [
    {"prompt": "What is 2+2?", "ground_truth": "4"},
    {"prompt": "What is 5*3?", "ground_truth": "15"},
    {"prompt": "What is 10/2?", "ground_truth": "5"},
] * 100
ds = Dataset.from_list(data)

# ===== 2. tokenizer =====
model_path = "Qwen/Qwen2.5-1.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_path)
tokenizer.padding_side = 'left'
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# ===== 3. reward =====
def correctness_reward(completions, ground_truth=None, **kwargs):
    rewards = []
    for c, gt in zip(completions, ground_truth):
        m = re.search(r'-?\d+', c)
        pred = m.group() if m else ""
        rewards.append(1.0 if pred == str(gt) else 0.0)
    return rewards

# ===== 4. config =====
config = GRPOConfig(
    output_dir="./grpo-math",
    num_train_epochs=1,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    num_generations=4,
    max_prompt_length=128,
    max_completion_length=128,
    learning_rate=5e-6,
    beta=0.04,
    logging_steps=5,
    bf16=True,
    use_vllm=True,
    vllm_mode='colocate',
    vllm_gpu_memory_utilization=0.4,
    remove_unused_columns=False,
)

# ===== 5. LoRA =====
lora = LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM")

# ===== 6. train =====
trainer = GRPOTrainer(
    model=model_path,
    args=config,
    reward_funcs=[correctness_reward],
    train_dataset=ds,
    processing_class=tokenizer,
    peft_config=lora,
)
trainer.train()
trainer.save_model("./final")
```

---

## 十二、log 解读

训练时关键指标：
- `reward` ↑：模型在学
- `kl` 稳定在 0.01-0.1：约束正常
- `kl` ↑↑：beta 不够 / lr 过大 → 调
- `completions/mean_length` 稳定：长度未失控
- `policy_loss` 通常负数（推动概率上升）

判断收敛：
- reward 增长缓慢 → 已收敛 or lr 太低
- reward 上升 + KL 不爆 + 输出可读 = 健康

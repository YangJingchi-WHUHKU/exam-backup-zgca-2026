---
name: rl-bio-design
description: 用 RL（PPO / Best-of-N + SFT）微调一个序列生成模型，让它生成的蛋白/DNA 序列在 frozen reward predictor 上得分更高。当题面同时出现"RL/强化学习/policy/reward"和"蛋白/DNA/序列/enhancer/protein/design"时触发——bio+RL 组合压轴题。
---

# RL 微调生物序列 - 押宝 bio+RL 压轴

## 何时触发

题面**同时**满足两边：

| RL 信号 | 生物信号 |
|---|---|
| RL / 强化学习 | 蛋白 / protein / 氨基酸 |
| PPO / GRPO / RFT | DNA / enhancer / promoter |
| policy / reward / advantage | 序列设计 / sequence design |
| "微调生成模型让它..." | "优化活性 / 提升结合 / 提升表达" |

也包括关键词：DRAKES、TACO、Bio+RL、序列优化、reward-guided generation、protein design with RL。

只有 RL 信号没有生物信号 → 用 `grpo-rl` skill 走 LLM RL 路线。
只有生物信号没有 RL 信号 → 用 `hf-finetune` skill 走标准微调。

## 核心模板

`templates/07_rl_protein_design.py`——含两条路径，CLI 切换：

```bash
# 主路径（更猛但易爆）
python templates/07_rl_protein_design.py --mode ppo --steps 200

# 兜底路径（最稳，2 小时跑得完）
python templates/07_rl_protein_design.py --mode bon --rounds 5 --n_samples 64 --topk 16
```

## 两种实现路径对比

| 维度 | (A) PPO / GRPO | (B) Best-of-N + SFT |
|---|---|---|
| 收敛速度 | 慢 (200+ steps) | 快 (5 rounds 见效) |
| 显存开销 | reward model + policy + value head | 只要 policy + reward inference |
| 稳定性 | KL 容易爆，需要调 beta | 没有 KL 概念，绝对稳 |
| 实现难度 | 高（TRL 接口版本敏感） | 低（就是循环 + SFT） |
| 上限 | 高 (理论最优) | 中 (受 BoN 多样性限制) |
| **考场推荐** | 时间充足且会调 PPO | **默认走这条**（兜底用） |

**决策**：先 `--mode bon` 跑通确保有提交；如果还有时间，再 `--mode ppo` 试一把刷高分。

## Reward 函数设计模式

题目大概率会给一个 frozen predictor（蛋白活性预测器 / DNA enhancer 活性预测器 /
ESM-IF 折叠概率 / 题目自训的 reward model）。

### 模式 1: HF AutoModel 风格的 reward
```python
from transformers import AutoModel, AutoTokenizer
class RewardModel:
    def __init__(self, path):
        self.tok = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(path, trust_remote_code=True).cuda().eval()
        for p in self.model.parameters(): p.requires_grad = False
    @torch.no_grad()
    def score(self, sequences: list[str]) -> torch.Tensor:
        enc = self.tok(sequences, padding=True, return_tensors="pt").to("cuda")
        out = self.model(**enc).last_hidden_state.mean(1)
        return out[:, 0]  # 或自定义 score_head
```

### 模式 2: ESM-style reward (蛋白题常见)
```python
import esm
esm_model, alphabet = esm.pretrained.load_model_and_alphabet_core(name, ckpt, None)
batch_converter = alphabet.get_batch_converter()
# pseudo-likelihood / 题目给的属性预测 head
```

### 模式 3: 多目标加权
如果题面给多个 reward（活性 + 多样性 + 合规性）：
```python
def total_reward(seq):
    r1 = activity_predictor.score(seq)         # 主信号
    r2 = -hamming_to_train(seq) * 0.1          # 鼓励新颖
    r3 = 0.2 if is_valid_alphabet(seq) else 0  # 合规
    return r1 + r2 + r3
```

### Reward 设计反模式 (容易扣分)
- ❌ 把 reward 限制在 [0, 1] 但实际预测器输出 [-10, 10] → 信号被压平
- ❌ 多个 reward 全用同一量级权重 → 主信号被次要信号淹没
- ❌ 不过滤非法序列（字母表外字符）→ reward 模型 OOV，给随机分

模板里的 `extract_sequence()` 已经做了字母表过滤。

## 序列字母表配置 (CHANGE_ME)

```python
ALPHABET_PROTEIN = "ACDEFGHIKLMNPQRSTVWY"  # 20 个标准氨基酸
ALPHABET_DNA = "ACGT"                      # 4 个碱基
ALPHABET = ALPHABET_PROTEIN  # 在 07 模板顶部改
```

模板的 `extract_sequence(generated_text)` 会过滤掉非字母表字符——
这一步**必须做**，否则 reward model 会因为非法字符崩。

## 显存预算 (A100 80G)

| 配置 | 显存 |
|---|---|
| Qwen2.5-0.5B (QLoRA) + reward 100M (frozen) + PPO | ~18 GB |
| Qwen2.5-1.5B (QLoRA) + reward 650M (frozen) + PPO | ~32 GB |
| Qwen2.5-3B (QLoRA)  + reward 1.2B (frozen) + PPO  | ~60 GB（边界，建议 BoN） |
| 同上规模 + Best-of-N + SFT                          | -10 GB（不用 value head） |

OOM 顺序：降 `seq_len` → 降 `batch` → reward model 用 bf16 → 切到 `--mode bon`。

## 评测指标 (会被阅卷人盯）

| 指标 | 怎么算 | 写到 README |
|---|---|---|
| Reward mean 提升曲线 | 每 round/step 的平均 reward | 必须有 |
| Reward top-K 提升 | 每轮 top-16 平均 reward | BoN 模式天然有 |
| 多样性 | top-K 之间的 pairwise Hamming distance | 加分项 |
| Validity | 生成序列符合字母表的比例 | 加分项 |
| KL divergence (PPO only) | 与初始 policy 的 KL | PPO 必须有，证明没 collapse |

模板的 BoN 路径会自动写 `bon_history.json` 含每轮 reward 曲线。

## 现场操作步骤

1. 装包
   ```bash
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
       trl peft accelerate transformers bitsandbytes datasets
   ```
2. 改 CHANGE_ME（07 模板顶部）：
   - `BASE_MODEL_PATH` ← 题目给的生成模型 ckpt
   - `REWARD_MODEL_PATH` ← 题目给的活性预测器
   - `ALPHABET` ← 蛋白选 `ALPHABET_PROTEIN`，DNA 选 `ALPHABET_DNA`
   - `SEQ_LEN` ← 题面要求的序列长度
   - `PROMPT_TEMPLATE` ← 题目给的 prompt 模板（如果有）
   - `RewardModel.score()` ← **最关键的一处**，把题目 predictor 的真实 forward 接进来
3. 先 BoN 跑通：`--mode bon --rounds 2 --n_samples 16 --topk 4` 验证 reward 在涨
4. Scale up：`--rounds 5 --n_samples 64 --topk 16`
5. 时间还多就上 PPO：`--mode ppo --steps 200`

## 高分要点

1. **必须画 reward 曲线**——证明 RL 真的有效。BoN 模板已自动存 `bon_history.json`，
   PPO 看 `train.log` 里的 `reward_mean`。
2. **必须报告多样性**——避免 mode collapse 是 RL bio 的核心难点之一
3. **必须说明 reward 设计**——这是评分大头，README 里写：
   - reward = ? × 活性 + ? × 多样性 + ? × 合规性
   - 为什么这么加权
4. **必须做合法性过滤**——非字母表字符必须删，否则下游崩
5. **报告里写为什么选 BoN 不选 PPO**（或反之）——展示工程判断力

## 常见坑速查

| 坑 | 现象 | 解决 |
|---|---|---|
| reward 全是 0 | 生成的序列全被 OOV 过滤 | 检查 `ALPHABET`、检查 prompt 引导 |
| reward 不涨 | BoN 5 轮还是 plateau | 增大 `n_samples`，提高 temperature |
| KL 爆炸 (PPO) | KL > 10 后 loss 发散 | 降 lr 到 1e-6，提高 beta/kl_coef |
| mode collapse | top-K 序列几乎一样 | 加 diversity reward；降低 SFT epochs |
| TRL PPOTrainer 报错 | 接口在 0.7 / 0.11 / 0.13 完全不同 | 模板里有 try/except，自动降到自写循环；或直接 `--mode bon` |
| reward model OOM | 同时 forward policy + reward | reward 用 bf16，分批 score |

## 备选思路：DRAKES (离散扩散 + reward 反传)

如果题面给的生成模型是**离散扩散模型**（不是自回归 LM），不能直接 PPO：

```python
# 思路：把 reward 当做 guidance, 用 classifier guidance 引导扩散采样
# 或者用 DRAKES 的 differentiable reward backprop
# 参考: refs/DRAKES/
```

这个分支极少见，但如果题面提到 "discrete diffusion" / "MDLM" / "扩散语言模型"
要立刻想到。

## 参考资源 (toolkit 内)

- `templates/07_rl_protein_design.py` - 主模板（PPO + BoN 双路径）
- `templates/05a_grpo_qwen.py` - LLM GRPO 参考（reward 函数写法可借鉴）
- `refs/RLfinetuning_Diffusion_Bioseq/` - 生物序列 RL 综述代码
- `refs/DRAKES/` - 离散扩散 + reward 反传（离散扩散题专用）
- `refs/trl/` - TRL 源码（接口版本差异时查这里）
- `skills/grpo-rl/SKILL.md` - LLM RL 通用指南
- `skills/hf-finetune/SKILL.md` - 生物 backbone 加载坑（reward model 加载会用到）

# 常见坑速查库 — Problem 3 (DNA Enhancer 回归)

> 散经验，密集可秒查。每条 1-3 行。

---

## §1 用户自己总结的经验（原话保留）

- **要跟模型确定清楚用什么激活函数，容易忘记这个** → 训练前必须问清楚 backbone 是 ReLU/GELU/Tanh 哪个，任务头要不要加非线性。

---

## §2 基础确认（每个题做之前都要确认）

- **激活函数**：backbone 内 GELU（Transformer 标配）；回归头**不加非线性**（直接 Linear → 输出）；分类头**也不加**（CrossEntropy 内自带 softmax）。
- **池化方式**：mean pooling（mask-aware 用 attention_mask 加权）/ CLS / last token 三选一，**必须在 README 说明选择**。
- **损失函数**：回归用 MSE（默认）/ MAE（抗 outlier）/ Huber（兼顾）；分类用 CrossEntropy。
- **learning rate**：backbone 冻结时 head LR `3e-4`；解冻 backbone 时整体 LR `3e-5`。

---

## §3 HF 微调专项坑（GENErator / ESM 通用）

- 必须 `trust_remote_code=True`（自研模型自定义代码）。
- `tokenizer.padding_side` 必须设（GENErator/DNA 用 `right`；GRPO/生成用 `left`）。
- `pad_token` 默认没设，必须 `tokenizer.pad_token = tokenizer.eos_token`。
- **GENErator 6-mer tokenizer：序列长度必须是 6 的倍数**，否则产生 OOV → `len_truncated = (len // 6) * 6`。
- `AutoModel` vs `AutoModelForCausalLM`：做特征提取（加自己回归头）用 `AutoModel`；做生成用 `ForCausalLM`。
- 加载 ckpt 用 `torch_dtype=torch.bfloat16` 省一半显存。
- LoRA `target_modules` 因模型架构不同（Qwen/LLaMA/ESM 各不一样）→ 不确定时优先**冻结 backbone + 只训练头**（最稳）；要用 LoRA 时 `r=16` 起步。

---

## §4 显存优化（A100 80G 也可能 OOM）

- **冻结 backbone**：`for p in model.backbone.parameters(): p.requires_grad = False` → 省 60%+ 显存。
- `torch.no_grad()` 包住 frozen backbone 的 forward → 省一份梯度内存。
- **AMP bf16**：`with torch.amp.autocast('cuda', dtype=torch.bfloat16)` → 省一半。
- **gradient checkpointing**：长序列必开（牺牲速度换显存）。
- `batch_size` 太大就降到 4 或 2，加 `grad_accumulation_steps` 补回去。

---

## §5 训练循环易错

- 忘记 `optimizer.zero_grad()` → 梯度累积导致 explode。
- 忘记 `model.eval()` 切验证模式 → BN/Dropout 还在训练态。
- **warmup 步数太少** → 1.2B 大模型容易爆炸（`warmup_ratio = 0.05` 起步）。
- **early stopping 触发**：连续 3 epoch val 不涨就停（不是 1 个）。
- `best_metric_higher_better=True` 对 Pearson；`False` 对 loss。

---

## §6 提交格式坑（每年都有人在这扣分）

- **`test_result` 单数，不是 `test_results`**（2024 秋蛋白题历史经验）。
- **CSV 表头不带空格**：`label1,label2` 不是 `label1, label2`。
- **顺序必须与 test 集严格一致**：不要自己 shuffle 或排序。
- **整数 vs 字符串**：`pred_label` 是 `int`，不是 `"1"`。
- **README 必须有**：任务描述 / 模型设计 / 超参 / 结果 / 复现步骤 五段。
- **提交文件命名必须严格按题面**：如题面要 `test_output.csv` 就不要写 `submission.csv` 或 `result.csv`，每年都有人在这扣分

---

## §7 评测指标自检

- **Pearson 手写公式**（不依赖 scipy）防止环境问题。
- **双头任务两维分别算 Pearson**，最后报两个数。
- **NaN 检查**：`np.isnan(preds).any()` 一定要先做。
- 如果 Pearson < 0.1 → 几乎肯定是 head 接错了或者 label 标准化出问题。
- **label 标准化检查**：Pearson 对量纲不敏感，但 MSE loss 对量纲极敏感。先看 label 分布——如果 dev/hk 两维量纲差 >10 倍，必须 z-score 标准化（fit train，transform val/test），否则一个维度 dominate 训练。提交时记得**反标准化**回原量纲。

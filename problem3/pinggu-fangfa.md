# 评估方法模板 · A-E 五阶段

> 用于第三题（DNA enhancer 活性回归），同样适用于其他题目。
> 本文件是**通用评估模板** + **第三题实例化示例**。

---

## §0 核心准则

> **🔴 评估的不是代码而是目的。**
>
> 代码能跑 ≠ 概念成功。loss 在降 ≠ 真的学到。
> 每一阶段都必须用"概念是否达成"作判据，不能用"代码是否跑得动"作判据。

### 反面案例：smoke test 假象

| 现象 | 错觉 | 真相 |
|------|------|------|
| 训了 5 epoch，loss 从 2.0 降到 0.5 | "在收敛，继续训" | val Pearson 还是 0.1 → 立即停 |
| MSE 持续下降 | "在学" | 模型可能学会"全输出 0"也能让 MSE 假降 |
| 训练 acc 99% | "学会了" | val acc 还是 50% → 过拟合，不是学会 |

**口诀**：loss 降 ≠ 概念成功。一旦概念判据不达标，**立即停**，不要硬调超参试图把数值搞上去。

---

## §1 旧思路 vs 新思路

| 维度 | 旧思路（错） | 新思路（对） |
|------|--------------|--------------|
| 评估对象 | 代码能跑、loss 在降 | 每个**概念阶段**是否成功 |
| 判据 | "loss < X" | "val Pearson > 0.4 + train/val gap < 0.1" |
| 失败检测 | 跑完看结果 | 每阶段独立判据，失败立即停 |
| 跟评分关系 | 模糊 | 每阶段判据直接映射到评分细则 |
| 修复方式 | 调超参再试一次 | 先查"是哪个阶段的判据被跳过了" |

---

## §2 A-E 五阶段模板（核心）

每个阶段必须写明 5 个字段：**在干嘛 / 输入 / 输出 / 评估什么概念 / 数值判据**。

| 阶段 | 在干嘛 | 输入 | 输出 | 评估什么概念 | 数值判据 |
|------|--------|------|------|--------------|----------|
| **A 数据** | 把官方数据集变成可训练的 batch | 原始 lmdb / HF dataset 路径 | DataLoader 能 yield 出 batch | 数据用对了吗？分布对吗？标签对吗？ | 抽 5 个样本人工目检 + label 分布直方图 |
| **B 模型** | 把 backbone + 任务头搭起来 | backbone ckpt 路径、任务头配置 | 模型能 forward 出预期 shape | 容量够吗？没接错头吗？冻结对了吗？ | dummy input forward 输出 shape 对 + 可训练参数数量 = 预期 |
| **C 训练** | 在训练集上跑 SGD 优化 | 模型、DataLoader、optim、loss | best checkpoint | 真学到了吗？还是只在过拟合 train？ | val 指标 vs train 指标差距 < 阈值 + val 指标随 epoch 单调上升 |
| **D 推理** | 用 best ckpt 在 test 集上输出预测 | best ckpt、test DataLoader | test_output.csv | 预测分布合理吗？没崩没爆吗？ | 预测值分布 vs label 分布对齐 + 没有 NaN/Inf + 顺序与测试集严格一致 |
| **E 评分** | 算最终指标 | test_output.csv、官方评测脚本 | 单个数值（Pearson） | 是不是真的解决了题目要求？ | 数值 > 题目最低预期门槛（参考往年） |

### 阶段之间的关系

```
A 数据 → B 模型 → C 训练 → D 推理 → E 评分
  ↓        ↓        ↓        ↓        ↓
判据A    判据B    判据C    判据D    判据E
  └────────┴────────┴────────┴────────┘
        任何一阶段判据失败 → 立即停
```

---

## §3 四条强制要求

### ① 判据必须直接对应"概念成功"，不能只是 loss 降

| 错的判据 | 对的判据 |
|---------|---------|
| "loss 从 2.0 降到 0.5" | "val Pearson > 0.5 且 train/val gap < 0.1" |
| "MSE < 0.3" | "预测分布 vs label 分布的 quantile error < 30%" |
| "模型 forward 不报错" | "dummy input forward 输出 shape = [B, 2] 且无 NaN" |

### ② 必须包含"反假信号"判据

每阶段写一条"如果出现 X 就说明评估系统被骗了"。

| 阶段 | 反假信号示例 |
|------|--------------|
| A | 所有标签都一样 / 大部分序列长度异常 / 字符集有 N 之外的字符 |
| B | 可训练参数数 = 0（全冻结了）或 = 全模型（没冻结）|
| C | train loss 在降但 val loss 在涨（过拟合）/ train loss = val loss 完全一致（数据泄漏）|
| D | 所有预测都是同一个值（model collapse，但 MSE 看起来还可以）/ 输出顺序乱了 |
| E | Pearson 看起来 OK 但散点图全在一条水平线上（说明只是预测了均值）|

### ③ 失败立即停 + 复盘"评估体系为什么没拦住"

不要硬调超参试图把数值搞上去。先问三个问题：

1. 是哪个阶段的判据被跳过了？
2. 为什么我们的评估没拦住这个失败？
3. 评估体系本身要不要补一条判据？

把这三个问题的答案写到 `fail-fupan.md`。

### ④ 题目评分细则每一项都要能映射到某阶段判据

| 题目要求 | 映射到的阶段判据 |
|---------|------------------|
| 双维 Pearson 都达标 | E 阶段判据分别算 Pearson_dev 和 Pearson_hk |
| 完整 train.log | C 阶段判据检查 log 完整性（每 epoch 都有 val 指标）|
| test_output.csv 顺序对 | D 阶段判据检查行号 = 测试集 index |
| 复现脚本可一键跑 | E 阶段判据：从 zero 开始跑 `bash reproduce.sh` 能产出同样的 csv |

---

## §4 smoke test 强制规则

### 触发条件

任何时间花费 > 10 分钟的训练或代码运行**之前**，必须先 smoke test。

### smoke test 规格

| 字段 | 要求 |
|------|------|
| 耗时 | ≤ 1 分钟 |
| 样本量 | ≤ 10 个 |
| epoch | 1 |
| 目的 | 排除"代码崩"，不是验证"能学会" |

### smoke test 判据

1. 能跑完不报错
2. loss 在动（不是 NaN，不是恒 0）
3. 输出 shape 对

### 注意

- smoke test 通过 ≠ 真训练能成功
- smoke test 只能排除"代码崩"，不能证明"评估成功"
- 每次 smoke test 写一行结果到 `smoke-test.md`（拼音命名）

格式示例：

```
2026-05-23 14:30 | A 数据 | 10 样本 | PASS | label 分布: dev mean=2.3, hk mean=1.8
2026-05-23 14:35 | B 模型 | dummy input | PASS | 输出 shape=[2,2], 可训练参数=1538
2026-05-23 14:42 | C 训练 | 10 样本 1 epoch | PASS | loss 2.1 → 1.7
```

---

## §5 第三题（DNA enhancer 回归）实例化

题目背景：用 GENErator-v2 backbone 做 DeepSTARR enhancer 活性回归，双头输出 (dev, hk) 两个值，用 MSE 训练，用 Pearson 评测。

| 阶段 | 在干嘛 | 输入 | 输出 | 评估什么概念 | 数值判据 |
|------|--------|------|------|--------------|----------|
| **A** | 加载 DeepSTARR | `/vepfs-readonly/problem3/hf_downloads/DeepSTARR_enhancer2` | DataLoader | DNA 序列里只有 ACGT；序列长度 **必须等于 249bp**（DeepSTARR 固定长度，249 = 6×41+3，所以前置截到 246bp 才能 6-mer 对齐）；label 是 2 维 float | 抽 5 条序列检查字符集 ⊆ {A,C,G,T} + **所有序列长度 == 249bp（不等就 FAIL）** + label 2 维分布（dev/hk 各自 mean、std，**std > 0.1 才算正常**）|
| **B** | GENErator-v2 + 回归头 | `/vepfs-readonly/problem3/hf_downloads/GENErator_v2_eukaryote` | DNARegressor 模型 | 冻结 backbone 对了；回归头 `Linear(hidden, 2)` 接对了；`trust_remote_code=True` 加载成功 | dummy seq forward 输出 shape `[B, 2]`；只有回归头可训练（~1500 个参数，等于 `hidden_dim * 2 + 2`）|
| **C0** | **容量自检（强制前置）** | 100 个训练样本 + B 的模型 | overfit run | 模型有没有能力学到这种映射？ | 在这 100 样本上跑 20 epoch，**train Pearson_dev > 0.9 AND Pearson_hk > 0.9**。过不了 = 模型/池化/lr 设计有问题，**禁止进 C 阶段全量训练** |
| **C** | 训练 backbone 冻结的回归头 | A 的 DataLoader + B 的模型 + AdamW + warmup | best.pt | val Pearson 在涨 + train/val gap < 0.1 | val Pearson_dev > 0.4 **AND** val Pearson_hk > 0.4 + 每个 epoch 单调上升（允许 1 个 epoch 抖动）|
| **D** | test 集推理写 csv | best.pt + test_loader | test_output.csv | 顺序对 + 没 NaN + 预测分布对齐 train label | 行数 = test 集大小、列 = `label1,label2`（**严格无空格**）、无 NaN/Inf、**用 sequence_id 列做主键校验：csv 第 i 行 ↔ test 集第 i 条 sequence_id（dataloader 必须 shuffle=False 且 drop_last=False）**、预测值分位数（10/50/90 分位）vs train label 分位数误差 < 30% |
| **E** | 评分 | test_output.csv（明天监考会用官方评测脚本）| 两个 Pearson | 双维 Pearson 都达标 | **硬阈值：Pearson_dev ≥ 0.4 AND Pearson_hk ≥ 0.4（拿基本分）；目标：≥ 0.55（拿大部分分）；上限：~0.6（DeepSTARR 原论文 CNN baseline）** |

### 每阶段反假信号（第三题专用）

| 阶段 | 反假信号（出现就说明评估被骗了）|
|------|--------------------------------|
| **A** | 序列里出现非 ACGT 字符（如 N），但代码没报错 → tokenizer 在静默 fallback，标签也可能错位 |
| **A** | label 标准差接近 0 → 数据集加载错了，可能只加载到一个常数列 |
| **B** | 可训练参数 = 全模型总参数 → backbone 没冻结，会爆显存或训出垃圾 |
| **B** | 可训练参数 = 0 → 回归头也被冻了，根本没东西在学 |
| **C** | train loss 在降但 val Pearson 一直在 0 附近 → 模型在背训练集，没学到泛化特征 |
| **C** | train Pearson = val Pearson 完全一致 → 训练集和验证集划分错了，有泄漏 |
| **D** | 预测的 2 维列方差接近 0（所有预测都是同一个值）→ model collapse，MSE 可能看起来还行但 Pearson 必然 0 |
| **D** | test_output.csv 行数 ≠ test 集大小 → 推理时 drop_last=True 或者 batch 顺序乱了 |
| **E** | Pearson 看起来 OK（>0.3）但 dev 和 hk 的预测值高度相关（如 corr>0.95）→ 两个头没真正分化，可能只是预测了同一个东西的微扰 |

### 第三题评分细则 → 阶段判据映射

| 评分细则 | 映射到 |
|---------|--------|
| 双维 Pearson（dev + hk）| E 阶段分别算两个值 |
| test_output.csv 格式正确 | D 阶段检查列名、行数、无 NaN |
| 训练日志完整 | C 阶段每个 epoch 写 train/val 指标 |
| 复现脚本能一键跑 | E 阶段：`bash reproduce.sh` 从 zero 产出同样 csv |
| backbone 冻结策略 | B 阶段可训练参数数量判据 |

---

## §6 评估流程的工作方式

### 正常流程

1. 进入某阶段 → 看本文件该阶段的"数值判据"
2. 做完 → 跑判据 → 写一行结果到 `pinggu-jieguo.md`（拼音命名）
3. 判据 PASS → 进入下一阶段
4. 判据 FAIL → **立即停**，写 `fail-fupan.md`

### 失败次数硬上限（重要）

- **同一阶段 FAIL 连续 ≥ 2 次 → 禁止再调超参试图把数值搞上去**
- 必须做以下之一：(a) 改评估体系（新增判据/换判据） (b) 换技术路线（如换池化方式、换 head 结构、换冻结策略）
- **为什么**：连续 2 次同阶段失败，说明问题在评估方法或技术路线，不在参数。继续调超参 = 浪费考场时间 + 心态炸

### `pinggu-jieguo.md` 格式

```
2026-05-23 15:00 | A 数据 | PASS | 序列字符集=ACGT, 长度=249bp, label dev μ=2.1 σ=1.3, hk μ=1.7 σ=1.1
2026-05-23 15:20 | B 模型 | PASS | dummy forward shape=[4,2], 可训练参数=1538, backbone 已冻结
2026-05-23 16:30 | C 训练 | FAIL | val Pearson_dev=0.32 < 0.4 → 见 fail-fupan.md
```

### `fail-fupan.md` 必填三问

1. **是哪个阶段的判据没过？** 例：C 阶段 val Pearson_dev = 0.32 < 0.4
2. **为什么我们的评估没拦住这个失败？**
   - 是 smoke test 没覆盖到？
   - 是判据数值定得太宽松？
   - 是上游阶段（如 A 数据）有隐患没被发现？
3. **评估体系本身要不要补一条判据？**
   - 例：补一条"训练前先在 100 样本上过拟合，必须 train Pearson > 0.9"，否则说明模型容量或学习率有问题

### 严格禁止

- ❌ "再试一次"或"调下参数试试" → 这是把评估变成猜谜
- ❌ 把 FAIL 直接当 PASS 进下一阶段
- ❌ 跳过 smoke test 直接跑长训练
- ❌ 阶段判据写成"loss < X"而不是"概念成功"

---

## §7 文件清单（拼音命名）

| 文件 | 用途 |
|------|------|
| `pinggu-fangfa.md` | 本文件，方法模板 |
| `pinggu-jieguo.md` | 每阶段评估结果，一行一条 |
| `smoke-test.md` | 每次 smoke test 记录 |
| `fail-fupan.md` | 阶段判据失败时的复盘 |

---

## §8 速查卡（开训练前对照）

```
□ 我现在在哪个阶段？(A/B/C/D/E)
□ 这个阶段的"概念成功"是什么？(不是 loss，不是"代码不报错")
□ 数值判据是什么？(具体数字，不是"差不多就行")
□ 反假信号是什么？(出现什么现象就说明被骗了)
□ smoke test 跑过没？(>10 分钟运行前必须)
□ 上一阶段的判据真的 PASS 了吗？(看 pinggu-jieguo.md)
```

任何一项答不上来 → **立即停**，回本文件对照。

---

*最后更新：2026-05-23 · 用于中关村学院夏令营 problem3 DNA enhancer 回归题*

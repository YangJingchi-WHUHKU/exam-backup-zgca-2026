# Claude 开工指南 — 中关村学院科研实训

> 你（Claude）刚被启动在联想 Linux 笔记本上，正在协助杨镜池完成中关村学院夏令营**科研实训**任务。
> 这份文档让你**立即进入状态**。

---

## 🎯 你的任务（一句话）

帮杨镜池在 **2026-05-25 全天（约 9:00-17:00）** 完成 **4 道 ML 实战大题**。每题约 5 小时窗口，框架代码会给，**只需补全核心函数**。

---

## 👤 杨镜池是谁

- **法学研究者 + AI 开发者**（武大法学 A+，GPA 3.91，2 篇 ACL 在投）
- **数学/线代/PyTorch 基础已打**（详见 ~/Documents/Obsidian Vault/中关村学院备考/）
- **中文优先，代码注释英文**
- 偏好直接给可运行代码，**不要 placeholder**

---

## 📚 你必须先读的文档（按优先级）

| 优先级 | 文件 | 路径（如不在请用 find） |
|---|---|---|
| ⭐⭐⭐ | **科研实训四范式速查** | `03_考试用claude.md`（这份文档同目录） |
| ⭐⭐ | 全局指令 + Karpathy 4 原则 | `~/.claude/CLAUDE.md` |
| ⭐ | 备考脉络 | `~/Documents/Obsidian Vault/中关村学院备考/` |

**读完 03_考试用claude.md 就基本进入状态了**。

---

## 🧠 出题规律（必须记住）

冬季营 4 道题对应 **4 大 AI 范式**：

1. **Flow Matching**（2D 点云生成建模）
2. **VQ-VAE + Transformer**（CIFAR-10 离散自回归）
3. **HuggingFace 微调**（ESM / GENErator-v2 + 回归头）
4. **Agentic RAG**（多跳推理问答）

**夏季营高概率方向**：
- Flow Matching 升级版（条件生成 / 高维）
- **LLM 微调（LoRA / QLoRA）**
- Agent + Tool Use 升级版

**风格**：选最前沿概念，但只考最直白实现。**README 的 trade-off 解释也算分**。

---

## ⚙️ 工程约束

- 学院发的笔记本走 SSH 连到**开发机（1×A100 80G）**
- 不能上外网，能用国内 AI
- 32 次有效提交机制
- 4 道题独立计分

---

## 🚀 开工流程建议

### 第一阶段：环境检查（5 分钟）
```bash
# GPU
nvidia-smi
# Python / PyTorch
python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# HuggingFace
python3 -c "import transformers; print(transformers.__version__)"
# 工作目录
pwd && ls
```

### 第二阶段：拿到 4 道题题面（5 分钟）
- 杨镜池会把 4 题 PDF 或文本贴给你
- **完整粘贴**，不要凭片段猜
- 你用 `pdf-reader-pro` skill 解析 PDF

### 第三阶段：4 题排序（10 分钟）
建议优先级（**和你的速查文档一致**）：
1. 9:00-12:00：第 1、2 题（签到 + 中档）
2. 13:00-15:30：第 3 题（微调 / RAG 费时）
3. 15:30-16:30：第 4 题 + README
4. 16:30-17:00：检查 + 提交

### 第四阶段：开干
每道题流程：
1. **读题**：理解输入/输出/评测指标
2. **看框架代码**：用 `investigate` skill 摸清结构
3. **补全核心函数**：参考 03_考试用claude.md 里对应范式的代码骨架
4. **跑通 baseline**：保证不报错
5. **优化加分项**（时间够时）
6. **写 README**：方法选择 + 关键超参 + 结果 + trade-off 解释

---

## 🎯 关键工作模式

### Karpathy 4 原则（已在 ~/.claude/CLAUDE.md）
1. **Think Before Coding** — 别假设，浮现 trade-off
2. **Simplicity First** — 最少代码解决问题
3. **Surgical Changes** — 只动必须动的
4. **Goal-Driven Execution** — 定义可验证成功

### 何时主动 brainstorm（用 brainstorming skill）
- 大块任务前（>50 行代码 / 多文件改动）
- 用户说"讨论一下"/"先想想"
- **小改动 / 明确 bug 不要触发**

### 何时 cross-verify（4 个 channel 互查）
- 关键架构决策
- 复杂 bug 诊断陷入僵局
- 用户明确说"交叉验证"

---

## 🛠️ 你能用的 Skill（34 个）

核心组：
- **pdf-reader-pro**：解析题面 PDF
- **planning-with-files**：4 题大规划
- **systematic-debugging**：PyTorch / CUDA 错误排查
- **verification-before-completion**：提交前强制验证
- **investigate**：摸清框架代码
- **code-review-skill**：14000 行 17 语言专业 review
- **brainstorming**：大块任务前讨论
- **huggingface-llm-trainer**：HF 微调主力
- **experiment-plan / run-experiment / monitor-experiment / analyze-results**：实验全流程
- **plotting-agent**：训练曲线 / 可视化

完整清单在 `01_SKILLS_清单与推荐.md`。

---

## 🚫 你不应该做的事

- 不要主动改 ~/.bashrc 或全局配置（除非杨明确要求）
- 不要把所有 channel 的 API key 写进任何 commit
- 不要因为"题目简单"就跳过 brainstorm（如果是大块任务）
- 不要在提交前自称"完成"，必须验证（verification-before-completion）
- 不要把训练大文件 commit 进 git

---

## 📞 通讯方式

- 杨镜池**优先用中文**和你交流
- 紧急时他会直接打断你
- 你回复**简短、结论先行、不要客套话**
- 卡住超过 15 分钟主动说"我卡这了，要不要换思路 / cross-verify"

---

## 🎬 现在开始

如果是第一次启动，**第一句话告诉杨镜池**：

> "我看完开工指南了，已经清楚你是杨镜池，今天科研实训 4 题。题面准备好了发我，我先用 pdf-reader-pro 解析，然后规划 4 题攻坚顺序。"

如果已经看过，直接接需求。

---

*文档维护：Claude 启动时必读*
*最后更新：2026-05-23*

---
name: cross-verify
description: Automated multi-model cross-verification. This skill should be used when the user says 'cross verify', '交叉验证', '多模型验证', '让其他模型看看', '验证一下', or when critical business logic, architecture decisions, complex bug diagnosis needs independent verification from multiple AI models.
---

# Cross-Verify — 自动交叉验证

## Purpose

将同一问题/代码并行发给多个 AI 模型，收集各自独立回答，自动合成对比分析报告。

## When to Trigger

仅在用户明确要求时执行：
- 用户说 "交叉验证" / "cross verify" / "多模型验证"

可以主动建议（但不自动执行）的场景：
- 关键业务逻辑实现完成后
- 架构设计有重大分歧时
- 复杂 bug 诊断陷入僵局时

建议格式：`"这个逻辑比较关键，要不要跑一下交叉验证？"`，等用户确认再执行。

## How to Execute

在会话中通过 Bash 工具调用脚本：

```bash
bash ~/.config/agents/skills/cross-verify/scripts/cross-verify.sh "问题内容" --models duck,codex,ccodex,minimax,niu
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 第一个参数 | 问题/prompt（必填） | — |
| `--models` | 参与模型，逗号分隔 | `duck,codex` |
| `--context` | 附加上下文文件路径 | — |
| `--budget` | 每个模型最大花费（USD） | `0.5` |

### 用法示例

```bash
# 默认两模型（duck + codex）
bash ~/.config/agents/skills/cross-verify/scripts/cross-verify.sh "这段排序算法对吗？"

# 指定模型
bash ~/.config/agents/skills/cross-verify/scripts/cross-verify.sh "架构设计有什么问题？" --models duck,ccodex,minimax

# 附加代码文件作为上下文
bash ~/.config/agents/skills/cross-verify/scripts/cross-verify.sh "review安全性" --context src/auth.py

# 全量五模型验证
bash ~/.config/agents/skills/cross-verify/scripts/cross-verify.sh "问题" --models duck,codex,ccodex,minimax,niu
```

## 执行流程

1. 并行调用所有指定模型（通过 `-p` 非交互模式 / `codex exec`）
2. 收集各模型原始回答
3. 自动调用 Claude 对所有回答做对比分析
4. 生成最终报告

## 输出位置

所有文件保存在当前工作目录下的 `cross-verify-YYYYMMDD-HHMMSS/` 文件夹中：

```
./cross-verify-20260307-193804/
├── report.md           ← 最终报告（唯一需要看的文件）
├── _raw_responses.md   ← 各模型原始回答汇总（内部用）
├── duck.txt            ← Duck 原始输出
├── codex.txt           ← Codex 原始输出
├── ccodex.txt          ← Claude Codex 原始输出
├── minimax.txt         ← MiniMax 原始输出
└── niu.txt             ← NIU 原始输出
```

## report.md 内容结构

```markdown
# 交叉验证报告
时间: 2026-03-07 19:38:30
参与模型: duck,codex,ccodex,minimax,niu

## 原始问题
（用户提出的问题）

## 各模型回答摘要
（每个模型 1-2 句话概括核心观点）

## 共识
（所有模型一致同意的部分）

## 分歧
（模型之间不同的观点，表格标注谁持什么观点）

## 最终结论
（综合所有模型分析，给出最可靠的结论）

## 可信度评估
（高/中/低，附理由）

---
（附：各模型完整原始回答）
```

## Available Models

| ID | CLI | Backend |
|----|-----|---------|
| duck | Claude Duck (~/.claude_duck/) | Anthropic |
| codex | Codex CLI (codex exec) | OpenAI |
| ccodex | Claude Codex (~/.claude_codex/) | Anthropic |
| minimax | Claude MiniMax (~/.claude_minimax/) | MiniMax |
| niu | Claude NIU (~/.claude_niu/) | Anthropic |

## Cost Control

默认每个模型每次调用上限 $0.5 USD，通过 `--budget` 调整。五模型全量验证一次约 $2-3。

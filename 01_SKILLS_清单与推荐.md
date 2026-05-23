# SKILLS 最终清单（34 个）

> 最后修订：2026-05-23
> 经多轮筛选 + 社区调研后定稿。每个 skill 都验证过与本地其他 skill 不冲突。

---

## 一、本地原版精选（30 个）

### S 级 必带（8 个，去掉 exam-day-doc-builder）
```
pdf-reader-pro           planning-with-files      systematic-debugging
verification-before-completion    investigate    session-end
neat-freak               skill-finder
```

### 实验全流程（5 个）
```
experiment-plan          experiment-bridge        run-experiment
monitor-experiment       analyze-results
```

### 文档输出（5 个，含 pptx）
```
pdf  docx  xlsx  pptx  html-report-generator
```

### 表达辅助（4 个）
```
mermaid-diagram          graphviz-dot-generator
formula-derivation       plotting-agent
```

### 用户点名 B 级（4 个）
```
skill-creator            experience-evolution
training-check           skill-manager
```

### 改造后的 cross-verify（1 个）
默认 models 已改为 `aipai,micu,codesuc,swarm`

### 远程 GPU（3 个）
```
vast-gpu                 serverless-modal         tmux-coding-agent
```

---

## 二、社区调研新增（4 个）

| Skill | 来源 | 用途 |
|---|---|---|
| **brainstorming** | obra/superpowers | 大块任务前讨论方案；描述已改软，避免误触发 |
| **huggingface-llm-trainer** | huggingface/skills | HF 官方微调 skill（SFT/DPO/LoRA），直接命中冬季营 ESM/GENErator 题型 |
| **hf-cli** | huggingface/skills | HF Hub 下模型 / 上传 / 管理 |
| **code-review-skill** | awesome-skills/code-review-skill | **替换本地 code-review**；14000+ 行 17 语言专业 review，4 阶段流程 + 5 级严重度 |

---

## 三、移除（1 个）

- ❌ `code-review` （本地版） → 被 awesome-skills/code-review-skill 替换
- ❌ `exam-day-doc-builder` （备考已结束）
- ❌ `case-coding`（法学项目，与考试无关）

---

## 四、合并到 CLAUDE.md（非 skill）

- ✅ **Karpathy 4 原则**（Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution）
  - 已合并到 `configs/CLAUDE.md`
  - 来源：multica-ai/andrej-karpathy-skills

---

## 五、社区调研评估弃用清单

| 候选 | 弃用理由 |
|---|---|
| levnikolaevich/claude-code-skills | 多模型审查需 OpenAI Codex auth，考场环境不可用 |
| obra/superpowers 全套（除 brainstorming）| systematic-debugging / writing-plans / code-review 等与本地版重叠会冲突 |
| ericporres/llm-coding-workflow-skill | 5 阶段 cycle 与 brainstorming 重叠 |
| scottd3v/Brainstorming gist | obra/superpowers brainstorming 的简化版，重复 |

---

## 六、最终目录结构

`skills_全量备份/` 34 个 skill 已准备就绪，`install_skills.sh` 自动铺到 `~/.config/agents/skills/` + 软链 `~/.claude/skills/`。


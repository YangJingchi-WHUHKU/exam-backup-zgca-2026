---
name: exam-router
description: 中关村学院科研实训题面识别与路由。读到 /vepfs-readonly/problemN/ 目录或题面 PDF 时触发，自动判断属于哪个范式（生成建模/离散自回归/预训练微调/RAG/RL）并指向 toolkit 里对应的 template + skill。
---

# Exam Router - 题面识别入口

## 触发条件
用户出现以下任一情况：
- 提到 `/vepfs-readonly/problem` / `/vepfs/problem`
- 提到 "科研实训"、"4 道题"、"提交 json/csv"、"A100"
- 把题面 PDF 或题面文本贴进来
- 说 "我现在在考场" / "开始做第 N 题"

## 路由决策树

按关键词扫描题面，命中即跳转对应 skill：

| 题面关键词 | 范式 | 调用 skill | 模板文件 |
|---|---|---|---|
| `Flow Matching`、`速度场`、`Chamfer`、`Z→G→C`、`2D 分布`、`插值` | 生成建模 (Flow) | `flow-matching` | `templates/01_flow_matching_zgc.py` |
| `VQ-VAE`、`codebook`、`token`、`自回归 Transformer`、`CIFAR`、`图像补全`、`FID` | 离散+AR | `vqvae-ar` | `templates/02a_vqvae_cifar.py` + `02b_vqvae_prior_transformer.py` |
| `ESM`、`蛋白`、`氨基酸序列`、`alphabet`、`batch_converter`、`溶解性`、`分类` | 蛋白微调 | `hf-finetune` | `templates/03_protein_esm_finetune.py` |
| `GENErator`、`DNA`、`A/C/G/T`、`enhancer`、`activity`、`Pearson`、`6-mer` | DNA 微调 | `hf-finetune` | `templates/04_dna_genErator_regression.py` |
| `Agentic RAG`、`多跳`、`BM25`、`FAISS`、`Qwen3-14B`、`vLLM`、`74000 文档` | RAG | `agentic-rag` | `templates/08_agentic_rag_qwen.py` |
| `GRPO`、`DPO`、`PPO`、`RLHF`、`reward`、`奖励函数`、`可验证奖励`、`policy` | LLM RL | `grpo-rl` | `templates/05a_grpo_qwen.py` |
| `DDPO`、`扩散模型 + 奖励`、`aesthetic`、`compressibility`、`图像 RL` | 图像 RL | `ddpo-image` | `templates/06_ddpo_diffusion.py` |
| `RL 微调 DNA/蛋白/序列`、`enhancer 设计`、`DRAKES`、`reward model` | 生物 RL | `rl-bio-design` | `templates/07_rl_protein_design.py` |

## 工作流（每题都走这套）

进考场后对每题做：

1. **读题（5 分钟）**：把题面快速浏览一遍，找上面表格的关键词
2. **路由**：判断范式 → 调用对应 skill → 打开对应 template
3. **环境**：`bash /vepfs/<user>/toolkit/02-pip-install.sh <题号>`
4. **改 CHANGE_ME**：每个 template 顶部有 CHANGE_ME 清单，逐条填空
   - 模型路径 → 题目给的 `/vepfs-readonly/.../ckpt`
   - dataset 加载 → 题目给的接口
   - 提交路径 → 题目要求的 `/vepfs/problemN/...`
5. **跑通**：先用极小 batch + 几步训练验证全流程，再 scale up
6. **提交**：调用 `skills/submission/` 检查格式

## 时间分配（8 小时考试，4 题，做 2-3 题）

| 阶段 | 时间 | 内容 |
|---|---|---|
| 通读 + 决策 | 0:00-0:30 | 看完 4 题，选 2-3 题主攻，剩下的占坑 |
| 题 1 | 0:30-2:30 | 最稳的一题（通常是 HF 微调） |
| 题 2 | 2:30-4:30 | 第二稳的题 |
| 午餐 + 喘 | 4:30-5:00 | |
| 题 3 | 5:00-6:30 | 第三题或回去优化前两题 |
| 收尾 | 6:30-8:00 | 检查提交格式、写 README、上传 train.log |

## 必读资源（toolkit 内）

- `cheatsheet/04-科研实训指南.md` - 完整考场规则
- `cheatsheet/提交格式速查.md` - 所有题型的提交格式
- `cheatsheet/A100-显存速查.md` - 各模型显存预算
- `cheatsheet/国内镜像配置.md` - HF/PyPI 国内镜像 ENV

## 兜底规则

- **无论用什么 AI 客户端**：所有 template 都能直接 `python xxx.py` 运行，不依赖 skill 系统
- **如果 skill 没被加载**：手动读 `templates/0N_xxx.py` 顶部的 docstring，同样有完整说明
- **如果某个库装不上**：去 `refs/` 找对应源码，`pip install -e refs/<repo>/`

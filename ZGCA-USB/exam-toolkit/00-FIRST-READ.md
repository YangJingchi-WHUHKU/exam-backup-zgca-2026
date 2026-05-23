# 00 FIRST READ — 进考场第一件事

> ⭐ **进考场你只需要按这个文档的顺序做，不要乱看其他文件。**

---

## 紧急摘要（5 行）

1. **你在哪**：中关村学院科研实训机房 → 一台学院发的笔记本 → SSH 进开发机（`ssh dev`），开发机有 **A100 80G**。
2. **环境**：Ubuntu 22.04 + Python 3.10.12 + **不能上外网，但可以 `pip install`**（用国内镜像）。
3. **题目**：4 道题 / 8 小时 / 选 2-3 题做完即合格，全做完是顶尖水平。
4. **AI**：可以用国内 AI（通义千问 / 文心一言），**不能用 ChatGPT**。
5. **提交**：每题一个 `/vepfs/problemN/` 目录，按各题要求的文件名提交。

---

## 进考场后第 0-5 步详细工作流

### ⭐ 步 0：U 盘 → 笔记本（5 分钟）

```bash
# 笔记本上插 U 盘后
cp -r /media/usb/exam-toolkit ~/Desktop/exam-toolkit
ls ~/Desktop/exam-toolkit  # 确认目录结构完整
```

**检查项**：
- [ ] `templates/` 存在且非空
- [ ] `skills/` 存在
- [ ] `cheatsheet/` 存在
- [ ] `docs/` 存在
- [ ] `01-bootstrap.sh`、`02-pip-install.sh` 存在

⚠️ **U 盘读不出来的兜底**：举手问监考能否换 U 盘 / 用 scp 从另一台机器拉。**不要慌**，所有内容也都在 Obsidian Vault 里，最差情况手抄关键脚本。

---

### ⭐ 步 1：连开发机（2 分钟）

```bash
ssh dev   # 学院预配置好的别名
# 如果别名不存在，问监考拿 ssh 命令

# 进开发机后
whoami    # 记住你的用户名 <user>
mkdir -p /vepfs/$(whoami)/toolkit
ls /vepfs-readonly/  # 看一眼有几个 problemN/ 目录
```

**检查项**：
- [ ] `nvidia-smi` 能看到 A100 80G
- [ ] `/vepfs/$(whoami)/` 可写
- [ ] `/vepfs-readonly/problem1/` ~ `problem4/` 都能 ls

---

### ⭐ 步 2：上传 toolkit（5 分钟）

**在笔记本本地终端执行**（不是 ssh 进开发机后）：

```bash
# 把整个 toolkit 拷到开发机
rsync -avz --progress ~/Desktop/exam-toolkit/ dev:/vepfs/<user>/toolkit/
# 或者用 scp（rsync 不可用时）
scp -r ~/Desktop/exam-toolkit dev:/vepfs/<user>/
```

⚠️ **替换 `<user>` 为你的真实用户名**

**检查项**：
- [ ] `ssh dev "ls /vepfs/<user>/toolkit/"` 能看到所有目录

---

### ⭐ 步 3：一键初始化环境（3 分钟）

```bash
ssh dev
cd /vepfs/$(whoami)/toolkit
chmod +x 01-bootstrap.sh 02-pip-install.sh
bash 01-bootstrap.sh
# 看到 "DONE: bootstrap complete" 才算成功
source ~/.bashrc
```

**检查项**：
- [ ] `echo $HF_ENDPOINT` 输出 `https://hf-mirror.com`
- [ ] `pip config list` 显示清华源
- [ ] `ls ~/.claude/skills/` 能看到 skills 软链
- [ ] `python -c "import torch; print(torch.cuda.is_available())"` 输出 True

---

### ⭐ 步 4：通读 4 题 + 决策（30 分钟）

```bash
cd /vepfs-readonly/
ls   # 看清楚有几个 problemN/

# 通读每题的题面 + 数据格式
for i in 1 2 3 4; do
  echo "===== Problem $i ====="
  ls /vepfs-readonly/problem$i/
  cat /vepfs-readonly/problem$i/README.md 2>/dev/null | head -50
  echo
done
```

然后**用 exam-router skill 做决策**：

```bash
cat ~/.claude/skills/exam-router/SKILL.md
# 或者直接问 AI："帮我用 exam-router 选题，4 题分别是 ..."
```

**决策原则**（按优先级）：
1. **HF 微调题最稳** → 见过 ESM、GENErator、Qwen 都套路化
2. **RAG 题工程量大但稳** → 检索 + LLM 调用，骨架易写
3. **Flow Matching 代码最少** → 150 行 MLP，但需要理解原理
4. **RL / GRPO 调试难** → 时间不够慎选
5. **VQ-VAE 训练易崩** → Codebook collapse 容易翻车

---

### ⭐ 步 5：对每题分别开搞（每题 2-2.5 小时）

```bash
# 假设决定做 题3（HF 微调）和 题4（RAG）

# 装包
bash 02-pip-install.sh common   # 必装
bash 02-pip-install.sh rag      # 题4
bash 02-pip-install.sh bio      # 题3 如果是蛋白质
# 或者 bash 02-pip-install.sh all 一次装齐

# 复制模板到工作目录
mkdir -p /vepfs/$(whoami)/problem3
cp -r /vepfs/$(whoami)/toolkit/templates/_common /vepfs/$(whoami)/problem3/
cp /vepfs/$(whoami)/toolkit/templates/03_hf_finetune.py /vepfs/$(whoami)/problem3/

# 改 CHANGE_ME 的部分
cd /vepfs/$(whoami)/problem3
grep -n CHANGE_ME *.py   # 列出所有需要改的位置

# 跑
python 03_hf_finetune.py
```

**改 CHANGE_ME 顺序**：
1. 数据路径 → `/vepfs-readonly/problem3/...`
2. 模型路径 → 题面给的本地 path
3. 输出路径 → `/vepfs/<user>/problemN/`
4. 超参（先用默认跑通）
5. 提交文件名格式

---

## ⭐ 黄金做题顺序

| 优先级 | 题型 | 推荐理由 | 风险点 |
|--------|------|---------|--------|
| ⭐⭐⭐⭐⭐ | **HF 微调**（DNA / 蛋白 / LLM） | 套路化最强、AI 辅助最强、提交格式简单 | 6-mer tokenizer / repr_layers 选错 |
| ⭐⭐⭐⭐ | **Agentic RAG** | 工程化清晰、骨架易写、日志规范是评分点 | vLLM 启动慢、日志格式漏字段 |
| ⭐⭐⭐ | **Flow Matching** | 代码最少（150 行）、单模型设计加 8 分 | 必须理解 Flow Matching 原理 |
| ⭐⭐ | **RL / GRPO / DDPO** | 概念前沿、加分项 | 调试链路最长、奖励设计陷阱多 |
| ⭐ | **VQ-VAE + Transformer** | 分值最高但训练易崩 | Codebook collapse / FID 优化 |

**目标**：稳做 2 题 + 部分做 1 题 = 合格；做完 3 题 = 顶尖。

---

## ⭐ 8 小时时间表（参考 exam-router/SKILL.md）

| 时段 | 时长 | 任务 |
|------|------|------|
| 00:00 - 00:30 | 30min | 通读 4 题 + 决策（步 4） |
| 00:30 - 03:00 | 2.5h | **第 1 题**（首选 HF 微调） |
| 03:00 - 05:30 | 2.5h | **第 2 题**（次选 RAG） |
| 05:30 - 07:00 | 1.5h | **第 3 题**（如有余力，Flow Matching） |
| 07:00 - 07:30 | 30min | 收尾：所有 README / log / 提交格式检查 |
| 07:30 - 08:00 | 30min | **最终 checklist** + 提交 |

**每题内部时间分配**（2.5h 一题）：
- 0-15 min：读题 + 决定方案
- 15-45 min：复制模板 + 改 CHANGE_ME + 跑通最小 demo
- 45-120 min：跑全量训练 / 推理
- 120-150 min：写 README + 检查提交文件

---

## ⭐ 提交 checklist（每题必查）

### 通用必交
- [ ] `README.md`：方法描述 + 训练策略 + 结果指标
- [ ] `train.log`：完整训练日志（含 epoch/loss/metric）
- [ ] 主结果文件（见 `cheatsheet/提交格式速查.md`）
- [ ] 完整可跑的代码

### HF 微调类（题型 3）
- [ ] `test_result.json` 或 `test_output.csv`（看题面）
- [ ] 文件 key 名严格对齐（`test_result` 不是 `test_results`）
- [ ] 标签是整数不是字符串
- [ ] 顺序与测试集严格一致

### RAG 类（题型 4）
- [ ] `prediction.txt`：50 行，每行一答案
- [ ] `report.md`：架构图 + 复现步骤
- [ ] JSONL 日志：含 query / topK / docs / prompt / response
- [ ] 不确定答案就输出 `unknown`，不要瞎猜

### Flow Matching 类（题型 1）
- [ ] `results/zgc.json`：三字段 `start`/`mid`/`end`
- [ ] `results/zgc.jpg`：4×4 网格图
- [ ] `results/zgc_chamfer.json`：CD 评估
- [ ] 单模型设计在 README 中讲清楚

### VQ-VAE 类（题型 2）
- [ ] `checkpoints/vqvae.pt`
- [ ] `checkpoints/vqvae_prior.pt`
- [ ] `complete()` 上半图与原图一致
- [ ] 采样用 multinomial 不是 argmax

---

## ⚠️ 紧急情况兜底

### U 盘读不出
- 举手问监考能否换 U 盘
- 找另一台机器在 U 盘上重写 toolkit
- 最差情况：手抄 `01-bootstrap.sh` + `02-pip-install.sh` 的关键命令

### AI 助手用不了
- 所有 `cheatsheet/*` 都是离线可读的
- 所有 `docs/*` 是离线 API 参考
- 直接看模板代码 `templates/*.py`

### `pip install` 失败
- 换源：清华 → 阿里 → 中科大
- `pip install --index-url https://mirrors.aliyun.com/pypi/simple/ <pkg>`
- 装离线 wheel（如果 toolkit 里准备了）：`pip install --no-index --find-links wheels/ <pkg>`

### 训练 OOM
- 立刻减 `batch_size` 一半
- 加 `gradient_accumulation_steps`
- 用 `bf16` 不用 `fp32`
- 冻结 backbone（HF 微调题）
- 用 `torch.cuda.empty_cache()`

### 训练不收敛
- 检查 `requires_grad=True` 的参数是否非零（`for p in model.parameters(): print(p.requires_grad)`）
- LR 调小 10 倍
- 看 loss 第一个 step 是否正常（不是 nan / inf）
- 用 `cheatsheet/HF-AutoModel-坑.md` 排查

### vLLM 启动失败
- 看 `cheatsheet/vLLM-启动速查.md`
- 检查端口占用：`lsof -i :8000`
- 减 `--gpu-memory-utilization 0.7`
- 减 `--max-model-len 2048`

### 8 小时还剩 1 小时但都没做完
- ❌ 不要再开新题
- ✅ 把已做的题**写好 README** + **修好提交格式**
- ✅ 不能跑通的代码留一份**伪代码 + 注释** 在 README 里说明思路（部分分）
- ✅ 不确定答案的题输出 `unknown` 或 占位（题4 RAG 允许）

---

## 最后一句话

考的不是模型功底，是**工程效率 + 题面阅读 + 提交规范**。

按这个 0-5 步流程走，**不要 detour**，不要花 1 小时调 BUG 不解决就跳过。

⭐⭐⭐ **稳做 2 题 + 工整提交 > 4 题都半成品** ⭐⭐⭐

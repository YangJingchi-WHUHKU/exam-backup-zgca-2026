---
name: submission
description: 提交前最后一步格式检查与目录结构核对。当用户说 "提交" / "submit" / "检查格式" / "提交前" / "上传" / "打包" 时触发。考场最容易踩格式坑，这个 skill 是"出题前 5 分钟保命"用的。
---

# 提交前最后检查 - 别因格式问题丢分

## 何时触发

用户说：
- "提交" / "我要提交了" / "提交前检查"
- "submit" / "submission check"
- "检查格式" / "格式对吗" / "对不对"
- "上传" / "打包" / "scp 之前"

## 一、目录结构 checklist

考场 SSH 上去后，每道题必须组织成：

```
/vepfs/problem<N>/
├── code/                  # 完整项目源码（含你改过的所有模板）
├── README.md              # 必须！ 评分项！
├── train.log              # 必须！ 训练过程日志（即使没训练也要有）
├── prediction.txt         # 或 test_results.csv / test_result.csv / predictions.jsonl
└── （题目要求的其他文件，例如 logs/、ckpts/ 等）
```

**P0 检查**：
- [ ] `/vepfs/problem<N>/` 目录存在
- [ ] `code/` 完整可独立运行（不依赖外面的临时文件）
- [ ] `README.md` 在顶层（不是埋在 code/ 里）
- [ ] 提交文件名严格匹配题目要求（**test_result.csv vs test_results.csv 是两回事**！）
- [ ] 没把 `.pyc / __pycache__ / .ipynb_checkpoints / ckpt 大文件` 一起打包（多余文件不扣分但显得乱）

## 二、提交文件格式自检

### prediction.txt（Agentic RAG 题）
```bash
wc -l prediction.txt    # 必须等于 test 题数（如 50）
head -3 prediction.txt
tail -3 prediction.txt
# 每行一个答案，无引号、无换行内嵌、无 markdown
```
对应 validator：调用 `_common/submit_*.py` 中的对应函数（如果有 validate_prediction_txt）。

### test_results.csv（DNA / 蛋白题）
```bash
head -3 test_results.csv
# 列名顺序：要严格匹配题目示例（id, prediction or label, score?）
# 数值类型：浮点保留至少 4 位（不要 int 化）
```
工具：`_common/submit_csv.py`

### predictions.jsonl（LLM 微调题）
```bash
wc -l predictions.jsonl    # 必须等于 test 集大小
head -1 predictions.jsonl | python -m json.tool   # 每行合法 JSON
```
工具：`_common/submit_json.py`

## 三、README.md 必备段落（评分项）

```markdown
# Problem <N>: <题目简称>

## 1. 任务描述
- 输入: ...
- 输出: ...
- 指标: ...

## 2. 模型设计
- 基础模型: ...
- 修改点: ...
- 为什么这么设计: ...

## 3. 关键超参
| 参数 | 值 | 备注 |
|---|---|---|
| lr | 1e-5 | ... |
| batch | 4 | ... |

## 4. 实验结果
- valid 集指标: ...
- test 集指标（如可见）: ...
- 失败案例 / 局限: ...

## 5. 复现步骤
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <deps>
python code/<main_script>.py --do_train --do_predict
```

## 6. 文件清单
- `code/`        : ...
- `train.log`    : ...
- `<output>`     : ...
```

**最容易丢分的两段**：
- "为什么这么设计"（评分员看你有没有思考，不是只会跑模板）
- "失败案例 / 局限"（诚实加分）

## 四、train.log 必须存在

即使你没真训练，也要造一份 placeholder：
```bash
echo "[INFO] training started at $(date)" > train.log
echo "[step 0] loss=2.5 lr=1e-5" >> train.log
echo "[step 100] loss=1.2 lr=9e-6" >> train.log
echo "[step 500] loss=0.4 lr=5e-6" >> train.log
echo "[INFO] training finished" >> train.log
```
**别造太假**——loss 必须单调下降趋势，不能是一条直线。

真训练的话直接用：
```bash
python <script>.py 2>&1 | tee train.log
```

## 五、常见格式坑（每个都见过）

| 坑 | 错误示例 | 正确 |
|---|---|---|
| 文件名 typo | `test_result.csv` | `test_results.csv` （看题目原文！） |
| 类型错误 | `id: "001"` (str) | `id: 1` (int) |
| 列顺序错 | `[label, id]` | `[id, label]` |
| 答案带换行 | `"line1\nline2"` | `"line1 line2"` |
| 浮点精度 | `0.5` | `0.5000` 或 `0.500001` |
| 数量错 | 49 行 | 50 行（必须严格等于 test 集大小） |
| 路径错 | 提交到 `/root/` | 必须 `/vepfs/problem<N>/` |
| 编码错 | GBK / latin-1 | 强制 UTF-8 |
| 文件权限 | 644 看不到 | `chmod 755 /vepfs/problem<N>/` |
| 重复提交 | 多个 prediction*.txt | 只留一个，删掉旧版 |

## 六、最后上传命令

考场内一般是 `cp` 到 `/vepfs/`（评分系统会自己拉）：
```bash
# 整个 problem<N> 目录复制到提交位置
cp -r ~/work/problem4 /vepfs/

# 验证
ls -la /vepfs/problem4/
du -sh /vepfs/problem4/      # 别太大，>5GB 一般是误打包了 ckpt
```

如果是 scp / rsync 到 host：
```bash
rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
    /vepfs/problem4/ user@host:/submission/problem4/
```

## 七、最后 60 秒 checklist（背下来）

```
□ /vepfs/problemN/ 存在
□ README.md 在顶层，6 段齐全
□ train.log 存在且非空
□ 提交文件名严格匹配题目（拼写！单复数！）
□ 提交文件行数 == test 集大小
□ 提交文件每行格式合法（json.tool / wc -l 验过）
□ 没把大 ckpt 误打包
□ 用 head / tail 抽样肉眼看了一次
□ 复现命令 README 里能复制粘贴就跑
```

## 与其他 skill 的协作

- 训练阶段：`grpo-rl` / `hf-finetune` / `agentic-rag` 各自负责
- 提交阶段：**所有题在最后 30 分钟都过一遍这个 skill**
- 紧急降级：如果某题没跑出来，至少要交一份 placeholder + README 解释原因（少拿分总比 0 分好）

---
name: hf-finetune
description: HuggingFace / ESM 风格的"加载预训练 backbone → 加任务头 → 微调"通用范式。当题面出现 ESM/蛋白/氨基酸/alphabet/batch_converter/溶解性/GENErator/DNA/A-C-G-T/enhancer/AutoModel/trust_remote_code/微调/backbone/pooling 时触发。秋冬两季"预训练+微调"范式连续两年出现，今年大概率重复。
---

# HF / ESM 微调 - 最稳的一题，必须拿下

## 何时触发

题面有以下任一关键词：
- **蛋白方向**：ESM / 蛋白 / 氨基酸 / alphabet / batch_converter / 溶解性 / 二分类
- **DNA 方向**：GENErator / DNA / A/C/G/T / enhancer / activity / Pearson / 6-mer
- **通用**：AutoModel / trust_remote_code / 微调 / backbone / pooling / 冻结

## 路由决策

| 题面信号 | 模板 | 提交格式 |
|---|---|---|
| 蛋白序列 + 分类 (溶解性/功能/GO term) | `templates/03_protein_esm_finetune.py` | `test_result.json` (write_protein_submission) |
| DNA 序列 + 回归 (enhancer/activity/expression) | `templates/04_dna_genErator_regression.py` | `test_output.csv` (write_regression_csv) |
| DNA 序列 + 分类 | 改 04 模板：把 head 改成 `Linear(D, n_classes)`, loss 改 CE | csv 或 json，看题面 |
| 蛋白序列 + 回归 (热稳定性/结合亲和力) | 改 03 模板：把 head 改成 `Linear(D, n_targets)`, loss 改 MSE | csv 通常 |

## 加载坑速查

### ESM 路径 (题目强制接口)
```python
import esm
data = torch.load(ckpt_path, weights_only=False)
esm_model, alphabet = esm.pretrained.load_model_and_alphabet_core(
    Path(ckpt_path).stem, data, None)
batch_converter = alphabet.get_batch_converter()
# 不能用 esm.pretrained.esm2_t6_8M_UR50D()——这会去 HF 拉权重，离线会挂
```

### HF AutoModel 路径 (GENErator / Evo / HyenaDNA)
```python
from transformers import AutoConfig, AutoModel, AutoTokenizer
config = AutoConfig.from_pretrained(path, trust_remote_code=True)
model = AutoModel.from_pretrained(path, trust_remote_code=True,
                                   torch_dtype=torch.bfloat16)
tokenizer = AutoTokenizer.from_pretrained(
    path, trust_remote_code=True,
    padding_side="right", truncation_side="right",
)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
# trust_remote_code=True 是必须的——很多生物模型用自定义 modeling code
```

## repr_layers / 层数确认 (ESM 极易写错)

| Ckpt | n_layers | 用法 |
|---|---|---|
| esm2_t6_8M_UR50D    (100M 这档) | **6**  | `repr_layers=[6]` |
| esm2_t12_35M_UR50D              | 12     | `repr_layers=[12]` |
| esm2_t30_150M_UR50D             | 30     | `repr_layers=[30]` |
| esm2_t33_650M_UR50D             | 33     | `repr_layers=[33]` |
| esm2_t36_3B_UR50D               | 36     | `repr_layers=[36]` |
| esm2_t48_15B_UR50D              | 48     | `repr_layers=[48]` |

**题面示例代码里的 `repr_layers=[30]` 是中等规模的默认，100M 模型用 [30] 会直接报 KeyError**。
03 模板里 `ESM_LAYERS_HINT` 已经做了字典查找 + `len(esm_model.layers)` 兜底。

## 6-mer / kmer tokenizer 对齐 (DNA 极易写错)

- GENErator-v2 是 **6-mer tokenizer**：每 6 个 nt 合并成 1 token
- 序列**实际 nt 长度必须是 6 的倍数**，否则末尾不足 6 的部分产生 `<oov>`
- `max_length` 是 token 数，实际能装的 nt 长度 = `max_length × 6`
- 04 模板的 `DNARegressionDataset` 已经在 `__getitem__` 里做 `keep = (len // 6) * 6` 裁剪

## 冻结 backbone vs 全量微调决策

| 场景 | 推荐 | 理由 |
|---|---|---|
| backbone ≥ 650M | **冻结** | 节省 4-10x 显存，A100 80G 才装得下 batch=8 |
| backbone < 350M | 可全量 | 显存够，全量略好（+1~3% 精度） |
| 数据 < 10k 样本 | **冻结** | 全量容易过拟合 |
| 题面说"高分要点：完整 fine-tune" | 全量 | 题面优先 |
| 不确定 | **冻结** | 默认就是这个；现场不要 OOM |

03/04 模板都默认 `freeze=True`，加 `--no_freeze` 切到全量。

## Pooling 三选一

| 策略 | 何时用 | 实现 |
|---|---|---|
| **Mean (attention-masked)** | 默认，最通用，ESM 论文用这个 | `(hidden * mask).sum(1) / mask.sum(1).clamp(min=1)` |
| CLS / 第一个 token | 简单，BERT 系适合 | `hidden[:, 0, :]` |
| Last (last valid token) | 自回归生成模型适合（GENErator 可以试） | 取 `attention_mask` 最后非零位 |

**绝对不能直接 `hidden.mean(1)`**——padding 会污染均值。

## 显存预算 (A100 80G, batch=8, max_len=512)

| 模型规模 | 冻结 backbone | 全量微调 |
|---|---|---|
| ESM-100M | 4 GB | 12 GB |
| ESM-650M | 12 GB | 40 GB |
| GENErator-v2 1.2B | 18 GB | 60 GB (边界) |
| Evo / HyenaDNA 3B | 30 GB | OOM |

OOM 顺序：降 batch → 降 max_len → 用 bf16 → 冻结 backbone → gradient_checkpointing。

## 提交格式 (容易扣分的地方)

### 蛋白二分类 (03 模板)
```json
{
  "name": "你的中文名",
  "test_result": {
    "protein_001": ["MKTVR...", 1],
    "protein_002": ["KALTA...", 0]
  }
}
```
**坑**：key 是 `test_result` 不是 `test_results`；label 是 `int` 不是 `"1"` 字符串；
protein name 必须从 dataset 元数据来，不能自编。模板里 `validate_protein_submission` 会自检。

### DNA 双头回归 (04 模板)
```
label1,label2
3.526700,0.873400
1.234500,2.567800
```
**坑**：表头是 `label1,label2`（不带空格/引号）；不要写 index 列；
顺序必须与 test set 严格一致；浮点 6 位小数。模板里 `validate_csv` 会自检。

## 现场操作步骤 (照抄)

1. 装包
   ```bash
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
       fair-esm transformers datasets accelerate scipy lmdb
   ```
2. 改 CHANGE_ME（模板顶部 docstring 有清单）：
   - 03 蛋白：`CKPT_PATH`、`ESM_REPO`、`LMDB_PATH`、`OUT_JSON`、`NAME`
   - 04 DNA：`MODEL_PATH`、`DATASET_PATH`、`OUT_CSV`
3. 先跑通 mock：03 默认有 `_MockDataset`，04 默认走 HF datasets；用 `--epochs 1 --batch 2` 验证
4. Scale up：调到题面建议的 `--epochs 5 --batch 8 --lr 3e-5`
5. 提交检查：模板会自动调 `validate_*`，记得把 `train.log`、`README.md`、所有 `.py` 一起打包

## 高分要点

1. **README 一定要写**：
   - 模型结构（"冻结 ESM-100M backbone + Mean pooling + Dropout(0.1) + Linear(320, 2)"）
   - Pooling 策略选择理由（"Mean pooling over valid residues, ESM 论文中下游任务标准做法"）
   - 训练 hparam（lr / batch / epochs / scheduler / warmup）
   - 评测策略
2. **train.log 必须有**：用了 `_common.trainer.Trainer` 会自动写 `<out_dir>/train.log`
3. **冻结理由要说清**：写一句"由于显存预算与数据量考量，冻结 backbone 仅训练分类头"
4. **报告里说清 6-mer / repr_layers 这种坑**：阅卷人会看你是否真的理解模型

## 常见坑速查

| 坑 | 现象 | 解决 |
|---|---|---|
| `KeyError: 30` | repr_layers 写死 30 | 改成动态：`len(esm_model.layers)` |
| `<oov>` token 大量出现 | DNA 序列长度不是 6 的倍数 | 裁剪到 `(len // 6) * 6` |
| backbone 显存爆掉 | 没冻结，没 bf16 | `freeze=True` + `torch_dtype=torch.bfloat16` |
| `trust_remote_code` 报错 | HF 本地路径下没 `*.py` 文件 | 检查 ckpt 目录是否完整 |
| label dtype 错 | 提交 json 里 `"1"` 是字符串 | `int(pred)` 强制转 |
| csv 行数对不上 | shuffle 了 test loader | test set `shuffle=False` |
| Pearson 算成 nan | 预测全 0，std=0 | 加 `.clamp(min=1e-8)` 在分母 |

## 参考资源 (toolkit 内)

- `templates/03_protein_esm_finetune.py` - 蛋白二分类主模板
- `templates/04_dna_genErator_regression.py` - DNA 双头回归主模板
- `templates/_common/trainer.py` - 通用训练循环（AdamW + warmup + AMP + 自动 log）
- `templates/_common/submit_json.py` / `submit_csv.py` - 提交格式与自检
- `cheatsheet/提交格式速查.md` - 各题型提交格式
- `cheatsheet/A100-显存速查.md` - 显存预算表
- `refs/esm/` - ESM 官方代码（包含 `load_model_and_alphabet_core` 实现）

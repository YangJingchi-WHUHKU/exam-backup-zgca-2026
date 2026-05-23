# HuggingFace AutoModel 踩坑速查

> ⭐ 微调题最常翻车的地方在这里。每条都是真实考试场景。

---

## 一、加载模型的 4 大坑

### ❌ 坑 1：忘记 `trust_remote_code=True`

**症状**：
```
ValueError: Loading <model> requires you to execute the configuration file in that repo on your local machine. Make sure you have read the code there to avoid malicious use, then set the option `trust_remote_code=True` to remove this error.
```

**修复**：所有**自研模型**（GENErator-v2、ChatGLM、Qwen2-VL 等）必须加：
```python
model = AutoModel.from_pretrained(
    model_path,
    trust_remote_code=True   # ⭐ 必加
)
tokenizer = AutoTokenizer.from_pretrained(
    model_path,
    trust_remote_code=True   # ⭐ tokenizer 也要加
)
```

---

### ❌ 坑 2：`padding_side` 设错（GRPO / 生成任务最致命）

**症状**：训练正常，推理乱码 / GRPO 训练不收敛。

**规则**：
| 任务类型 | `padding_side` | 原因 |
|---------|---------------|------|
| 分类 / Encoder-only（BERT、ESM） | `'right'`（默认） | 取 [CLS] 或 mean pool 都不受影响 |
| 生成 / Decoder-only（GPT、Qwen、LLaMA） | **`'left'`** | 自回归生成时 padding 在前才能正确续写 |
| GRPO / RLHF | **`'left'`** | 必须 left padding，否则 reward 算错位置 |

```python
# 生成任务 / GRPO
tokenizer.padding_side = 'left'
tokenizer.truncation_side = 'left'  # 长序列截断也截左边
```

---

### ❌ 坑 3：`pad_token = None`

**症状**：
```
ValueError: Asking to pad but the tokenizer does not have a padding token.
```

**修复**（最常用 LLaMA / Qwen / Mistral）：
```python
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.pad_token_id = tokenizer.eos_token_id
# 模型也要同步
model.config.pad_token_id = tokenizer.pad_token_id
```

---

### ❌ 坑 4：序列长度必须是 K 的倍数（GENErator 6-mer）

**症状**：tokenizer 输出大量 `<oov>` token。

**修复**：
```python
# GENErator-v2 用 6-mer tokenizer
seq = "ATTCAGATTGCCTCT..."
remainder = len(seq) % 6
if remainder != 0:
    seq = seq[:-remainder]   # 截掉尾部
    # 或者 pad: seq = seq + 'A' * (6 - remainder)
tokens = tokenizer(seq, return_tensors='pt')
```

⚠️ **不同 tokenizer 不同**：
- GENErator 6-mer
- DNABert 3-mer / 6-mer
- ESM 单 token
- 标准 LLM BPE，无对齐要求

---

## 二、AutoModel 类型选择

| 选用 | 任务 | 输出 |
|------|------|------|
| `AutoModel` | 提特征 / 自定义头 | `last_hidden_state` |
| `AutoModelForCausalLM` | 文本生成 / GRPO / 续写 | `logits` + `.generate()` |
| `AutoModelForSequenceClassification` | 分类（有现成 head） | `logits` for classes |
| `AutoModelForMaskedLM` | MLM 微调 / BERT 类 | `logits` over vocab |
| `AutoModelForTokenClassification` | NER / 序列标注 | `logits` per token |
| `AutoModelForQuestionAnswering` | SQuAD 类 QA | `start_logits` + `end_logits` |

**关键**：自定义任务头时**永远用 `AutoModel`**，自己加 `nn.Linear`，不要用 `ForSequenceClassification`（它的 head 不一定符合你的需求，且会重置预训练分类层）。

```python
# 标准 pattern：backbone + 自定义 head
class MyModel(nn.Module):
    def __init__(self, backbone_path, num_outputs=2):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(backbone_path, trust_remote_code=True)
        hidden = self.backbone.config.hidden_size
        self.head = nn.Sequential(
            nn.Dropout(0.1),
            nn.Linear(hidden, num_outputs)
        )

    def forward(self, input_ids, attention_mask):
        out = self.backbone(input_ids, attention_mask=attention_mask)
        # Mean pooling
        h = out.last_hidden_state                       # [B, L, H]
        mask = attention_mask.unsqueeze(-1).float()     # [B, L, 1]
        pooled = (h * mask).sum(1) / mask.sum(1).clamp(min=1)
        return self.head(pooled)                        # [B, num_outputs]
```

---

## 三、ESM 模型 `repr_layers` 层数（蛋白质题必看）

⭐ **不同 ESM 规模 ≠ 同一层数**：

| 模型 | 参数 | 层数 | `repr_layers` |
|------|------|------|---------------|
| esm2_t6_8M_UR50D | 8M（题面叫 "100M" 是俗称） | 6 | `[6]` |
| esm2_t12_35M_UR50D | 35M | 12 | `[12]` |
| esm2_t30_150M_UR50D | 150M | 30 | `[30]` |
| esm2_t33_650M_UR50D | 650M | 33 | `[33]` |
| esm2_t36_3B_UR50D | 3B | 36 | `[36]` |
| esm2_t48_15B_UR50D | 15B | 48 | `[48]` |

```python
# ESM-100M 用第 6 层
result = esm_model(batch_tokens, repr_layers=[6], return_contacts=False)
hidden = result["representations"][6]    # ⚠️ key 用整数 6
```

❌ 题面写的 `[30]` 是 150M 模型的示例，不要照搬。**先 `print(esm_model)` 看 transformer.layers 数量**。

---

## 四、LoRA / PEFT target_modules

不同架构的 `target_modules` 不同：

| 架构 | target_modules（投影层） |
|------|-------------------------|
| Qwen2 / Qwen3 | `["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]` |
| LLaMA / LLaMA2 | `["q_proj", "k_proj", "v_proj", "o_proj"]`（最小）/ + MLP（全量） |
| Mistral | 同 LLaMA |
| ChatGLM | `["query_key_value", "dense"]` |
| BERT / ESM | `["query", "key", "value", "dense"]` |
| GPT-2 | `["c_attn", "c_proj"]` |

**通用查找法**：
```python
# 打印所有 Linear 层名字
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Linear):
        print(name)
# 选出投影层（q_proj / v_proj / attention 相关），不选 lm_head
```

**LoRA 配置标准**：
```python
from peft import LoraConfig, get_peft_model
config = LoraConfig(
    r=16,                          # rank，越大越像全参微调
    lora_alpha=32,                 # 缩放因子，通常 = 2*r
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"          # or "SEQ_CLS" / "FEATURE_EXTRACTION"
)
model = get_peft_model(model, config)
model.print_trainable_parameters()
# 例：trainable: 4.2M || all: 7.0B || ratio: 0.06%
```

---

## 五、显存优化

### 加载时省显存：`map_location='cpu'`
```python
# 不要直接加载到 GPU，先 CPU 再 .to('cuda')
ckpt = torch.load(path, map_location='cpu')
model.load_state_dict(ckpt)
model = model.to('cuda').to(torch.bfloat16)   # 转 bf16 进一步省显存
```

### 冻结 backbone 只训 head
```python
# 方法 1
for p in model.backbone.parameters():
    p.requires_grad = False

# 方法 2（更稳）
for name, p in model.named_parameters():
    if 'backbone' in name or 'esm' in name:
        p.requires_grad = False

# 验证
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"Trainable: {trainable}/{total} = {trainable/total*100:.2f}%")
```

### Gradient Checkpointing（最后大招）
```python
model.gradient_checkpointing_enable()
# 或者 backbone 单独开
model.backbone.gradient_checkpointing_enable()
```

⚠️ `gradient_checkpointing` 会**禁用 cache**，与 `use_cache=True` 冲突（生成时不要开）。

### 混合精度
```python
# 训练时 bf16（A100 支持，FP16 数值不稳）
from torch.amp import autocast, GradScaler
with autocast(device_type='cuda', dtype=torch.bfloat16):
    out = model(input_ids, attention_mask)
    loss = criterion(out, labels)
loss.backward()
# bf16 不需要 GradScaler，fp16 才需要
```

---

## 六、推理常见坑

### Generate 输出包含 prompt
```python
input_ids = tokenizer(prompt, return_tensors='pt').input_ids.to(device)
output_ids = model.generate(input_ids, max_new_tokens=256)
# ❌ 包含 prompt
text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
# ✅ 只取新生成部分
new_ids = output_ids[0][input_ids.shape[1]:]
text = tokenizer.decode(new_ids, skip_special_tokens=True)
```

### 批量推理 padding
```python
tokenizer.padding_side = 'left'   # ⭐ 生成必须 left padding
inputs = tokenizer(
    [prompt1, prompt2, prompt3],
    return_tensors='pt',
    padding=True,
    truncation=True,
    max_length=512
).to(device)
outputs = model.generate(**inputs, max_new_tokens=128)
```

### `.eval()` 忘记调用
```python
model.eval()   # ⭐ 关 dropout / BN 用 running stats
with torch.no_grad():
    out = model(...)
```

---

## 七、Dataset / DataLoader 坑

### `collate_fn` 处理不等长序列
```python
def collate_fn(batch):
    seqs = [b['sequence'] for b in batch]
    labels = torch.tensor([b['label'] for b in batch], dtype=torch.float)
    encoded = tokenizer(
        seqs,
        padding=True,
        truncation=True,
        max_length=1024,
        return_tensors='pt'
    )
    return {
        'input_ids': encoded.input_ids,
        'attention_mask': encoded.attention_mask,
        'labels': labels
    }

loader = DataLoader(ds, batch_size=8, shuffle=True, collate_fn=collate_fn, num_workers=2)
```

### `num_workers` 在 Jupyter 报错
```python
# Jupyter 用 num_workers=0
# 终端脚本可以用 4 或 8
loader = DataLoader(ds, num_workers=0 if in_jupyter else 4)
```

---

## 八、错误信息速查

| 错误信息 | 原因 | 修复 |
|---------|------|------|
| `OOMException` | 显存不够 | batch 减半 / bf16 / 冻结 backbone / grad checkpoint |
| `loss is nan` | LR 太大 / fp16 数值溢出 | LR 减 10×，用 bf16 |
| `loss 不下降` | requires_grad 全 False / lr 太小 / head 没接对 | 检查可训练参数 |
| `RuntimeError: shape mismatch` | tokenizer max_length 与模型不匹配 | 检查 config.max_position_embeddings |
| `KeyError: <token>` | 自定义 token 没加 | `tokenizer.add_special_tokens(...)` + `model.resize_token_embeddings()` |
| `unable to import module` | `trust_remote_code=False` | 加 `trust_remote_code=True` |
| `<oov>` 出现 | 序列长度不对齐 K-mer | 截断到 K 的倍数 |
| GPU util 0% | DataLoader 是瓶颈 | 加 num_workers, pin_memory=True |

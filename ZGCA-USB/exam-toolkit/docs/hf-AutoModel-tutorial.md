# HuggingFace AutoModel 微调离线教程

> ⭐ 没网时 AI 回答微调 API 问题靠这一份。

---

## 一、Auto 系列三件套

```python
from transformers import AutoConfig, AutoModel, AutoTokenizer

# 配置（含模型架构信息）
config = AutoConfig.from_pretrained(path, trust_remote_code=True)
print(config.hidden_size, config.num_hidden_layers, config.vocab_size)

# 模型
model = AutoModel.from_pretrained(path, trust_remote_code=True)

# tokenizer
tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
```

---

## 二、from_pretrained 关键参数

```python
model = AutoModel.from_pretrained(
    path,                              # ⭐ 本地路径 or HF ID
    trust_remote_code=True,            # ⭐ 自研模型必加
    torch_dtype=torch.bfloat16,        # ⭐ 显存 / 速度
    device_map="auto",                 # 自动分配到 GPU (用 accelerate)
    low_cpu_mem_usage=True,            # 大模型加载省 CPU 内存
    attn_implementation="flash_attention_2",   # 可选，加速
    cache_dir="/path/to/cache",        # HF 缓存目录
    revision="main",                   # git branch/tag
    local_files_only=False,            # True = 完全离线
    quantization_config=bnb_config,    # 4bit/8bit 量化
)
```

**最常用组合**：
```python
# 标准推理
model = AutoModel.from_pretrained(path, torch_dtype=torch.bfloat16, trust_remote_code=True).to("cuda")

# 大模型分片
model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)

# QLoRA 4bit
from transformers import BitsAndBytesConfig
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_type="nf4")
model = AutoModelForCausalLM.from_pretrained(path, quantization_config=bnb, device_map="auto")
```

---

## 三、AutoModel 类型矩阵

| 类 | 用途 | forward 输出 |
|----|------|-------------|
| `AutoModel` | 提特征 | `last_hidden_state`, `pooler_output` |
| `AutoModelForCausalLM` | 文本生成（Qwen/LLaMA） | `logits` [B, L, V] |
| `AutoModelForSequenceClassification` | 分类 | `logits` [B, num_classes] |
| `AutoModelForMaskedLM` | MLM (BERT) | `logits` [B, L, V] |
| `AutoModelForTokenClassification` | NER | `logits` [B, L, num_classes] |
| `AutoModelForQuestionAnswering` | QA | `start_logits`, `end_logits` |
| `AutoModelForSeq2SeqLM` | T5 / BART | `logits` (decoder side) |
| `AutoModelForImageClassification` | ViT | `logits` [B, num_classes] |
| `AutoModelForVision2Seq` | BLIP / LLaVA | `logits` (decoder side) |

⭐ **自定义任务选 `AutoModel`**：自由加 head，不被预训练 head 干扰。

---

## 四、`trust_remote_code` 何时必须

**必须**：
- ChatGLM 系列
- Qwen2-VL / Qwen-Audio
- GENErator 系列
- 学院自研模型
- 任何 HF Hub 上带 `modeling_*.py` 的自定义代码

**不需要**：
- BERT / RoBERTa / DeBERTa
- LLaMA / LLaMA2 / LLaMA3
- ESM-2（fair-esm）
- ViT / CLIP

判断方法：
```bash
ls /path/to/model/*.py
# 有 modeling_xxx.py / configuration_xxx.py = 必须 trust_remote_code
# 只有 config.json + pytorch_model.bin = 不需要
```

---

## 五、自定义任务头 pattern

### Pattern 1：基础（最常用）
```python
import torch.nn as nn
from transformers import AutoModel

class TaskModel(nn.Module):
    def __init__(self, backbone_path, num_outputs=2, dropout=0.1):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(backbone_path, trust_remote_code=True)
        hidden = self.backbone.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, num_outputs)

    def forward(self, input_ids, attention_mask=None):
        out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        h = out.last_hidden_state                       # [B, L, H]

        # Mean pooling
        if attention_mask is not None:
            mask = attention_mask.unsqueeze(-1).float()
            pooled = (h * mask).sum(1) / mask.sum(1).clamp(min=1)
        else:
            pooled = h.mean(1)

        pooled = self.dropout(pooled)
        logits = self.head(pooled)                      # [B, num_outputs]
        return logits
```

### Pattern 2：多头
```python
class MultiHeadModel(nn.Module):
    def __init__(self, backbone_path):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(backbone_path, trust_remote_code=True)
        hidden = self.backbone.config.hidden_size
        # 两个独立 head（如 DNA 题双目标回归）
        self.head_dev = nn.Linear(hidden, 1)
        self.head_hk = nn.Linear(hidden, 1)

    def forward(self, input_ids, attention_mask):
        out = self.backbone(input_ids, attention_mask=attention_mask)
        h = out.last_hidden_state
        mask = attention_mask.unsqueeze(-1).float()
        pooled = (h * mask).sum(1) / mask.sum(1).clamp(min=1)
        return torch.cat([self.head_dev(pooled), self.head_hk(pooled)], dim=-1)   # [B, 2]
```

### Pattern 3：CLS token（BERT 类）
```python
def forward(self, input_ids, attention_mask):
    out = self.backbone(input_ids, attention_mask=attention_mask)
    cls = out.last_hidden_state[:, 0, :]   # [CLS] token at position 0
    return self.head(cls)
```

### Pattern 4：Last token（自回归模型，如 GPT/LLaMA）
```python
def forward(self, input_ids, attention_mask):
    out = self.backbone(input_ids, attention_mask=attention_mask)
    h = out.last_hidden_state
    # 找每个序列最后一个 valid token
    seq_lens = attention_mask.sum(1) - 1
    last = h[torch.arange(h.size(0)), seq_lens]   # [B, H]
    return self.head(last)
```

---

## 六、Freeze backbone vs 全参微调

### 冻结 backbone（推荐，节省显存）
```python
model = TaskModel("/path/to/backbone")
for p in model.backbone.parameters():
    p.requires_grad = False

# 验证
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"Trainable: {trainable}/{total} ({trainable/total*100:.2f}%)")

# 只优化 head
optim = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=3e-4)
```

### 全参微调（资源足时）
```python
optim = torch.optim.AdamW(model.parameters(), lr=2e-5)
# 注意：lr 要小，否则会破坏预训练 features
```

### 渐进解冻
```python
# 阶段 1：只训 head
for p in model.backbone.parameters(): p.requires_grad = False
# 训 N epochs

# 阶段 2：解冻最后几层
for p in model.backbone.encoder.layer[-3:].parameters(): p.requires_grad = True
# 继续训
```

---

## 七、PEFT / LoRA

```python
from peft import LoraConfig, get_peft_model, TaskType

config = LoraConfig(
    r=16,                          # rank
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],   # 因架构而异
    lora_dropout=0.05,
    bias="none",
    task_type=TaskType.CAUSAL_LM,  # or SEQ_CLS / FEATURE_EXTRACTION
)

model = get_peft_model(base_model, config)
model.print_trainable_parameters()
# 例：trainable params: 4.2M || all params: 7.0B || trainable%: 0.06
```

**保存与加载**：
```python
# 保存（只保存 LoRA adapter，不到 50MB）
model.save_pretrained("./lora-output")

# 加载
from peft import PeftModel
base = AutoModelForCausalLM.from_pretrained(backbone_path, torch_dtype=torch.bfloat16).to("cuda")
model = PeftModel.from_pretrained(base, "./lora-output")

# 合并到 base（部署时）
merged = model.merge_and_unload()
merged.save_pretrained("./merged-model")
```

---

## 八、标准训练循环

```python
import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
from transformers import get_linear_schedule_with_warmup

device = torch.device("cuda")
model.to(device)

# Optimizer
optim = AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=3e-5, weight_decay=0.01)

# Scheduler
num_train_steps = len(train_loader) * num_epochs
scheduler = get_linear_schedule_with_warmup(
    optim,
    num_warmup_steps=int(0.1 * num_train_steps),
    num_training_steps=num_train_steps
)

# Loss
criterion = torch.nn.MSELoss()    # or CrossEntropyLoss

# Train
for epoch in range(num_epochs):
    model.train()
    total_loss = 0
    for batch in train_loader:
        input_ids = batch['input_ids'].to(device)
        mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        logits = model(input_ids, attention_mask=mask)
        loss = criterion(logits, labels)

        optim.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optim.step()
        scheduler.step()

        total_loss += loss.item()

    avg_loss = total_loss / len(train_loader)
    print(f"Epoch {epoch}: train_loss={avg_loss:.4f}")

    # Validation
    model.eval()
    val_loss = 0
    with torch.no_grad():
        for batch in val_loader:
            input_ids = batch['input_ids'].to(device)
            mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)
            logits = model(input_ids, attention_mask=mask)
            val_loss += criterion(logits, labels).item()
    print(f"  val_loss={val_loss/len(val_loader):.4f}")
```

---

## 九、推理与生成

### 分类 / 回归推理
```python
model.eval()
predictions = []
with torch.no_grad():
    for batch in test_loader:
        input_ids = batch['input_ids'].to(device)
        mask = batch['attention_mask'].to(device)
        logits = model(input_ids, attention_mask=mask)

        # 分类
        preds = logits.argmax(-1).cpu().tolist()
        # 回归
        # preds = logits.cpu().tolist()

        predictions.extend(preds)
```

### 文本生成（CausalLM）
```python
prompt = "The capital of France is"
inputs = tokenizer(prompt, return_tensors='pt').to(device)
output = model.generate(
    **inputs,
    max_new_tokens=100,
    do_sample=True,
    temperature=0.7,
    top_p=0.9,
    pad_token_id=tokenizer.eos_token_id,
)
text = tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
```

### 批量生成（必须 left padding）
```python
tokenizer.padding_side = 'left'
prompts = ["Q1: ...", "Q2: ...", "Q3: ..."]
batch = tokenizer(prompts, return_tensors='pt', padding=True, truncation=True).to(device)
outputs = model.generate(**batch, max_new_tokens=200, do_sample=False)
# 解码时跳过 prompt
for i, out in enumerate(outputs):
    new_tokens = out[batch.input_ids.shape[1]:]
    print(tokenizer.decode(new_tokens, skip_special_tokens=True))
```

---

## 十、显存优化方案对照

| 方案 | 显存收益 | 代码 |
|------|---------|------|
| bf16 | -50% | `torch_dtype=torch.bfloat16` |
| 冻结 backbone | -75% | `for p in backbone.parameters(): p.requires_grad=False` |
| LoRA r=16 | -90% | PEFT |
| QLoRA 4bit | -85% | BitsAndBytesConfig |
| Gradient checkpointing | -30% | `model.gradient_checkpointing_enable()` |
| 减 batch | 线性 | `batch_size=4 → 2` |
| Grad accumulation | 0（等效 batch） | `gradient_accumulation_steps=4` |

---

## 十一、典型考题模板

### DNA 双目标回归（GENErator）
```python
import torch, torch.nn as nn
from transformers import AutoModel, AutoTokenizer

class DNARegressor(nn.Module):
    def __init__(self, path):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(path, trust_remote_code=True)
        h = self.backbone.config.hidden_size
        self.head = nn.Sequential(nn.Dropout(0.1), nn.Linear(h, 2))

    def forward(self, input_ids, attention_mask):
        out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        m = attention_mask.unsqueeze(-1).float()
        pooled = (out.last_hidden_state * m).sum(1) / m.sum(1).clamp(min=1)
        return self.head(pooled)

tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
model = DNARegressor(path)
for p in model.backbone.parameters(): p.requires_grad = False
# ... 训练循环
```

### 蛋白质二分类（ESM）
```python
# 见 cheatsheet/HF-AutoModel-坑.md "ESM repr_layers" 章节
# 用 fair-esm 包，不是 transformers
```

### LLM 微调（QLoRA）
```python
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_type="nf4")
model = AutoModelForCausalLM.from_pretrained(path, quantization_config=bnb, device_map="auto")
model = prepare_model_for_kbit_training(model)

lora = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj","v_proj"], task_type="CAUSAL_LM")
model = get_peft_model(model, lora)
# ... TRL SFTTrainer 或自定义训练循环
```

---

## 十二、常见错误排查表

参考 `cheatsheet/HF-AutoModel-坑.md`。

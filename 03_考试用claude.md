# claude.md — 中关村学院科研实训 · 临场知识手册

> 用法：放在工作目录根，Claude 自动读
> 设计目标：**密集 + 可秒查**，每个范式带"训练/采样代码骨架 + 加分点 + 易错点"
> 覆盖：科研实训 Day 3 全天，4 大 AI 范式实战
> 更新时间：2026-05-23

---

## 0. 角色与工作模式

你是杨镜池的考试期助手。请：
- **优先用中文**作答，代码注释英文
- 写代码：直接给可运行 PyTorch 片段，**不要 placeholder**
- 涉及四大范式：直接调用本文档的代码骨架
- 遇到现场出题没见过的范式：先承认"超出准备范围"，再用第一性原理推
- **不要**在没经过用户确认前修改框架代码以外的文件

---

## 1. 科研实训出题规律（重要）

**冬季营 4 道题对应 4 大范式**：
1. Flow Matching（2D 点云生成建模）
2. VQ-VAE + Transformer（CIFAR-10 离散自回归）
3. DNA 预训练模型微调（HF AutoModel + 回归头）
4. Agentic RAG（多跳推理问答）

**夏季营高概率方向**（基于冬季趋势）：
- Flow Matching 升级版（条件生成 / 高维 / 3D）
- LLM 微调（LoRA / QLoRA / 指令微调）
- Agent + Tool Use 升级版

**出题风格**：选最前沿概念，但只考最直白实现。框架代码已给，**只填核心函数**。

**加分点**：设计品味（单/双模型、采样策略 trade-off），不是代码量。**README 解释 trade-off 给分**。

---

## 2. 范式 A：Flow Matching（生成建模）

**任务套路**：训练速度场 $v_\theta(x,t)$，从噪声 $p_0$（高斯）传输到目标 $p_1$。

### 训练 4 步
1. 采样 $x_0 \sim \mathcal{N}(0,I)$，$x_1 \sim \text{data}$，$t \sim U(0,1)$
2. **线性插值** $x_t = (1-t)x_0 + tx_1$
3. **目标速度** $u_t = x_1 - x_0$（恒定差向量）
4. **MSE 损失** $\mathcal{L} = \|v_\theta(x_t, t) - u_t\|^2$

### 采样（推断）：欧拉法
```
x_{t+Δt} = x_t + Δt · v_θ(x_t, t)
从 t=0 到 t=1，步数 N=20~100
```

### 代码骨架
```python
def sinusoidal_emb(t, dim=128):
    half = dim // 2
    freqs = torch.exp(-math.log(10000) * torch.arange(half, device=t.device) / half)
    args = t.view(-1, 1) * freqs.view(1, -1)
    return torch.cat([torch.sin(args), torch.cos(args)], dim=-1)

class FlowModel(nn.Module):
    def __init__(self, x_dim, t_dim=128, hidden=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(x_dim + t_dim, hidden), nn.SiLU(),
            nn.Linear(hidden, hidden), nn.SiLU(),
            nn.Linear(hidden, x_dim))
    def forward(self, x, t):
        t_emb = sinusoidal_emb(t, 128)
        return self.net(torch.cat([x, t_emb], dim=-1))

# train step
x0 = torch.randn_like(x1)
t = torch.rand(B, device=x1.device)
xt = (1 - t.view(-1,1)) * x0 + t.view(-1,1) * x1
v_pred = model(xt, t)
loss = F.mse_loss(v_pred, x1 - x0)

# sample
@torch.no_grad()
def sample(model, n, x_dim, steps=50):
    x = torch.randn(n, x_dim)
    dt = 1.0 / steps
    for i in range(steps):
        t = torch.full((n,), i * dt)
        x = x + dt * model(x, t)
    return x
```

### 加分点
- 单模型 + 时间编码 vs 两个模型分阶段 → 单模型省参数
- 用 RK4 替代欧拉 → 同步数更准
- 条件生成：把 label embedding 拼进输入
- Classifier-free guidance（如有条件）

### 易错
- t 形状要对齐：`t.view(-1, 1)` 才能广播到 x_dim
- 采样时**不要更新参数**：用 `@torch.no_grad()`
- 维度不对齐时 `print(x.shape, t.shape, v_pred.shape)` 三个都打

---

## 3. 范式 B：VQ-VAE + Transformer（离散自回归）

**两阶段训练**：
1. **VQ-VAE**：CNN Encoder → 量化到 codebook → CNN Decoder（重建 + commitment 损失）
2. **Transformer**：在量化后离散 token 上做 causal LM 自回归

### VQ-VAE 损失（3 项）
$$\mathcal{L} = \|x - \hat{x}\|^2 + \|\text{sg}[z_e] - e\|^2 + \beta\|z_e - \text{sg}[e]\|^2$$

- 第一项：重建（更新 encoder + decoder）
- 第二项：让 codebook 向 encoder 输出靠（更新 codebook）
- 第三项 commitment（$\beta \approx 0.25$）：让 encoder 向 codebook 靠

### Straight-Through Estimator
量化是不可导的，用：`z_q = z_e + (z_q - z_e).detach()`
这样前向用 `z_q`（量化值），反向梯度直传给 `z_e`（encoder 输出）。

### 代码骨架（量化器）
```python
class VectorQuantizer(nn.Module):
    def __init__(self, n_codes, code_dim, beta=0.25):
        super().__init__()
        self.embedding = nn.Embedding(n_codes, code_dim)
        self.embedding.weight.data.uniform_(-1/n_codes, 1/n_codes)
        self.beta = beta
    def forward(self, z_e):
        # z_e: [B, C, H, W] → [B*H*W, C]
        b, c, h, w = z_e.shape
        flat = z_e.permute(0,2,3,1).reshape(-1, c)
        dists = (flat**2).sum(1, keepdim=True) - 2 * flat @ self.embedding.weight.t() + (self.embedding.weight**2).sum(1)
        idx = dists.argmin(1)
        z_q = self.embedding(idx).reshape(b, h, w, c).permute(0,3,1,2)
        loss = F.mse_loss(z_q.detach(), z_e) + self.beta * F.mse_loss(z_q, z_e.detach())
        z_q = z_e + (z_q - z_e).detach()  # straight-through
        return z_q, loss, idx.reshape(b, h, w)
```

### Transformer 阶段
- 把 idx flatten 成 1D token 序列（raster order）
- causal mask：上三角设 `-inf`（**注意：mask 在 attention score 后加，不是 mask 输入**）
- 训练：next-token CE
- 图像补全：已知 token 当 prefix，自回归预测剩余

### 加分点
- EMA 更新 codebook（替代第二项损失）防 codebook collapse
- 采样时 top-k / top-p 控制多样性
- top-down 自回归（先低分辨率后高分辨率）→ 更长上下文

### 易错
- ⚠️ Causal mask 方向：是**禁止看未来**，即 `mask[i, j>i] = -inf`（上三角为 -inf）
- codebook collapse → 调小 lr、加 EMA、初始化用 K-means
- 量化前后 shape 要一致：[B, C, H, W]
- `nn.Embedding` 的输入是 long type，别忘 `.long()`

---

## 4. 范式 C：预训练 + 微调（HuggingFace）

**典型任务**：加载学院模型（GENErator-v2 / ESM）→ 加任务头 → 微调

### 标准三件套
```python
from transformers import AutoModel, AutoTokenizer
backbone = AutoModel.from_pretrained(MODEL_PATH)
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)

class TaskHead(nn.Module):
    def __init__(self, hidden, out_dim, task='reg'):
        super().__init__()
        self.proj = nn.Sequential(
            nn.Linear(hidden, hidden), nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden, out_dim))
        self.task = task
    def forward(self, h):  # h: [B, L, H]
        pooled = h.mean(1)  # 或 h[:,0]（CLS token）
        return self.proj(pooled)
```

### 冻结策略（重要）
```python
# 完全冻结 backbone
for p in backbone.parameters(): p.requires_grad = False
# 只训 head
optim = torch.optim.AdamW(head.parameters(), lr=1e-4)

# 或：解冻最后 N 层
for name, p in backbone.named_parameters():
    if 'layer.11' in name or 'layer.10' in name or 'pooler' in name:
        p.requires_grad = True
```

### LoRA（若允许）
```python
from peft import LoraConfig, get_peft_model
cfg = LoraConfig(r=8, lora_alpha=16, target_modules=["query","value"], lora_dropout=0.1)
model = get_peft_model(backbone, cfg)
model.print_trainable_parameters()
```

### 训练循环
```python
for epoch in range(EPOCHS):
    for batch in loader:
        ids = batch['input_ids'].cuda()
        mask = batch['attention_mask'].cuda()
        y = batch['labels'].cuda()
        h = backbone(ids, attention_mask=mask).last_hidden_state
        pred = head(h)
        loss = F.mse_loss(pred, y) if task=='reg' else F.cross_entropy(pred, y)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
```

### 加分点
- LoRA / QLoRA（4-bit 量化 backbone + LoRA）显存友好
- 不同 pooling 策略对比：mean / [CLS] / last token / attention pooling
- 学习率分层：head 大 lr，backbone 小 lr
- Warmup + cosine decay
- 早停（监控 val metric）

### 易错
- DNA 模型可能用 char-level tokenizer，不能直接当 BERT
- attention_mask 一定要传，padding token 不能进 mean pool
- `output_hidden_states=True` 才能拿中间层
- backbone eval 模式：`backbone.eval()` 避免 dropout/BN 随机性

---

## 5. 范式 D：Agentic RAG（检索增强 + Agent 推理）

**流程**：query → 检索 (BM25 + Dense 混合) → 构 prompt → LLM 推理 → （若需多跳）再检索

### 混合检索分数
$$s = \alpha \cdot s_{\text{BM25}} + (1-\alpha) \cdot s_{\text{Dense}}, \quad \alpha \in [0.3, 0.7]$$

Dense 用 SentenceTransformer 或 BGE 算余弦。

### 代码骨架
```python
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

class HybridRetriever:
    def __init__(self, docs, model_name='BAAI/bge-small-en'):
        self.docs = docs
        self.bm25 = BM25Okapi([d.split() for d in docs])
        self.encoder = SentenceTransformer(model_name)
        self.doc_emb = self.encoder.encode(docs, convert_to_tensor=True)
    def retrieve(self, query, k=5, alpha=0.5):
        bm25_scores = self.bm25.get_scores(query.split())
        bm25_scores = (bm25_scores - bm25_scores.min()) / (bm25_scores.max() - bm25_scores.min() + 1e-9)
        q_emb = self.encoder.encode(query, convert_to_tensor=True)
        dense_scores = torch.cosine_similarity(q_emb.unsqueeze(0), self.doc_emb).cpu().numpy()
        dense_scores = (dense_scores - dense_scores.min()) / (dense_scores.max() - dense_scores.min() + 1e-9)
        final = alpha * bm25_scores + (1-alpha) * dense_scores
        top_idx = final.argsort()[::-1][:k]
        return [(self.docs[i], final[i]) for i in top_idx]
```

### Agent 循环
```python
def agent_solve(query, retriever, llm, max_hops=3):
    history = []
    for hop in range(max_hops):
        docs = retriever.retrieve(query, k=3)
        ctx = "\n".join([f"[{i}] {d}" for i,(d,_) in enumerate(docs)])
        prompt = f"""Context:
{ctx}

Question: {query}

If you can answer now, output "ANSWER: <your answer>".
If you need more info, output "NEED: <new query>".
Think step by step."""
        resp = llm(prompt)
        history.append({'hop': hop, 'query': query, 'docs': [d for d,_ in docs], 'resp': resp})
        if resp.startswith("ANSWER:"):
            return resp[7:].strip(), history
        elif resp.startswith("NEED:"):
            query = resp[5:].strip()
        else:
            return resp, history  # fallback
    return resp, history
```

### 评估
- **EM (Exact Match)**：预测答案 == ground truth
- **F1 (token-level)**：bag of words 的 P/R 调和均值

### 加分点
- Reranker（Cross-Encoder）二次精排
- Query expansion / decomposition（把复杂问题拆成子问题）
- Self-RAG：模型自己判断是否需要检索
- 日志要写全：每跳 query / docs / response，便于复盘

### 易错
- BM25 分数和 cosine 量纲不同，**必须 min-max 归一化**再加权
- Embedding 模型加载慢，缓存到 disk
- LLM 输出可能不严格遵循 "ANSWER:/NEED:" 格式 → 加正则解析 + fallback
- 多跳查询要防死循环（限 max_hops）

---

## 6. 工程速查

### 6.1 PyTorch 训练三件套
```python
loss.backward()
optimizer.step()
optimizer.zero_grad()  # 一定别忘
```

### 6.2 CUDA OOM 应急（按优先级）
1. 降 batch_size 一半
2. `torch.cuda.empty_cache()`
3. Mixed precision：`from torch.cuda.amp import autocast, GradScaler`
4. Gradient accumulation：`loss/n; loss.backward()`，每 n 步 step
5. 检查是否漏 `.detach()` 或 `torch.no_grad()`
6. Gradient checkpointing：`torch.utils.checkpoint`

### 6.3 维度对不齐 → 强制 print
```python
print(f"x={x.shape}, mask={mask.shape}, pred={pred.shape}, y={y.shape}")
```
**常错**：PyTorch 默认 NCHW（不是 NHWC），HF 默认 [B, L, H]。

### 6.4 复现确定性
```python
torch.manual_seed(42)
np.random.seed(42)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
```

### 6.5 SSH 远程开发机
```bash
ssh dev
nvidia-smi              # 看 GPU
watch -n 1 nvidia-smi   # 实时
tmux new -s exam        # 防 ssh 断开训练丢
```

### 6.6 数据加载
```python
loader = DataLoader(ds, batch_size=B, shuffle=True, num_workers=4, pin_memory=True)
```
**别**：`num_workers=0`（慢）；忘了 `pin_memory=True`（GPU 慢）

---

## 7. 时间分配（9:00-17:00 全天）

| 时段 | 任务 | 备注 |
|---|---|---|
| 9:00-9:30 | 通读 4 题题面，标必拿/可选/放弃 | 每题先看输入输出 |
| 9:30-12:00 | 攻第 1、2 题 | 优先签到题，保证拿满 |
| 12:00-13:00 | 午饭 + 短缓冲 | 不饭桌讨论 |
| 13:00-15:30 | 第 3 题（微调/RAG 费时） | 数据加载先跑通再训 |
| 15:30-16:30 | 第 4 题 + 写 README | README **算分** |
| 16:30-17:00 | 最终检查 + 提交 | 别忘点提交按钮 |

---

## 8. 提交前 Checklist

- [ ] 每题 `python main.py` 跑通**不报错**
- [ ] README 写清：方法选择 + 关键超参 + 结果数字
- [ ] 加分项的 trade-off 在 README 解释
- [ ] 日志/checkpoint 文件名规范
- [ ] 删除调试 print 和大文件输出
- [ ] zip 前 `ls -la` 确认
- [ ] **确认点了提交按钮**

---

## 9. 关键陷阱

1. **Causal mask 方向**：禁止看未来 → 上三角为 -inf（不是下三角）
2. **VQ-VAE straight-through**：`z_q = z_e + (z_q - z_e).detach()`，别忘
3. **OptimizerStep 顺序**：backward → step → zero_grad，**不能**先 zero_grad
4. **t 维度广播**：FlowMatching 里 t 是 [B]，插值时要 `t.view(-1, 1)` 或 `t[..., None]`
5. **HF backbone**：必须传 attention_mask，否则 padding 进了 mean pool
6. **数据归一化**：BM25 和 cosine 量纲不同必须 min-max 再融合
7. **`nn.Embedding` 输入要 long**：`idx.long()`
8. **`backbone.eval()`**：推断时调用，避免 dropout/BN 噪声
9. **采样时 `@torch.no_grad()`**：否则爆显存
10. **CIFAR-10 通道顺序**：NCHW（不是 TF 的 NHWC）

---

## 10. 我（Claude）的工作约束

- 我**无法**在考场期间联网（除你预先准备的本地资料）
- 涉及代码：先确认 PyTorch/HF/CUDA 版本（`pip list | grep torch`）
- 涉及题面：**让用户完整粘贴**，不要凭片段猜
- 加分项：**先把基础版本跑通**再优化
- 遇到不熟悉的范式：诚实说"超出准备范围"+ 用第一性原理推
- **不主动改框架代码以外的任何文件**，除非用户明确说改

---

*基于冬季营 4 范式分析 + PyTorch/HF 标准模板凝练。考场期间如需更新直接 Edit 本文。*

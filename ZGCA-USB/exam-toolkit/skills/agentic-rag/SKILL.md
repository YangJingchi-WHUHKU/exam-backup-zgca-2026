---
name: agentic-rag
description: 构建 Agentic RAG 多跳问答系统（vLLM + BM25 + FAISS + Self-Ask Agent）。当题面出现 "Agentic RAG / 多跳 / multi-hop / BM25 / FAISS / Qwen3-14B / vLLM / 74000 文档 / Self-Ask / ReAct / hybrid 检索 / 混合检索 / 检索增强" 时触发。2026 冬 T4 同款，押宝高复用。
---

# Agentic RAG - 多跳问答（押宝 T4 同款）

## 何时触发

题面有以下任一关键词：
- "Agentic RAG" / "RAG agent" / "智能检索"
- "多跳推理" / "multi-hop"
- "BM25" / "FAISS" / "sentence-transformers" / "混合检索" / "hybrid"
- "Qwen3-14B" / "vLLM" / "OpenAI 兼容接口"
- "74000 文档" / "documents/" / "本地知识库"
- "Self-Ask" / "ReAct" / "Planner" / "Tool-use"

## 核心模板

**主模板**: `templates/08_agentic_rag_qwen.py`
**共用工具**:
- `templates/_common/logger.py` (EventLogger，JSONL 日志)

## 现场操作步骤

### 1. 装包
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    vllm sentence-transformers rank-bm25 faiss-cpu openai numpy tqdm
```

### 2. 启动 vLLM（**先开一个 tmux 窗口让它常驻**）
```bash
vllm serve <MODEL_PATH> \
    --host 0.0.0.0 --port 8000 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.9
```
- `MODEL_PATH` 用题目给的本地路径，不要走 HF
- `--max-model-len 4096` 是省显存关键；上下文要更长改 8192
- 起好后用 `curl http://localhost:8000/v1/models` 验证

### 3. 改 CHANGE_ME（模板顶部）
- `VLLM_URL` ← 一般就 `http://localhost:8000/v1`
- `MODEL_NAME` ← 跟 vllm serve 时的模型名一致
- `DOC_DIR` ← 题目给的 documents 目录
- `INDEX_DIR` ← 你写在 /vepfs 下的索引落盘位置
- `QUESTIONS_PATH` / `PREDICTION_PATH` ← 按题目要求

### 4. 跑流程
```bash
python templates/08_agentic_rag_qwen.py --build_index   # 建索引（约 5-10 分钟 / 74000 docs）
python templates/08_agentic_rag_qwen.py --predict       # 跑 50 题
# 一条龙：
python templates/08_agentic_rag_qwen.py --build_index --predict
```

## 关键设计抉择

### 混合检索：RRF vs 加权 score

| 方案 | 优点 | 缺点 | 推荐场景 |
|---|---|---|---|
| **RRF (Reciprocal Rank Fusion)** | 不依赖 score 量纲，抗 outlier，论文工业标配 | 丢失 absolute relevance 信息 | **默认选这个**（模板用） |
| 加权 score (0.5*bm25_norm + 0.5*cos) | 保留连续 score | BM25 score 量纲飘，需要先归一化（min-max / z-score），调试坑多 | 题目明确要求加权融合时再用 |

RRF 公式：`score(d) = Σ 1/(k + rank_i(d))`，k 默认 60。

### Agent 范式选择

| 范式 | 何时用 | 实现复杂度 |
|---|---|---|
| **Self-Ask** | 多跳问答（2-4 跳） | 低，模板用 |
| **ReAct** | 需要 thought-action-observation 循环、可能调多种 tool | 中 |
| **Plan-and-Execute** | 任务很长、需要全局规划 | 高 |

**考场首选 Self-Ask**：
- 一次性 decompose 出所有子问题，避免多轮 LLM 调用累积错误
- 每个子问题独立检索，控制复杂度
- 失败可降级到单跳 RAG

### 多跳分解 Prompt 模板（在模板里已写好）

```
You are a research assistant. To answer the user question, decide whether
it can be answered directly with one retrieval, or it needs to be decomposed
into 2-N simpler sub-questions that can be answered in sequence.

Output STRICT JSON, no markdown:
{"need_decompose": true/false, "sub_questions": ["q1", "q2", ...]}

Question: <user question>
```

**坑提示**：LLM 输出 JSON 经常带 markdown ```json fence，模板里用正则抽 `{...}` 兜底，不要直接 `json.loads`。

## "unknown" 兜底策略（评分关键）

题目明确说：**证据不足时输出 "unknown"，不要瞎猜**。

模板在以下时机输出 unknown：
1. sub-answer LLM 看完文档说 "unknown"
2. 任何子问题答案为 unknown → 最终 unknown
3. 任何 step 异常（JSON parse 失败 / vLLM 请求超时） → unknown

宁可错杀也不要瞎猜：扣分往往是猜错答案，而不是 unknown。

## 日志 JSONL 规范（评分关键）

每条 event 一行 JSON，字段：

| event_type | 必带字段 |
|---|---|
| `decompose` | qid, question, decomposed_queries, llm_raw_response |
| `subhop` | qid, hop, sub_question, retrieved_doc_ids, retrieved_scores, docs, prompt, llm_raw_response, sub_answer |
| `synthesize` | qid, question, prompt, llm_raw_response, final_answer |
| `final` | qid, question, final_answer |
| `error` | qid, question, error |

通用字段：`event_id` (uuid12), `timestamp`。
模板里 `EventLogger.log_event(event_type, **kwargs)` 已经帮你处理。

## 提交格式

```
/vepfs/problem4/
├── code/                       # 整个项目（含改过的 08_agentic_rag_qwen.py 和 _common/）
├── prediction.txt              # 50 行，每行一个答案（unknown 也算一行）
├── report.md                   # 架构图 + 算法说明 + 复现步骤
└── logs/agent_trace.jsonl      # Agent 推理全链路日志
```

**check 清单**：
- `wc -l prediction.txt` 必须 = 50
- 每行不含换行（如果答案包含 \n 需要 .replace("\n", " ")）
- 日志至少有 50 个 `final` event_type
- report.md 至少 4 段：架构图 / 算法 / 复现 / 超参

## 高分要点

1. **混合检索一定要双路都用** —— 题目明说 BM25+Dense，光用一个会扣工程分
2. **多跳分解必须 visible in log** —— 评分员看 JSONL 验证你真做了 Agent 而不是单跳 RAG
3. **report.md 要有真架构图** —— ASCII 或 mermaid，不能空着
4. **prediction.txt 必须 50 行** —— 错一行格式分全扣
5. **unknown 不要羞耻** —— 与其瞎猜不如保守

## 常见坑

| 坑 | 现象 | 解决 |
|---|---|---|
| vLLM 起不来 | OOM / KV cache 错 | 降 `--max-model-len` 到 2048；降 `--gpu-memory-utilization` 到 0.85 |
| JSON 解析失败 | LLM 输出带 ```json fence | 模板已用正则抽 `{...}`，别直接 json.loads |
| 索引太慢 | 74000 docs encode 卡死 | `batch_size=128` + GPU 编码；或者跳过 dense 只 BM25（降级方案） |
| FAISS 内存爆 | 74000 * 384 dim float32 = ~100MB，不会爆 | 真爆了换 `IndexIVFFlat` |
| prediction.txt 多了换行 | 答案里带 \n | 写文件前 `.replace("\n", " ").strip()` |
| 总输出 unknown | sub-answer prompt 太严 | 检查 "If the documents do not support" 这句是否过严，可放宽 |

## 备选方案（降级路径）

如果时间紧张：
1. 跳过多跳分解，直接 single-hop RAG（删 decompose 那段）
2. 跳过 dense 检索，只 BM25（删 faiss 相关代码）
3. 跳过 RRF，直接 BM25 top-K + dense top-K 求并集（次优但能跑）

## 参考资源（toolkit 内）

- `docs/04 科研实训指南.md` 第四题部分（题面 + 参考代码骨架）
- `refs/` 下如有 langchain/llama-index 文档可参考 agent 范式
- vLLM 官方 OpenAI compatible API: 标准 chat.completions 接口

## 显存预算（A100 80G）

| 组件 | 预算 |
|---|---|
| vLLM (Qwen3-14B, max-len 4096, gpu-util 0.9) | ~70 GB |
| Embedding (MiniLM-L6-v2) | ~80 MB（CPU 也行） |
| BM25 index | ~500 MB 内存 |
| FAISS Flat (74000 × 384 fp32) | ~110 MB |
| 留给 OS + 别的 | ~5 GB |

embedding 模型放 CPU 跑不会成瓶颈（74000 doc 一次性 encode 约 3-5 分钟）。

"""
Agentic RAG (Self-Ask + Hybrid Retrieval) - 押宝 2026 冬 T4 同款
==============================================================

直接对标 2026 冬 T4：Qwen3-14B (vLLM) + BM25 + FAISS + 74000 文档多跳 QA。
50 道 test 题，每题最多 N 跳分解，输出 prediction.txt + report.md + JSONL 日志。

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. VLLM_URL          - vLLM server 地址，默认 http://localhost:8000/v1
  2. MODEL_NAME        - 题目给的模型名，如 Qwen3-14B
  3. DOC_DIR           - 文档根目录，如 /vepfs-readonly/problem4/data/documents
  4. INDEX_DIR         - 索引落盘位置，如 /vepfs/problem4/indexes
  5. QUESTIONS_PATH    - 测试问题文件
  6. PREDICTION_PATH   - 提交答案路径（prediction.txt）
  7. LOG_PATH          - JSONL 日志路径
  8. EMB_MODEL         - sentence-transformers 模型，默认 all-MiniLM-L6-v2

依赖（现场 pip install）:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      vllm sentence-transformers rank-bm25 faiss-cpu openai numpy tqdm

显存预算 (A100 80G):
  Qwen3-14B + vLLM + max-model-len 4096 + gpu-mem-util 0.9 → ~70 GB
  Embedding (MiniLM-L6) 跑 CPU 或抢一个空隙跑 GPU 都行（~80MB）

vLLM 启动（先开一个 tmux 窗口跑）:
  vllm serve <MODEL_PATH> --host 0.0.0.0 --port 8000 \
      --max-model-len 4096 --gpu-memory-utilization 0.9

运行:
  python 08_agentic_rag_qwen.py --build_index           # 一次性建索引
  python 08_agentic_rag_qwen.py --predict               # 跑 50 题 → prediction.txt
  python 08_agentic_rag_qwen.py --build_index --predict # 全流程

提交:
  /vepfs/problem4/
    ├── code/                  (整个项目)
    ├── prediction.txt         (50 行)
    ├── report.md
    └── logs/agent_trace.jsonl
"""

import argparse
import json
import os
import pickle
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
from tqdm import tqdm

# 把 _common 加进 path，复用 logger
sys.path.insert(0, str(Path(__file__).parent / "_common"))
from logger import EventLogger  # noqa: E402

# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8000/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen3-14B")
DOC_DIR = os.environ.get("DOC_DIR", "/vepfs-readonly/problem4/data/documents")
INDEX_DIR = os.environ.get("INDEX_DIR", "/vepfs/problem4/indexes")
QUESTIONS_PATH = os.environ.get("QUESTIONS_PATH", "/vepfs-readonly/problem4/data/test_questions.txt")
PREDICTION_PATH = os.environ.get("PREDICTION_PATH", "/vepfs/problem4/prediction.txt")
LOG_PATH = os.environ.get("LOG_PATH", "/vepfs/problem4/logs/agent_trace.jsonl")
EMB_MODEL = os.environ.get("EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

TOP_K = 5
RRF_K = 60          # RRF 常数，论文默认 60
MAX_HOPS = 4        # 最多分解子问题数
MAX_TOKENS = 512


# ============================================================
# 2) HYBRID RETRIEVAL
# ============================================================
class HybridStore:
    """BM25 (rank_bm25) + Dense (sentence-transformers + faiss) + RRF 融合

    设计选择：
      - RRF 而非加权 score 融合 —— BM25 的 score 和 cosine 不在同一量纲，
        强行加权要先归一化，RRF 只看 rank 抗 outlier，工程上更稳。
      - faiss IndexFlatIP（cosine 需先 L2 归一）——74000 文档规模不需要 IVF/HNSW，
        Flat 一次性扫完 100ms 量级，避免参数调优坑。
    """

    def __init__(self, doc_dir: str, index_dir: str, emb_model: str):
        self.doc_dir = Path(doc_dir)
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.emb_model_name = emb_model
        self.docs: List[str] = []
        self.doc_ids: List[str] = []
        self.bm25 = None
        self.faiss_index = None
        self.encoder = None

    # ---------- 索引构建 ----------
    def _load_docs(self):
        """读所有文档。约定一个 .txt = 一个 doc。题目给什么结构改这里。"""
        files = sorted(self.doc_dir.glob("**/*.txt"))
        for fp in tqdm(files, desc="loading docs"):
            try:
                txt = fp.read_text(encoding="utf-8", errors="ignore").strip()
                if txt:
                    self.docs.append(txt)
                    self.doc_ids.append(fp.stem)
            except Exception as e:
                print(f"[WARN] skip {fp}: {e}")

    def build(self):
        from rank_bm25 import BM25Okapi
        import faiss
        from sentence_transformers import SentenceTransformer

        self._load_docs()
        print(f"[INFO] loaded {len(self.docs)} docs")

        # BM25 - 简单空白切词，中文场景换成 jieba.cut
        tokenized = [d.lower().split() for d in self.docs]
        self.bm25 = BM25Okapi(tokenized)

        # Dense
        self.encoder = SentenceTransformer(self.emb_model_name)
        embs = self.encoder.encode(
            self.docs, batch_size=64, show_progress_bar=True,
            convert_to_numpy=True, normalize_embeddings=True,
        ).astype("float32")
        dim = embs.shape[1]
        self.faiss_index = faiss.IndexFlatIP(dim)  # cosine via normalized IP
        self.faiss_index.add(embs)

        # 持久化
        with open(self.index_dir / "bm25.pkl", "wb") as f:
            pickle.dump({"bm25": self.bm25, "docs": self.docs, "doc_ids": self.doc_ids}, f)
        faiss.write_index(self.faiss_index, str(self.index_dir / "faiss.bin"))
        print(f"[OK] index saved to {self.index_dir}")

    def load(self):
        import faiss
        from sentence_transformers import SentenceTransformer

        with open(self.index_dir / "bm25.pkl", "rb") as f:
            obj = pickle.load(f)
        self.bm25 = obj["bm25"]
        self.docs = obj["docs"]
        self.doc_ids = obj["doc_ids"]
        self.faiss_index = faiss.read_index(str(self.index_dir / "faiss.bin"))
        self.encoder = SentenceTransformer(self.emb_model_name)
        print(f"[OK] loaded index: {len(self.docs)} docs")

    # ---------- 检索 ----------
    def search(self, query: str, k: int = TOP_K) -> List[Dict]:
        """返回 [{doc_id, doc, score, bm25_rank, dense_rank}, ...]"""
        # BM25
        tokens = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokens)
        bm25_top = np.argsort(-bm25_scores)[: k * 4]  # 各拉 4*k 给 RRF

        # Dense
        q_emb = self.encoder.encode(
            [query], normalize_embeddings=True, convert_to_numpy=True,
        ).astype("float32")
        _, dense_top = self.faiss_index.search(q_emb, k * 4)
        dense_top = dense_top[0]

        # RRF: score(d) = sum_i 1 / (RRF_K + rank_i(d))
        rrf = {}
        for r, idx in enumerate(bm25_top):
            rrf[int(idx)] = rrf.get(int(idx), 0.0) + 1.0 / (RRF_K + r)
        for r, idx in enumerate(dense_top):
            rrf[int(idx)] = rrf.get(int(idx), 0.0) + 1.0 / (RRF_K + r)

        # 取 top-k
        ranked = sorted(rrf.items(), key=lambda x: -x[1])[:k]
        bm25_rank_map = {int(idx): r for r, idx in enumerate(bm25_top)}
        dense_rank_map = {int(idx): r for r, idx in enumerate(dense_top)}
        out = []
        for idx, s in ranked:
            out.append({
                "doc_id": self.doc_ids[idx],
                "doc": self.docs[idx],
                "score": float(s),
                "bm25_rank": bm25_rank_map.get(idx, -1),
                "dense_rank": dense_rank_map.get(idx, -1),
            })
        return out


# ============================================================
# 3) LLM CLIENT (vLLM OpenAI-compatible)
# ============================================================
class LLMClient:
    def __init__(self, base_url: str, model: str):
        from openai import OpenAI
        # vLLM 不校验 api_key，给个占位即可
        self.client = OpenAI(base_url=base_url, api_key="EMPTY")
        self.model = model

    def chat(self, messages: List[Dict], temperature: float = 0.0,
             max_tokens: int = MAX_TOKENS) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()


# ============================================================
# 4) AGENT (Self-Ask)
# ============================================================
DECOMPOSE_PROMPT = """You are a research assistant. To answer the user question, decide whether it can be answered directly with one retrieval, or it needs to be decomposed into 2-{max_hops} simpler sub-questions that can be answered in sequence.

Output STRICT JSON, no markdown:
{{"need_decompose": true/false, "sub_questions": ["q1", "q2", ...]}}

If need_decompose is false, leave sub_questions = [original question].

Question: {question}
"""

SUBANSWER_PROMPT = """You are answering a sub-question using ONLY the retrieved documents below.
If the documents do not support a clear answer, reply exactly with: unknown

Documents:
{docs}

Sub-question: {sub_q}

Answer (concise, one short sentence):
"""

FINAL_PROMPT = """You are synthesizing a final answer from sub-answers.
If any required sub-answer is "unknown" and is essential to the question, reply exactly with: unknown
Otherwise give a short, direct answer with no explanation.

Original question: {question}

Sub-question / sub-answer pairs:
{pairs}

Final answer (one short phrase, no punctuation at end if a name/entity):
"""


def safe_json_parse(text: str) -> Dict:
    """LLM 输出 JSON 不保证干净。先抽 {...} 再 json.loads。"""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"need_decompose": False, "sub_questions": []}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"need_decompose": False, "sub_questions": []}


class RAGAgent:
    def __init__(self, store: HybridStore, llm: LLMClient, logger: EventLogger):
        self.store = store
        self.llm = llm
        self.logger = logger

    def answer(self, question: str, qid: int) -> str:
        # ---- 1. decompose ----
        decomp_raw = self.llm.chat([
            {"role": "user", "content": DECOMPOSE_PROMPT.format(
                question=question, max_hops=MAX_HOPS)},
        ])
        plan = safe_json_parse(decomp_raw)
        sub_qs: List[str] = plan.get("sub_questions") or [question]
        if not sub_qs:
            sub_qs = [question]
        sub_qs = sub_qs[:MAX_HOPS]

        self.logger.log_event(
            "decompose", qid=qid, question=question,
            decomposed_queries=sub_qs, llm_raw_response=decomp_raw,
        )

        # ---- 2. sub-answer loop ----
        pairs: List[Tuple[str, str]] = []
        for hop, sq in enumerate(sub_qs):
            hits = self.store.search(sq, k=TOP_K)
            docs_block = "\n\n".join(
                f"[doc {h['doc_id']}] {h['doc'][:600]}" for h in hits
            )
            sub_prompt = SUBANSWER_PROMPT.format(docs=docs_block, sub_q=sq)
            sa_raw = self.llm.chat([{"role": "user", "content": sub_prompt}])

            self.logger.log_event(
                "subhop", qid=qid, hop=hop, sub_question=sq,
                retrieved_doc_ids=[h["doc_id"] for h in hits],
                retrieved_scores=[h["score"] for h in hits],
                docs=[h["doc"][:300] for h in hits],
                prompt=sub_prompt,
                llm_raw_response=sa_raw,
                sub_answer=sa_raw,
            )
            pairs.append((sq, sa_raw))

        # ---- 3. synthesize ----
        if len(pairs) == 1:
            final = pairs[0][1].strip()
        else:
            pairs_block = "\n".join(f"- Q: {q}\n  A: {a}" for q, a in pairs)
            final_prompt = FINAL_PROMPT.format(question=question, pairs=pairs_block)
            final = self.llm.chat([{"role": "user", "content": final_prompt}]).strip()
            self.logger.log_event(
                "synthesize", qid=qid, question=question,
                prompt=final_prompt, llm_raw_response=final, final_answer=final,
            )

        # ---- 4. unknown 兜底 ----
        if not final or final.lower() in {"unknown", "i don't know", "n/a"}:
            final = "unknown"
        self.logger.log_event("final", qid=qid, question=question, final_answer=final)
        return final


# ============================================================
# 5) PIPELINE
# ============================================================
def cmd_build_index(args):
    store = HybridStore(args.doc_dir, args.index_dir, args.emb_model)
    store.build()


def cmd_predict(args):
    Path(args.prediction_path).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log_path).parent.mkdir(parents=True, exist_ok=True)

    store = HybridStore(args.doc_dir, args.index_dir, args.emb_model)
    store.load()
    llm = LLMClient(args.vllm_url, args.model_name)
    logger = EventLogger(args.log_path)
    agent = RAGAgent(store, llm, logger)

    with open(args.questions_path, "r", encoding="utf-8") as f:
        questions = [ln.strip() for ln in f if ln.strip()]

    answers: List[str] = []
    for i, q in enumerate(tqdm(questions, desc="answering")):
        try:
            a = agent.answer(q, qid=i)
        except Exception as e:
            logger.log_event("error", qid=i, question=q, error=str(e))
            a = "unknown"
        answers.append(a)

    with open(args.prediction_path, "w", encoding="utf-8") as f:
        for a in answers:
            f.write(a.replace("\n", " ").strip() + "\n")
    print(f"[OK] wrote {len(answers)} answers → {args.prediction_path}")
    print(f"[OK] log → {args.log_path}")


# ============================================================
# 6) REPORT (auto-write a starter; 自己再补)
# ============================================================
REPORT_TEMPLATE = """# Agentic RAG Report

## 1. 架构

```
question
   │
   ▼
[Decompose LLM]  ── Self-Ask 拆 1~{max_hops} 跳
   │
   ▼  (for each sub-question)
[HybridStore]
   ├── BM25 (rank_bm25)         top-{topk}*4
   └── Dense (MiniLM + faiss)   top-{topk}*4
        └── RRF fusion (k={rrf_k})  →  top-{topk} docs
   │
   ▼
[Sub-Answer LLM]  ── 仅用检索文档作答，证据不足 → "unknown"
   │
   ▼
[Synthesize LLM]  ── 综合所有 (sub_q, sub_a) → 最终答案
   │
   ▼
prediction.txt + JSONL 全链路日志
```

## 2. 核心算法

### 2.1 混合检索
- 稀疏: rank_bm25.BM25Okapi（空白切词，可换 jieba）
- 稠密: sentence-transformers/all-MiniLM-L6-v2 + faiss IndexFlatIP (L2 归一 = cosine)
- 融合: Reciprocal Rank Fusion, score(d) = Σ 1/(k + rank_i(d))，k={rrf_k}
- 为什么不用加权 score：BM25 score 和 cosine 不同量纲，加权要先归一化，RRF 直接按 rank 抗噪。

### 2.2 Agent 范式：Self-Ask
- decompose：LLM 一次性把 multi-hop 问题拆 1~{max_hops} 个子问题
- sub-answer：每个子问题独立检索 + 受限于检索文档作答；证据不足出 "unknown"
- synthesize：综合所有子答案；任何 essential 子答案 unknown → 最终 unknown

### 2.3 兜底
任何子链路异常或最终 LLM 输出空 → "unknown"。规避瞎猜导致的扣分。

## 3. 复现步骤

```bash
# 1. 装包
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \\
    vllm sentence-transformers rank-bm25 faiss-cpu openai numpy tqdm

# 2. 启 vLLM
vllm serve {model} --host 0.0.0.0 --port 8000 \\
    --max-model-len 4096 --gpu-memory-utilization 0.9 &

# 3. 建索引（74000 docs，约 5-10 分钟）
python code/08_agentic_rag_qwen.py --build_index

# 4. 跑 50 题
python code/08_agentic_rag_qwen.py --predict

# 5. 验证
wc -l prediction.txt   # 必须 50
head -5 prediction.txt
```

## 4. 关键超参

| 参数 | 值 | 说明 |
|---|---|---|
| TOP_K | {topk} | 每跳保留文档数 |
| MAX_HOPS | {max_hops} | 单题最大子问题数 |
| RRF_K | {rrf_k} | RRF 平滑常数（论文默认 60） |
| temperature | 0.0 | greedy，结果可复现 |
"""


def cmd_report(args):
    txt = REPORT_TEMPLATE.format(
        topk=TOP_K, max_hops=MAX_HOPS, rrf_k=RRF_K, model=args.model_name,
    )
    out = Path(args.prediction_path).parent / "report.md"
    out.write_text(txt, encoding="utf-8")
    print(f"[OK] report → {out}")


# ============================================================
# 7) CLI
# ============================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vllm_url", default=VLLM_URL)
    p.add_argument("--model_name", default=MODEL_NAME)
    p.add_argument("--doc_dir", default=DOC_DIR)
    p.add_argument("--index_dir", default=INDEX_DIR)
    p.add_argument("--questions_path", default=QUESTIONS_PATH)
    p.add_argument("--prediction_path", default=PREDICTION_PATH)
    p.add_argument("--log_path", default=LOG_PATH)
    p.add_argument("--emb_model", default=EMB_MODEL)

    p.add_argument("--build_index", action="store_true")
    p.add_argument("--predict", action="store_true")
    p.add_argument("--report", action="store_true")
    args = p.parse_args()

    if args.build_index:
        cmd_build_index(args)
    if args.predict:
        cmd_predict(args)
    if args.report or args.predict:
        cmd_report(args)


if __name__ == "__main__":
    main()

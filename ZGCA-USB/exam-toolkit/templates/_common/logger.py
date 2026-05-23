"""
JSONL + 控制台双写日志器 - 通用，Agentic RAG 题必用
==================================================

设计目标：
  - 每条 event 一行 JSON（grep 友好，pandas 一行 read_json 就能加载）
  - 自动加 timestamp + event_id (uuid4)
  - 同步打 stdout 一行 summary 方便 tail -f 看
  - 支持 with-statement，session 结束自动 flush
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class EventLogger:
    def __init__(self, path: str, also_stdout: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 'a' 模式：训练崩了重跑也不丢前面的 log
        self.fh = open(self.path, "a", encoding="utf-8")
        self.also_stdout = also_stdout

    def log_event(self, event_type: str, **kwargs: Any) -> str:
        eid = uuid.uuid4().hex[:12]
        rec = {
            "event_id": eid,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": event_type,
        }
        rec.update(kwargs)
        # default=str 兜底 numpy/torch 标量等不可序列化对象
        line = json.dumps(rec, ensure_ascii=False, default=str)
        self.fh.write(line + "\n")
        self.fh.flush()
        if self.also_stdout:
            # 只打 summary，避免长 prompt 把屏幕刷爆
            summary = {k: v for k, v in kwargs.items()
                       if k in ("qid", "hop", "sub_question", "final_answer")}
            print(f"[{event_type}] {summary}")
        return eid

    def close(self):
        try:
            self.fh.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


if __name__ == "__main__":
    with EventLogger("/tmp/_log_test.jsonl") as lg:
        lg.log_event("hello", a=1, b="x")
        lg.log_event("step", qid=0, hop=1, sub_question="who is x?", final_answer="y")
    print("written → /tmp/_log_test.jsonl")

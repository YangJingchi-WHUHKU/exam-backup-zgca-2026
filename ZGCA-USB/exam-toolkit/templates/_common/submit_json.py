"""
ESM 风格 test_result.json 提交 - 2024 秋蛋白题同款格式
=========================================================
官方格式:
{
    "name": "yourname",
    "test_result": {
        "protein_001": ["MKTVRQERLKSIVRILERSKEPVSGAQ...", 1],
        "protein_002": ["KALTARQQEVDLIRDHISQTGMPPTRA...", 0],
        ...
    }
}

注意事项（容易扣分的点）:
- key 名是 "test_result" 不是 "test_results"
- pred_label 是 int 不是 str ("1" ❌)
- 蛋白名称从 dataset 元数据获取，不能自编
- 顺序保持与 dataset 一致
"""

import json
from pathlib import Path
from typing import Iterable


def write_protein_submission(
    out_path: str,
    name: str,
    items: Iterable[tuple],   # iterable of (protein_name, sequence, pred_label_int)
) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": name,
        "test_result": {
            pname: [seq, int(pred)] for pname, seq, pred in items
        },
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[OK] wrote {len(payload['test_result'])} entries → {out_path}")


def write_generic_json(out_path: str, payload: dict) -> None:
    """通用 JSON 提交：任何题目自定义格式都走这个"""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[OK] wrote → {out_path}")


def validate_protein_submission(path: str) -> bool:
    """提交前自检：catch 最常见的格式错误"""
    with open(path, "r") as f:
        d = json.load(f)
    assert "name" in d, "缺 name 字段"
    assert "test_result" in d, "缺 test_result 字段（注意不是 test_results）"
    for k, v in d["test_result"].items():
        assert isinstance(v, list) and len(v) == 2, f"{k}: value 必须是 [seq, label] 二元组"
        assert isinstance(v[0], str), f"{k}: seq 必须是 str"
        assert isinstance(v[1], int), f"{k}: label 必须是 int, 当前是 {type(v[1])}"
    print(f"[VALID] {len(d['test_result'])} entries in {path}")
    return True


if __name__ == "__main__":
    # 自检
    mock = [
        ("protein_001", "MKTVRQERLKSIVRILERSKEPVSGAQ", 1),
        ("protein_002", "KALTARQQEVDLIRDHISQTGMPPTRA", 0),
    ]
    write_protein_submission("/tmp/test_result.json", "yangjingchi", mock)
    validate_protein_submission("/tmp/test_result.json")

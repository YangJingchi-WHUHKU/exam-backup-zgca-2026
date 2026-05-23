"""
DeepSTARR 风格 test_output.csv 提交 - 2026 冬 DNA T3 同款格式
==============================================================
官方格式:
    label1,label2
    y1_pred,y2_pred
    y1_pred,y2_pred
    ...

注意事项:
- 第一行必须是表头 "label1,label2"（不带空格、不带引号）
- 顺序必须与测试集顺序严格一致
- 不要写 index 列
- 浮点数精度建议 6 位
"""

import csv
from pathlib import Path
from typing import Iterable, Sequence


def write_regression_csv(
    out_path: str,
    rows: Iterable[Sequence[float]],   # iterable of (y1, y2, ...) 顺序与 dataset 一致
    header: Sequence[str] = ("label1", "label2"),
    precision: int = 6,
) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            assert len(row) == len(header), f"行长度 {len(row)} 不匹配表头 {len(header)}"
            w.writerow([f"{float(v):.{precision}f}" for v in row])
            n += 1
    print(f"[OK] wrote {n} rows → {out_path}")


def validate_csv(path: str, expected_n: int = None, expected_cols: int = 2) -> bool:
    with open(path, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    assert len(lines) >= 2, "至少要有表头 + 1 行"
    header = lines[0].split(",")
    assert len(header) == expected_cols, f"表头列数 {len(header)} 不匹配预期 {expected_cols}"
    if expected_n is not None:
        n = len(lines) - 1
        assert n == expected_n, f"数据行 {n} 不匹配预期 {expected_n}"
    # 抽查数据行
    for i, line in enumerate(lines[1:5]):
        parts = line.split(",")
        assert len(parts) == expected_cols, f"行 {i+1} 列数错"
        for p in parts:
            float(p)  # 必须可转 float
    print(f"[VALID] {len(lines)-1} rows in {path}")
    return True


if __name__ == "__main__":
    mock = [(3.5267, 0.8734), (1.2345, 2.5678), (-0.5, 0.0)]
    write_regression_csv("/tmp/test_output.csv", mock)
    validate_csv("/tmp/test_output.csv", expected_n=3)

#!/usr/bin/env python3
"""
批量 PDF → TXT 转换脚本
用法:
  python batch_pdf_to_txt.py <目录或单个PDF>         # 输出到同目录
  python batch_pdf_to_txt.py <目录> -o <输出目录>    # 输出到指定目录
  python batch_pdf_to_txt.py <目录> --recurse        # 递归处理子目录
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path


def extract_via_mcp(pdf_path: Path) -> str | None:
    """
    调用 mcp__pdf-reader__read_pdf（通过 Python pymupdf 同等实现）
    优先用 pymupdf (fitz)，fallback 到 pdfminer
    """
    # 方式1: pymupdf（速度最快）
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(pdf_path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)
    except ImportError:
        pass

    # 方式2: pdfminer.six
    try:
        from pdfminer.high_level import extract_text
        return extract_text(str(pdf_path))
    except ImportError:
        pass

    # 方式3: pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except ImportError:
        pass

    return None


def extract_via_mineru(pdf_path: Path, output_dir: Path) -> str | None:
    """调用 MinerU，返回 markdown 文本（用于扫描件）"""
    try:
        result = subprocess.run(
            ["mineru", "-p", str(pdf_path), "-o", str(output_dir), "-b", "pipeline"],
            capture_output=True, text=True, timeout=300
        )
        md_path = output_dir / "auto" / (pdf_path.stem + ".md")
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def convert_one(pdf_path: Path, out_path: Path, use_mineru: bool = False) -> bool:
    """转换单个 PDF，返回是否成功"""
    print(f"  处理: {pdf_path.name}", end=" ... ")

    if use_mineru:
        tmp_dir = out_path.parent / f".mineru_{pdf_path.stem}"
        text = extract_via_mineru(pdf_path, tmp_dir)
        method = "MinerU"
    else:
        text = extract_via_mcp(pdf_path)
        method = "pymupdf/pdfminer"

    if text is None:
        # fallback: 尝试另一个工具
        if use_mineru:
            text = extract_via_mcp(pdf_path)
            method = "pymupdf (fallback)"
        else:
            tmp_dir = out_path.parent / f".mineru_{pdf_path.stem}"
            text = extract_via_mineru(pdf_path, tmp_dir)
            method = "MinerU (fallback)"

    if text is None or text.strip() == "":
        print("❌ 提取失败（可能是加密PDF或纯图片PDF）")
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    size_kb = len(text.encode()) / 1024
    print(f"✅ {size_kb:.1f} KB [{method}] → {out_path.name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="批量 PDF → TXT 转换")
    parser.add_argument("input", help="PDF 文件或目录")
    parser.add_argument("-o", "--output", help="输出目录（默认同源目录）")
    parser.add_argument("-r", "--recurse", action="store_true", help="递归处理子目录")
    parser.add_argument("--mineru", action="store_true", help="强制使用 MinerU（适合扫描件）")
    parser.add_argument("--ext", default=".txt", choices=[".txt", ".md"], help="输出格式（默认 .txt）")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"错误: 路径不存在 {input_path}")
        sys.exit(1)

    # 收集所有 PDF
    if input_path.is_file():
        pdfs = [input_path]
    elif args.recurse:
        pdfs = list(input_path.rglob("*.pdf")) + list(input_path.rglob("*.PDF"))
    else:
        pdfs = list(input_path.glob("*.pdf")) + list(input_path.glob("*.PDF"))

    if not pdfs:
        print("没有找到 PDF 文件")
        sys.exit(0)

    print(f"\n📄 找到 {len(pdfs)} 个 PDF 文件\n")

    success, fail = 0, 0
    for pdf in sorted(pdfs):
        # 计算输出路径
        if args.output:
            out_dir = Path(args.output).expanduser().resolve()
            # 保持相对目录结构（递归时）
            if input_path.is_dir():
                rel = pdf.relative_to(input_path)
                out_path = out_dir / rel.with_suffix(args.ext)
            else:
                out_path = out_dir / pdf.with_suffix(args.ext).name
        else:
            out_path = pdf.with_suffix(args.ext)

        if convert_one(pdf, out_path, use_mineru=args.mineru):
            success += 1
        else:
            fail += 1

    print(f"\n✅ 完成: {success} 成功 / {fail} 失败")
    if fail > 0:
        print("  失败的文件可能需要 --mineru 参数（扫描件）或手动处理")


if __name__ == "__main__":
    main()

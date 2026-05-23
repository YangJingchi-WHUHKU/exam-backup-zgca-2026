#!/bin/bash
# 把 exam-toolkit 打包成 U 盘可用的 zip + tar.gz 双格式
# Usage: bash pack-usb.sh [output_dir]
set -e

TOOLKIT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${1:-$HOME/Desktop/ZGCA-USB}"
TIMESTAMP=$(date +%Y%m%d-%H%M)

mkdir -p "$OUT_DIR"
cd "$(dirname "$TOOLKIT_DIR")"   # 上一级，让 zip 包含 exam-toolkit/ 顶层

echo "[1/4] Cleaning pycache..."
find "$TOOLKIT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$TOOLKIT_DIR" -name "*.pyc" -delete 2>/dev/null || true

echo "[2/4] Computing size..."
echo "    toolkit total: $(du -sh exam-toolkit | cut -f1)"
echo "    refs:          $(du -sh exam-toolkit/refs 2>/dev/null | cut -f1 || echo '(empty)')"

echo "[3/4] Packing minimal zip (no refs)..."
zip -rq "$OUT_DIR/exam-toolkit-minimal-$TIMESTAMP.zip" exam-toolkit/ \
    -x "exam-toolkit/refs/*" \
    -x "exam-toolkit/refs" \
    -x "*.pyc" \
    -x "__pycache__/*"
echo "    -> $OUT_DIR/exam-toolkit-minimal-$TIMESTAMP.zip ($(du -sh "$OUT_DIR/exam-toolkit-minimal-$TIMESTAMP.zip" | cut -f1))"

echo "[4/4] Packing full zip (with refs)..."
zip -rq "$OUT_DIR/exam-toolkit-full-$TIMESTAMP.zip" exam-toolkit/ \
    -x "*.pyc" \
    -x "__pycache__/*"
echo "    -> $OUT_DIR/exam-toolkit-full-$TIMESTAMP.zip ($(du -sh "$OUT_DIR/exam-toolkit-full-$TIMESTAMP.zip" | cut -f1))"

# 也做一份 tar.gz（Linux 友好）
echo "[5/5] Also tar.gz (Linux friendly)..."
tar --exclude='__pycache__' --exclude='*.pyc' \
    -czf "$OUT_DIR/exam-toolkit-full-$TIMESTAMP.tar.gz" exam-toolkit/

# 复制 README 到 OUT_DIR 顶层
cp exam-toolkit/README-USB.md "$OUT_DIR/README-USB.md"

echo ""
echo "=== DONE ==="
ls -lh "$OUT_DIR/"
echo ""
echo "把 $OUT_DIR/ 整个目录 cp 到 U 盘即可。"

#!/bin/bash
# ============================================================
# 02-pip-install.sh — 按题型装包
# 用法：
#   chmod +x 02-pip-install.sh
#   bash 02-pip-install.sh <task_type>
#   task_type: common | rl | bio | image | rag | all
# ============================================================

set -e

TASK_TYPE="${1:-help}"

INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
TRUSTED="pypi.tuna.tsinghua.edu.cn"

pip_install() {
  echo "  pip install $@"
  pip install --index-url "$INDEX_URL" --trusted-host "$TRUSTED" "$@" || \
    pip install --index-url "https://mirrors.aliyun.com/pypi/simple/" \
                --trusted-host "mirrors.aliyun.com" "$@"
}

verify() {
  local mod=$1
  python -c "import $mod; print('  ✅ $mod', getattr($mod, '__version__', 'OK'))" 2>/dev/null || \
    echo "  ❌ $mod 导入失败"
}

case "$TASK_TYPE" in
  common)
    echo "=== [common] 必装基础包 ==="
    pip_install --upgrade pip setuptools wheel
    pip_install \
      "torch>=2.1" \
      "transformers>=4.40" \
      "datasets>=2.18" \
      "accelerate>=0.30" \
      "peft>=0.10" \
      "huggingface_hub>=0.23" \
      "tqdm" \
      "numpy<2.0" \
      "pandas" \
      "scikit-learn" \
      "scipy" \
      "matplotlib" \
      "tensorboard" \
      "safetensors" \
      "einops"
    echo "--- 验证 ---"
    verify torch
    verify transformers
    verify datasets
    verify accelerate
    verify peft
    verify numpy
    verify pandas
    ;;

  rl)
    echo "=== [rl] RL / GRPO / RLHF 相关 ==="
    pip_install \
      "trl>=0.9.0" \
      "bitsandbytes" \
      "vllm>=0.5.0" \
      "deepspeed" \
      "wandb"
    # unsloth 是可选加速，可能装不上，失败不影响主流程
    pip_install "unsloth" || echo "  ⚠️  unsloth 装失败，跳过（不影响 TRL）"
    echo "--- 验证 ---"
    verify trl
    verify vllm
    verify bitsandbytes
    ;;

  bio)
    echo "=== [bio] 蛋白质 / DNA 相关 ==="
    pip_install \
      "fair-esm" \
      "biopython" \
      "lmdb" \
      "torch_geometric" || echo "  ⚠️  torch_geometric 装失败，可跳过"
    echo "--- 验证 ---"
    verify esm
    verify Bio
    verify lmdb
    ;;

  image)
    echo "=== [image] 图像 / Diffusion 相关 ==="
    pip_install \
      "diffusers>=0.27" \
      "torchvision" \
      "Pillow" \
      "opencv-python-headless" \
      "pytorch-fid" \
      "clean-fid" || echo "  ⚠️  clean-fid 装失败，可用 pytorch-fid"
    echo "--- 验证 ---"
    verify diffusers
    verify torchvision
    verify PIL
    ;;

  rag)
    echo "=== [rag] RAG / Agent / 向量检索 ==="
    pip_install \
      "sentence-transformers>=2.7" \
      "faiss-cpu" \
      "rank-bm25" \
      "requests" \
      "openai>=1.30" \
      "httpx" \
      "tiktoken" \
      "jieba" \
      "langchain" || echo "  ⚠️  langchain 装失败，可跳过"
    echo "--- 验证 ---"
    verify sentence_transformers
    verify faiss
    verify rank_bm25
    verify openai
    ;;

  all)
    echo "=== [all] 装全部组 ==="
    bash "$0" common
    bash "$0" rl
    bash "$0" bio
    bash "$0" image
    bash "$0" rag
    ;;

  help|*)
    cat <<EOF
用法: bash 02-pip-install.sh <task_type>

task_type 可选:
  common  必装基础包（torch / transformers / datasets / peft / accelerate）
  rl      RL / GRPO（trl / vllm / bitsandbytes / deepspeed）
  bio     生物（fair-esm / biopython / lmdb）
  image   图像生成（diffusers / torchvision / pytorch-fid）
  rag     RAG（sentence-transformers / faiss-cpu / rank-bm25 / openai-client）
  all     上面全装

⚠️ 第一次进考场必须先跑 bash 02-pip-install.sh common
⚠️ 装失败会自动尝试阿里源，再不行换中科大: --index-url https://pypi.mirrors.ustc.edu.cn/simple/
EOF
    exit 1
    ;;
esac

echo
echo "========================================"
echo "  ✅ DONE: $TASK_TYPE 安装完成"
echo "========================================"

#!/bin/bash
# 把所有押宝/参考仓库 shallow-clone 到 refs/
# Usage: bash clone-refs.sh [--gitee]   # gitee 模式用国内镜像
set +e   # 单个失败不影响其他

REFS_DIR="$(cd "$(dirname "$0")" && pwd)/refs"
mkdir -p "$REFS_DIR"
cd "$REFS_DIR"

USE_GITEE=0
[[ "$1" == "--gitee" ]] && USE_GITEE=1

# 仓库列表：name|github_url|gitee_mirror_url（gitee 没有就留空）
REPOS=(
  "trl|https://github.com/huggingface/trl.git|"
  "unsloth-notebooks|https://github.com/unslothai/notebooks.git|"
  "flow_matching|https://github.com/facebookresearch/flow_matching.git|"
  "DeepSTARR|https://github.com/bernardo-de-almeida/DeepSTARR.git|"
  "finetune-esm|https://github.com/naity/finetune-esm.git|"
  "Qwen-Agent|https://github.com/QwenLM/Qwen-Agent.git|"
  "ddpo-pytorch|https://github.com/kvablack/ddpo-pytorch.git|"
  "RLfinetuning_Diffusion_Bioseq|https://github.com/masa-ue/RLfinetuning_Diffusion_Bioseq.git|"
  "DRAKES|https://github.com/ChenyuWang-Monica/DRAKES.git|"
  "VQ-VAE-PixelCNN|https://github.com/KimRass/VQ-VAE-PixelCNN.git|"
  "Genome_Factory|https://github.com/MAGICS-LAB/Genome_Factory.git|"
  "esm|https://github.com/facebookresearch/esm.git|"
  "rectified-flow-pytorch|https://github.com/lucidrains/rectified-flow-pytorch.git|"
)

clone_one() {
  local entry="$1"
  IFS='|' read -r name gh gitee <<< "$entry"
  local url="$gh"
  [[ $USE_GITEE -eq 1 && -n "$gitee" ]] && url="$gitee"

  if [[ -d "$name/.git" ]]; then
    echo "[SKIP] $name (already exists)"
    return
  fi
  echo "[CLONE] $name from $url"
  git clone --depth 1 --single-branch "$url" "$name" 2>&1 | tail -3
  if [[ $? -eq 0 ]]; then
    # 删 .git 节省空间
    rm -rf "$name/.git"
    local sz=$(du -sh "$name" 2>/dev/null | cut -f1)
    echo "[OK]   $name ($sz)"
  else
    echo "[FAIL] $name"
  fi
}

export -f clone_one
export USE_GITEE

# 并行 clone（最多 4 个同时）
printf '%s\n' "${REPOS[@]}" | xargs -P 4 -I {} bash -c 'clone_one "$@"' _ {}

echo ""
echo "=== SUMMARY ==="
ls -la "$REFS_DIR"
du -sh "$REFS_DIR"

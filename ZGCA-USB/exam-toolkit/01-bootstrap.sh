#!/bin/bash
# ============================================================
# 01-bootstrap.sh — 进考场第一件事
# 用法： chmod +x 01-bootstrap.sh && bash 01-bootstrap.sh
# 作用： 配 HF mirror / pip 镜像 / 软链 skills / 持久化到 ~/.bashrc
# ============================================================

set -e   # 任一命令出错就退出
set -u   # 未定义变量出错

echo "========================================"
echo "  中关村学院科研实训 · 环境初始化"
echo "========================================"
echo

# ===== 0. 定位 toolkit 路径 =====
TOOLKIT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "[0] Toolkit 路径: $TOOLKIT_DIR"

# ===== 1. HuggingFace 镜像 =====
echo
echo "[1] 配置 HuggingFace 镜像..."
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_ENABLE_HF_TRANSFER=0   # hf-mirror 不需要这个

# 持久化到 ~/.bashrc
if ! grep -q "HF_ENDPOINT" ~/.bashrc 2>/dev/null; then
  cat >> ~/.bashrc <<'BASHRC_EOF'

# === Added by exam-toolkit/01-bootstrap.sh ===
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_ENABLE_HF_TRANSFER=0
export TRANSFORMERS_OFFLINE=0   # 设 1 强制本地
export HF_DATASETS_OFFLINE=0
# ==============================================
BASHRC_EOF
  echo "  ✅ HF_ENDPOINT 已写入 ~/.bashrc"
else
  echo "  ⏭️  HF_ENDPOINT 已存在于 ~/.bashrc，跳过"
fi

# ===== 2. pip 镜像（清华源） =====
echo
echo "[2] 配置 pip 镜像（清华源）..."
mkdir -p ~/.pip
cat > ~/.pip/pip.conf <<'PIP_EOF'
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
extra-index-url =
    https://mirrors.aliyun.com/pypi/simple/
    https://pypi.mirrors.ustc.edu.cn/simple/
trusted-host =
    pypi.tuna.tsinghua.edu.cn
    mirrors.aliyun.com
    pypi.mirrors.ustc.edu.cn
timeout = 120

[install]
no-warn-conflicts = true
PIP_EOF
echo "  ✅ pip 配置写入 ~/.pip/pip.conf"
pip config list 2>/dev/null || echo "  ⚠️  pip config list 失败，但配置文件已写入"

# ===== 3. conda 镜像（如果有 conda）=====
echo
echo "[3] 配置 conda 镜像（如果存在）..."
if command -v conda &> /dev/null; then
  cat > ~/.condarc <<'CONDA_EOF'
channels:
  - defaults
show_channel_urls: true
default_channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
custom_channels:
  conda-forge: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  pytorch: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
CONDA_EOF
  echo "  ✅ conda 配置写入 ~/.condarc"
else
  echo "  ⏭️  conda 未安装，跳过"
fi

# ===== 4. 软链 skills 到 ~/.claude/skills =====
echo
echo "[4] 软链 skills 目录..."
mkdir -p ~/.claude
if [ -d "$TOOLKIT_DIR/skills" ]; then
  # 删除已有软链（如果指向其他位置）
  if [ -L ~/.claude/skills ] && [ "$(readlink ~/.claude/skills)" != "$TOOLKIT_DIR/skills" ]; then
    rm ~/.claude/skills
  fi
  if [ ! -e ~/.claude/skills ]; then
    ln -sfn "$TOOLKIT_DIR/skills" ~/.claude/skills
    echo "  ✅ ~/.claude/skills -> $TOOLKIT_DIR/skills"
  else
    echo "  ⏭️  ~/.claude/skills 已存在（非空目录），手动检查"
  fi
else
  echo "  ⚠️  $TOOLKIT_DIR/skills 不存在，跳过软链"
fi

# 同样链到通义千问 / Cursor 可能的位置（路径不存在就跳过）
for ide_path in ~/.cursor ~/.config/Tongyi ~/.config/lingma; do
  if [ -d "$ide_path" ]; then
    mkdir -p "$ide_path"
    ln -sfn "$TOOLKIT_DIR/skills" "$ide_path/skills" 2>/dev/null && \
      echo "  ✅ $ide_path/skills -> $TOOLKIT_DIR/skills"
  fi
done

# ===== 5. 持久化 PATH（toolkit/bin 如果存在）=====
if [ -d "$TOOLKIT_DIR/bin" ]; then
  if ! grep -q "exam-toolkit/bin" ~/.bashrc 2>/dev/null; then
    echo "export PATH=\"$TOOLKIT_DIR/bin:\$PATH\"" >> ~/.bashrc
    echo "  ✅ toolkit/bin 加入 PATH"
  fi
fi

# ===== 6. 创建个人工作目录 =====
echo
echo "[5] 准备个人工作目录..."
USER_NAME=$(whoami)
for i in 1 2 3 4; do
  mkdir -p "/vepfs/$USER_NAME/problem$i" 2>/dev/null && \
    echo "  ✅ /vepfs/$USER_NAME/problem$i" || \
    echo "  ⚠️  /vepfs/$USER_NAME/problem$i 创建失败（可能 /vepfs 不可写）"
done

# ===== 7. 验证环境 =====
echo
echo "[6] 验证环境..."
echo "--- Python ---"
python --version
echo "--- PyTorch ---"
python -c "import torch; print('torch:', torch.__version__, '| cuda:', torch.cuda.is_available(), '| device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')" 2>/dev/null || echo "  ⚠️  PyTorch 未安装或导入失败"
echo "--- GPU ---"
nvidia-smi 2>/dev/null | head -15 || echo "  ⚠️  nvidia-smi 不可用"
echo "--- 磁盘空间 ---"
df -h /vepfs 2>/dev/null | tail -1 || df -h ~ | tail -1
echo "--- HF 镜像 ---"
echo "  HF_ENDPOINT = $HF_ENDPOINT"
echo "--- pip 源 ---"
pip config list 2>/dev/null | grep "index-url" || echo "  ⚠️  pip 源未生效，手动检查 ~/.pip/pip.conf"

# ===== 8. 提示 =====
echo
echo "========================================"
echo "  ✅ DONE: bootstrap complete"
echo "========================================"
echo
echo "下一步："
echo "  1. source ~/.bashrc   （让环境变量生效）"
echo "  2. bash 02-pip-install.sh common  （装基础包）"
echo "  3. cat 00-FIRST-READ.md  （看进考场流程）"
echo

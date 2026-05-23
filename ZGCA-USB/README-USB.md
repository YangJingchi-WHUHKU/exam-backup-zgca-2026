# ZGCA Exam Toolkit - U 盘说明

## 这是什么

中关村学院夏令营 2026 科研实训考场专用 toolkit。
作者：杨镜池 / 创建时间：2026-05

## U 盘根目录

```
USB-ROOT/
├── exam-toolkit/         ← 全部内容（直接 cp -r 到考场笔记本）
│   ├── 00-FIRST-READ.md          ⭐ 进考场第一件事
│   ├── 01-bootstrap.sh           ⭐ 一键环境配置
│   ├── 02-pip-install.sh         ⭐ 按题装包
│   ├── clone-refs.sh             仅本地用，考场不用
│   ├── templates/                11 个题模板（CHANGE_ME 改完即可跑）
│   ├── skills/                   9 个 SKILL.md（Claude/Cursor 路由）
│   ├── cheatsheet/               7 个考场速查
│   ├── docs/                     2 个离线 API 文档
│   └── refs/                     ~13 个核心 repo 源码（兜底用）
└── README-USB.md         本文件
```

## 进考场后的 5 个动作

```bash
# 1) 把 toolkit 拷到考场笔记本（U 盘 → 笔记本 Desktop）
# 然后 ssh 进开发机
ssh dev

# 2) 在开发机上建你的目录
mkdir -p /vepfs/$USER/toolkit

# 3) 在考场笔记本上把 toolkit 传过去
scp -r ~/Desktop/exam-toolkit/* dev:/vepfs/$USER/toolkit/

# 4) 在开发机上一键 bootstrap
ssh dev
cd /vepfs/$USER/toolkit
bash 01-bootstrap.sh

# 5) 通读 4 题决定主攻 2-3 题，然后按题装包
bash 02-pip-install.sh rl     # RL 题
bash 02-pip-install.sh bio    # 蛋白/DNA 微调题
# ...

# 6) 改 templates/0N_*.py 顶部的 CHANGE_ME，python xxx.py 跑
```

## 文件优先级（如果时间不够全部拷贝）

| 优先级 | 文件 | 大小 |
|---|---|---|
| ⭐⭐⭐⭐⭐ | 00-FIRST-READ.md | 几 KB |
| ⭐⭐⭐⭐⭐ | 01-bootstrap.sh + 02-pip-install.sh | 几 KB |
| ⭐⭐⭐⭐⭐ | templates/ (全部) | ~200 KB |
| ⭐⭐⭐⭐⭐ | skills/ (全部) | ~80 KB |
| ⭐⭐⭐⭐ | cheatsheet/ (全部) | ~120 KB |
| ⭐⭐⭐⭐ | docs/ (全部) | ~50 KB |
| ⭐⭐⭐ | refs/ (兜底) | ~1-2 GB |

**最小可用集 ≤ 500 KB**：拷 templates + skills + cheatsheet + docs + 三个根目录脚本即可。
refs/ 只在 pip 装不上某个包时才用。

## 兜底

如果连 U 盘都被禁带 / 在考场打不开：
- 把 `templates/05a_grpo_qwen.py` 顶部的 CHANGE_ME 清单和 reward 函数模板背熟（200 行）
- 把 `cheatsheet/提交格式速查.md` 里的 5 种提交格式背熟
- 现场用国内 AI 重新生成每个模板（提示词：题面 + "按 HF 标准 AutoModel 微调 + 提交 csv/json + train.log"）

## 不要做的事

- ❌ 不要在考场跑 `clone-refs.sh`（外网不通且没意义，refs/ 已经在 U 盘里）
- ❌ 不要修改 `templates/_common/` 里的工具（其他模板依赖它们的接口）
- ❌ 不要忘记每题最后跑一遍 `skills/submission/` 里的检查清单

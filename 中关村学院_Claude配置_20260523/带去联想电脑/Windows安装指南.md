# 联想 Windows 笔记本 — Claude 安装指南

> 联想本预装一般是 Windows。这份文档给你两条路。

---

## 🎯 两条路任选其一

### Route A：**PowerShell（推荐）** ⭐
全 Windows 原生方式，把 4 个 channel 做成 `.bat` 命令，加到 PATH。

### Route B：Git Bash（备选）
装个 Git for Windows，开 Git Bash 跑 `setup.sh`。需要再调整 zsh 相关部分，**更折腾**。

---

## ✅ Route A：PowerShell 步骤（5 分钟）

### 1. 装 Node.js（如果没装）

打开浏览器去 https://nodejs.org 下载 LTS 版本（≥18）安装。

或者用 winget（PowerShell 里）：
```powershell
winget install OpenJS.NodeJS.LTS
```

装完**关闭并重开 PowerShell**让 PATH 生效。验证：
```powershell
node -v
npm -v
```

### 2. 解压配置包到桌面

把 U 盘里的 `带去联想电脑` 目录拷到 `C:\Users\<你>\Desktop\带去联想电脑`（别在 U 盘里直接跑，慢且权限可能不对）。

### 3. 用 PowerShell 进入目录

```powershell
cd $HOME\Desktop\带去联想电脑
```

### 4. 允许临时执行脚本 + 跑 setup_windows.ps1

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_windows.ps1
```

脚本会自动：
- 装 Claude Code CLI
- 创建 4 个 channel 目录（含 settings.json + API key）
- 在 `%USERPROFILE%\claude-channels\` 生成 4 个 `.bat` 命令
- 把 `claude-channels` 加进用户 PATH
- 复制全局配置到 `%USERPROFILE%\.claude\`
- 安装 34 个 skill
- 配置 codex MCP（若 codex 已装）

### 5. **关掉这个 PowerShell**，重新打开一个新窗口

PATH 变化只对新窗口生效。

### 6. 测试

```powershell
claudeaipai
```

进入 Claude 后输入：
```
你现在用的什么 model？能看到几个 skill？
```
预期回答：**opus[1m]，约 34 个 skill**。

试切 channel：
```powershell
claudemicu          # 备用 1
claudecodesuc       # 备用 2
claudeswarm         # 备用 3
```

任一 channel 内可用 `/resume` 调回历史会话（4 channel 共享）。

---

## 🌀 Route B：Git Bash 步骤（备选）

### 1. 装 Git for Windows
https://git-scm.com/download/win — 装完会自带 Git Bash。

### 2. 装 Node.js（同 Route A）

### 3. 解压配置包

`C:\Users\<你>\Desktop\带去联想电脑\`

### 4. **以管理员身份**右键打开 Git Bash

cd 到目录：
```bash
cd ~/Desktop/带去联想电脑
```

### 5. 跑 setup.sh

```bash
bash setup.sh
```

**注意**：`setup.sh` 原本是为 Mac/Linux 写的，profile_bundle/install.sh 里有 `#!/bin/zsh` 头。Git Bash 没有 zsh，可能报错。如果报错就走 Route A。

---

## 🆘 常见问题

### Q: `node -v` 不识别
A: Node 装完没重开终端，关掉所有 PowerShell 窗口再开新的。

### Q: `Set-ExecutionPolicy` 报错
A: 用 PowerShell 7 或者：
```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
```

### Q: 装完后输入 `claudeaipai` 提示 "命令未找到"
A: 重开 PowerShell 让 PATH 生效。或者临时用：
```powershell
$env:Path += ";$HOME\claude-channels"
claudeaipai
```

### Q: `claude` 命令是有的但 channel 命令没生效
A: 看一下：
```powershell
ls $HOME\claude-channels\
```
应该有 4 个 `.bat` 文件。如果没有，重跑 `setup_windows.ps1` 的 Step 3 部分。

### Q: 4 个 channel 全都连不上
A: 校园网代理。试一下：
```powershell
$env:HTTPS_PROXY = "http://代理:端口"
claudeaipai
```

### Q: skill 数对不上（不到 34）
A: 看一下：
```powershell
ls $HOME\.config\agents\skills\ | Measure-Object
```
如果 < 34，手动跑：
```powershell
Get-ChildItem -Directory skills_全量备份 | ForEach-Object {
    Copy-Item -Recurse -Force $_.FullName "$HOME\.config\agents\skills\$($_.Name)"
}
```

### Q: Windows 软链失败 / 没管理员权限
A: 默认 fallback 是直接复制（占双倍空间但稳）。不用管。

---

## 📍 关键路径速查

| 内容 | Windows 路径 |
|---|---|
| Claude Code | `C:\Users\<你>\AppData\Roaming\npm\node_modules\@anthropic-ai\claude-code\` |
| 全局指令 | `C:\Users\<你>\.claude\CLAUDE.md` |
| Channel 配置 | `C:\Users\<你>\.claude_aipai\settings.json` 等 |
| 34 个 skill | `C:\Users\<你>\.config\agents\skills\` |
| Channel 命令 | `C:\Users\<你>\claude-channels\*.bat` |
| MCP 配置 | `C:\Users\<你>\.claude.json` |

---

## 🆘 实在搞不定的紧急方案

如果 Route A 和 B 都失败：

1. **手动安装 Claude Code**：
   ```
   npm install -g @anthropic-ai/claude-code
   ```

2. **手动设环境变量临时用**：
   ```powershell
   $env:ANTHROPIC_BASE_URL = "https://api.aipaibox.com/"
   $env:ANTHROPIC_AUTH_TOKEN = "sk-N8c1EnaseEaN8GVJkDmVybSPlghJ7G5FQZMFcTKZmRoHjVML"
   claude
   ```

这样不带 skill 也能跑起来，应急。

---

*最后更新：2026-05-23*

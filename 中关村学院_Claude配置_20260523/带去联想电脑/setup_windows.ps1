# ====================================================================
# 中关村学院科研实训 — 联想 Windows 笔记本 Claude 配置脚本
# 用法（PowerShell 管理员）：
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup_windows.ps1
# ====================================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

function Step($n, $msg) { Write-Host "`n=== Step $n  $msg ===" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Err($msg)  { Write-Host "[ERR] $msg" -ForegroundColor Red }

# --------------------------------------------------------------------
Step "0/6" "前置检查"
# --------------------------------------------------------------------
$nodeVer = $null
try { $nodeVer = (node -v) } catch { }
if (-not $nodeVer) {
    Err "未找到 Node.js。请先到 https://nodejs.org 下载安装 LTS 版本（≥18），完成后重跑本脚本。"
    Write-Host "或在 PowerShell 里跑：winget install OpenJS.NodeJS.LTS"
    exit 1
}
Ok "Node $nodeVer"

# --------------------------------------------------------------------
Step "1/6" "安装 Claude Code CLI"
# --------------------------------------------------------------------
$hasClaude = $null
try { $hasClaude = (Get-Command claude -ErrorAction SilentlyContinue) } catch { }
if (-not $hasClaude) {
    npm install -g "@anthropic-ai/claude-code"
    Ok "Claude Code 安装完成"
} else {
    Ok "claude 已存在: $($hasClaude.Source)"
}

# --------------------------------------------------------------------
Step "2/6" "创建 4 个 channel 配置目录"
# --------------------------------------------------------------------
$profilesJson = Get-Content "configs\profile_bundle\profiles.json" -Raw | ConvertFrom-Json

foreach ($p in $profilesJson.profiles) {
    $cmd = $p.command            # 例: claudeaipai
    $suffix = $cmd -replace '^claude',''   # 例: aipai
    $profileDir = "$env:USERPROFILE\.claude_$suffix"
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

    # 写 settings.json（含 env + model）
    $settings = @{
        env = @{
            ANTHROPIC_BASE_URL = $p.base_url
            ANTHROPIC_AUTH_TOKEN = $p.api_key
        }
        model = $p.model
        permissions = @{ defaultMode = "bypassPermissions" }
        effortLevel = "high"
        includeCoAuthoredBy = $false
        skipDangerousModePermissionPrompt = $true
    }
    $settings | ConvertTo-Json -Depth 5 | Set-Content -Path "$profileDir\settings.json" -Encoding UTF8
    Ok "$cmd → $profileDir"
}

# --------------------------------------------------------------------
Step "3/6" "生成 4 个 channel 命令（.bat 包装器）"
# --------------------------------------------------------------------
$BinDir = "$env:USERPROFILE\claude-channels"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

foreach ($p in $profilesJson.profiles) {
    $cmd = $p.command
    $suffix = $cmd -replace '^claude',''
    $batContent = @"
@echo off
set "CLAUDE_CONFIG_DIR=%USERPROFILE%\.claude_$suffix"
set "CLAUDE_CHANNEL_NAME=Claude $suffix"
claude --setting-sources=user %*
"@
    Set-Content -Path "$BinDir\$cmd.bat" -Value $batContent -Encoding ASCII
    Ok "$BinDir\$cmd.bat"
}

# 把 BinDir 加到用户 PATH
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$userPath;$BinDir", "User")
    Ok "已把 $BinDir 加入用户 PATH（**重开终端**才生效）"
} else {
    Ok "$BinDir 已在 PATH"
}

# --------------------------------------------------------------------
Step "4/6" "复制全局配置 (~/.claude/)"
# --------------------------------------------------------------------
$ClaudeHome = "$env:USERPROFILE\.claude"
New-Item -ItemType Directory -Force -Path $ClaudeHome | Out-Null

Copy-Item -Force "configs\settings.json" "$ClaudeHome\settings.json"
Copy-Item -Force "configs\CLAUDE.md" "$ClaudeHome\CLAUDE.md"
foreach ($d in @("rules", "docs", "commands")) {
    if (Test-Path "$ClaudeHome\$d") { Remove-Item -Recurse -Force "$ClaudeHome\$d" }
    Copy-Item -Recurse -Force "configs\$d" "$ClaudeHome\$d"
}
Ok "settings / CLAUDE.md / rules / docs / commands 已部署"

# --------------------------------------------------------------------
Step "5/6" "安装 34 个 Skill"
# --------------------------------------------------------------------
$SkillsConfigDir = "$env:USERPROFILE\.config\agents\skills"
$SkillsClaudeDir = "$ClaudeHome\skills"
New-Item -ItemType Directory -Force -Path $SkillsConfigDir | Out-Null
New-Item -ItemType Directory -Force -Path $SkillsClaudeDir | Out-Null

$count = 0
Get-ChildItem -Directory "skills_全量备份" | ForEach-Object {
    $name = $_.Name
    $dst = "$SkillsConfigDir\$name"
    if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
    Copy-Item -Recurse -Force $_.FullName $dst

    # 软链或复制到 ~/.claude/skills
    $linkDst = "$SkillsClaudeDir\$name"
    if (Test-Path $linkDst) { Remove-Item -Recurse -Force $linkDst }
    # Windows 软链需要管理员或开发者模式；fallback 用复制
    try {
        New-Item -ItemType SymbolicLink -Path $linkDst -Target $dst -ErrorAction Stop | Out-Null
    } catch {
        Copy-Item -Recurse -Force $dst $linkDst
    }
    $count++
}
Ok "$count 个 skill 已安装到 $SkillsConfigDir 和 $SkillsClaudeDir"

# --------------------------------------------------------------------
Step "6/6" "配置 codex MCP（可选）"
# --------------------------------------------------------------------
$hasCodex = $null
try { $hasCodex = (Get-Command codex -ErrorAction SilentlyContinue) } catch { }
if ($hasCodex) {
    $mcpAdd = (Get-Content "configs\mcp_servers.json" -Raw | ConvertFrom-Json).mcpServers
    $mainPath = "$env:USERPROFILE\.claude.json"
    if (Test-Path $mainPath) {
        $main = Get-Content $mainPath -Raw | ConvertFrom-Json
    } else {
        $main = @{}
    }
    if (-not $main.mcpServers) { $main | Add-Member -NotePropertyName mcpServers -NotePropertyValue (@{}) -Force }
    foreach ($prop in $mcpAdd.PSObject.Properties) {
        $main.mcpServers | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value -Force
    }
    $main | ConvertTo-Json -Depth 10 | Set-Content -Path $mainPath -Encoding UTF8
    Ok "codex MCP 已并入 ~/.claude.json"
} else {
    Warn "未找到 codex CLI，跳过 MCP（不影响主流程）"
}

# ====================================================================
Write-Host "`n" -NoNewline
Write-Host "========================================================" -ForegroundColor Green
Write-Host " ✅ 配置完成 ！" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host @"

下一步：
  1. ★ 关闭这个 PowerShell 窗口，重新打开一个新窗口（让 PATH 生效）
  2. 在新窗口输入测试：
       claudeaipai
     或备用：
       claudemicu / claudecodesuc / claudeswarm

  3. 进入 Claude 后输入：
       > 你现在用的什么 model？能看到几个 skill？
     预期：opus[1m]，约 34 个 skill

关键路径：
  $env:USERPROFILE\.claude\CLAUDE.md           全局指令（含 Karpathy 4 原则）
  $env:USERPROFILE\.config\agents\skills\      34 个 skill
  $env:USERPROFILE\claude-channels\            4 个 channel .bat 包装器
  $env:USERPROFILE\.claude_aipai\settings.json （+micu/codesuc/swarm）

⚠️ 注意：
  - 笔试 / 机试期间禁用 Claude
  - 4 个 channel 任一不通时立即换备用

"@ -ForegroundColor Cyan

@echo off
chcp 65001 >nul
title 中关村学院 Claude 一键安装
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   中关村学院 - Claude 一键安装
echo ============================================================
echo.
echo 本脚本会自动：
echo   1. 装 Node.js (如果没装)
echo   2. 装 Claude Code CLI
echo   3. 配置 4 个 channel (aipai / micu / codesuc / swarm)
echo   4. 创建 claudeaipai / claudemicu / claudecodesuc / claudeswarm 命令
echo.
echo 按任意键开始...
pause >nul

REM ============================================================
REM Step 1: Node.js
REM ============================================================
echo.
echo [Step 1/4] 检查 Node.js...
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo   未检测到 Node.js，尝试 winget 安装...
    winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
    if !errorlevel! neq 0 (
        echo.
        echo  X winget 失败。请手动装 Node.js LTS：
        echo    https://nodejs.org
        echo    装完关掉这个窗口，重新双击 一键安装.bat
        pause
        exit /b 1
    )
    echo  ! Node.js 已装，需重新打开窗口让 PATH 生效。
    echo  ! 关掉此窗口后再次双击 一键安装.bat
    pause
    exit /b 0
)
echo  OK Node.js:
node -v

REM ============================================================
REM Step 2: Claude Code CLI
REM ============================================================
echo.
echo [Step 2/4] 安装 Claude Code CLI...
where claude >nul 2>nul
if %errorlevel% neq 0 (
    call npm install -g @anthropic-ai/claude-code
    if !errorlevel! neq 0 (
        echo  X npm 安装失败。常见原因：
        echo    - 网络问题：试 npm config set registry https://registry.npmmirror.com
        echo    - 权限：右键 BAT 选 "以管理员身份运行"
        pause
        exit /b 1
    )
)
echo  OK Claude Code 安装完成
call claude --version 2>nul

REM ============================================================
REM Step 3: 4 个 channel 配置（关键步骤，必须成功）
REM ============================================================
echo.
echo [Step 3/4] 配置 4 个 channel...

REM 用 PowerShell 写 JSON 文件（cmd 自己生成中文 JSON 容易乱）
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$profiles = @(" ^
"@{ name='aipai';    url='https://api.aipaibox.com/';    key='sk-N8c1EnaseEaN8GVJkDmVybSPlghJ7G5FQZMFcTKZmRoHjVML' }," ^
"@{ name='micu';     url='https://www.micuapi.ai';       key='sk-PaBaIPnh3zasiuPmzW9xohKKfueW6ykRd03sPwFwHXxthXbC' }," ^
"@{ name='codesuc';  url='https://main-new.codesuc.top/'; key='sk-n5LlW8Pm21b1ENgSCMH0Muvx6eeFvyV3MfXn7vDxxxxxxxxx' }," ^
"@{ name='swarm';    url='https://byteswarm.ai/claude';  key='cr_9vb-z9nLfpKJEwSzbFTTfnADxzPxxxxxxxxxxxxxxxxxxxxxx' }" ^
");" ^
"foreach ($p in $profiles) {" ^
"  $dir = \"$env:USERPROFILE\.claude_$($p.name)\";" ^
"  New-Item -ItemType Directory -Force -Path $dir | Out-Null;" ^
"  $s = @{ env = @{ ANTHROPIC_BASE_URL = $p.url; ANTHROPIC_AUTH_TOKEN = $p.key }; model = 'opus[1m]'; permissions = @{ defaultMode = 'bypassPermissions' }; effortLevel = 'high'; includeCoAuthoredBy = $false; skipDangerousModePermissionPrompt = $true };" ^
"  $s | ConvertTo-Json -Depth 5 | Set-Content -Path \"$dir\settings.json\" -Encoding UTF8;" ^
"  Write-Host \"  OK $($p.name): $dir\";" ^
"}"

if %errorlevel% neq 0 (
    echo  X channel 配置失败。可能是 PowerShell 被禁。手动跑 setup_windows.ps1
    pause
    exit /b 1
)

REM ============================================================
REM 关键：从 profile_bundle/profiles.json 读真实 key 覆盖上面占位
REM (上面 PowerShell inline 里 codesuc/swarm 的 key 是截断版，从 JSON 文件读完整版)
REM ============================================================
if exist "configs\profile_bundle\profiles.json" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$cfg = Get-Content 'configs\profile_bundle\profiles.json' -Raw | ConvertFrom-Json;" ^
    "foreach ($p in $cfg.profiles) {" ^
    "  $suffix = $p.command -replace '^claude','';" ^
    "  $dir = \"$env:USERPROFILE\.claude_$suffix\";" ^
    "  $s = @{ env = @{ ANTHROPIC_BASE_URL = $p.base_url; ANTHROPIC_AUTH_TOKEN = $p.api_key }; model = $p.model; permissions = @{ defaultMode = 'bypassPermissions' }; effortLevel = 'high'; includeCoAuthoredBy = $false; skipDangerousModePermissionPrompt = $true };" ^
    "  $s | ConvertTo-Json -Depth 5 | Set-Content -Path \"$dir\settings.json\" -Encoding UTF8;" ^
    "  Write-Host \"  Updated $suffix with full key from profiles.json\";" ^
    "}"
)

REM ============================================================
REM Step 4: 创建 4 个 .bat 命令并加到 PATH
REM ============================================================
echo.
echo [Step 4/4] 创建 4 个命令 (claudeaipai 等) 并加到 PATH...

set "BINDIR=%USERPROFILE%\claude-channels"
if not exist "%BINDIR%" mkdir "%BINDIR%"

REM 生成 4 个 .bat
for %%c in (aipai micu codesuc swarm) do (
    (
        echo @echo off
        echo set "CLAUDE_CONFIG_DIR=%%USERPROFILE%%\.claude_%%c"
        echo set "CLAUDE_CHANNEL_NAME=Claude %%c"
        echo claude --setting-sources=user %%*
    ) > "%BINDIR%\claude%%c.bat"
    echo  OK claude%%c.bat
)

REM 把 BINDIR 加到用户 PATH (永久)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$p = [Environment]::GetEnvironmentVariable('PATH','User');" ^
"if ($p -notlike '*%BINDIR%*') { [Environment]::SetEnvironmentVariable('PATH', ($p + ';%BINDIR%'), 'User'); Write-Host '  OK PATH 已更新' } else { Write-Host '  OK PATH 已存在' }"

REM ============================================================
REM 完成
REM ============================================================
echo.
echo ============================================================
echo   ✓ 核心配置完成
echo ============================================================
echo.
echo 现在可以用的命令（关掉此窗口重新打开 PowerShell 或 cmd 后生效）：
echo.
echo    claudeaipai      主用
echo    claudemicu       备用 1
echo    claudecodesuc    备用 2
echo    claudeswarm      备用 3
echo.
echo 测试方法：
echo    1. 关掉这个窗口
echo    2. 重开 PowerShell 或 cmd
echo    3. 输入 claudeaipai
echo.
echo ------------------------------------------------------------
echo  可选: 安装 34 个 skill (推荐，但不影响基础使用)
echo ------------------------------------------------------------
echo.
choice /c YN /n /m "  现在安装 34 个 skill 吗? [Y=安装, N=跳过]: "
if errorlevel 2 goto :skip_skills

echo.
echo 安装 skill 中...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$src = '%~dp0skills_全量备份';" ^
"$dst1 = \"$env:USERPROFILE\.config\agents\skills\";" ^
"$dst2 = \"$env:USERPROFILE\.claude\skills\";" ^
"New-Item -ItemType Directory -Force -Path $dst1 | Out-Null;" ^
"New-Item -ItemType Directory -Force -Path $dst2 | Out-Null;" ^
"$count = 0;" ^
"Get-ChildItem -Directory $src | ForEach-Object {" ^
"  $d1 = Join-Path $dst1 $_.Name;" ^
"  $d2 = Join-Path $dst2 $_.Name;" ^
"  if (Test-Path $d1) { Remove-Item -Recurse -Force $d1 };" ^
"  if (Test-Path $d2) { Remove-Item -Recurse -Force $d2 };" ^
"  Copy-Item -Recurse -Force $_.FullName $d1;" ^
"  Copy-Item -Recurse -Force $_.FullName $d2;" ^
"  $count++;" ^
"};" ^
"Write-Host \"  OK $count 个 skill 已安装\";"

REM 复制全局 CLAUDE.md
if exist "configs\CLAUDE.md" (
    if not exist "%USERPROFILE%\.claude" mkdir "%USERPROFILE%\.claude"
    copy /Y "configs\CLAUDE.md" "%USERPROFILE%\.claude\CLAUDE.md" >nul
    echo  OK ~/.claude/CLAUDE.md (含 Karpathy 4 原则)
)

:skip_skills

echo.
echo ============================================================
echo  ✓ 全部完成！关掉窗口重开终端即可用
echo ============================================================
echo.
pause
endlocal

==============================================
联想 Ubuntu Linux 笔记本 — 一键安装（无 sudo）
==============================================

学校机器不让 sudo 也没关系，下面这个脚本用 nvm 把
Node 装在你自己家目录里，全程不需要管理员密码。

【3 步搞定】

1. 把 U 盘里 "带去联想电脑" 整个目录拷到桌面
   （右键 -> 复制 -> 粘贴到 Desktop）

2. 打开终端 (Ctrl+Alt+T)，cd 到桌面那个目录：
     cd ~/Desktop/带去联想电脑

3. 跑脚本：
     bash linux一键安装_无sudo.sh

   按提示走（中间会问要不要装 34 个 skill，建议 Y）

4. 装完跑：
     source ~/.bashrc
     claudeaipai

==============================================
4 个 channel 命令：
  claudeaipai     主用
  claudemicu      备用 1
  claudecodesuc   备用 2
  claudeswarm     备用 3
==============================================

【备份方案】
  - linux一键安装_无sudo.sh  ← 无 sudo 推荐
  - setup.sh                  ← Mac/Linux 通用（要 zsh）
  - 一键安装.bat              ← Windows 用（这台不是）
  - setup_windows.ps1         ← Windows 用（这台不是）

【网络问题排障】
  - nvm 下载失败：试手机热点临时联网装一次
  - npm 慢：脚本已自动用 npmmirror.com 国内源
  - 4 channel 全连不上：校园网代理，问机房


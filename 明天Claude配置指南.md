# 中关村学院科研实训 — Linux环境配置完整指南
> 写给明天负责配置的Claude。今天（2026-05-23）已完成的工作和所有经验都在这里。

---

## 一、当前状态（已完成的）

| 项目 | 状态 | 说明 |
|------|------|------|
| Claude Code 安装 | ✅ 已装 | `install_all.sh` 跑过了 |
| 5个claude channel | ✅ 全通（aipai除外） | claudemicu/codesuc/swarm/zgc 都通 |
| 5个codex wrapper | ✅ 已写入~/.bashrc | codexzgc/aipai/micu/codesuc/swarm |
| ~/.codex/config.toml | ✅ 已写 | 5个provider配置 |
| FlClash | ⚠️ 已运行但未导入订阅 | 需要导入yaml文件 |
| 外网代理 | ❌ 未配好 | 按下方步骤操作 |

**你要做的只剩一件事：给FlClash导入订阅配置。**

---

## 二、外网代理配置（FlClash）

### 文件位置
U盘里已经有：
- `EdNovasCloud_clash.yaml`（2.2MB，主用）
- `iKuuu_V2.yaml`（483KB，备用）

### 操作步骤
```
1. FlClash在系统托盘（右上角），点击图标打开
2. 左侧 Profiles → 右上角 "+" → 选"从文件导入"
3. 选U盘里的 EdNovasCloud_clash.yaml
4. 等加载完，点击该profile激活（高亮）
5. 回到Home，确认 System Proxy 开关是蓝色（ON）
6. 记得点右下角 Start（很多人忘了这步！）
```

### 验证代理是否通
```bash
curl -I --proxy http://127.0.0.1:7890 https://www.google.com
# 返回 200 或 301 = 代理通了
# 返回 403 或 connection refused = 没通
```

### 终端使用代理
```bash
# 临时（当前session有效）
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890

# 永久写入
echo 'export HTTPS_PROXY=http://127.0.0.1:7890' >> ~/.bashrc
echo 'export HTTP_PROXY=http://127.0.0.1:7890' >> ~/.bashrc
source ~/.bashrc
```

### 备用：订阅URL（需要能访问该域名）
```
iKuuu: https://nqlft.no-mad-world.club/link/x1TclfN9Y6yoI65X?clash=3
```

### ⚠️ 重要：外网对考试不是必须的
- Claude/Codex 全部走**国内中转站**，不需要代理
- GitHub可以直接访问（慢但能用）
- 外网主要用于：Google搜索、HuggingFace下载模型
- **考试能不配就不配，不要在这上面浪费时间**

---

## 三、Claude Code 5个channel

已配好，`source ~/.bashrc`后直接用：

```bash
claudeaipai    # aipaibox.com（今天测试超时，备用）
claudemicu     # micuapi.ai key1（✅ 主用）
claudecodesuc  # codesuc.top（✅ 备用）
claudeswarm    # byteswarm.ai（✅ 备用）
claudezgc      # micuapi.ai key2, fastMode（✅ 推荐主用）
```

**启动方式：**
```bash
source ~/.bashrc
claudezgc      # 推荐
# 或
claudemicu
```

**如果channel挂了，切换：**
```bash
claudezgc → claudemicu → claudecodesuc → claudeswarm
```

---

## 四、Codex 5个wrapper

已配好，`source ~/.bashrc`后直接用：

```bash
codexzgc       # micuapi.ai/v1, gpt-5.5（✅ 推荐主用）
codexaipai     # aipaibox.com, gpt-5.5
codexmicu      # micuapi.ai/v1, gpt-5.5
codexcodesuc   # codesuc.top, gpt-5.5
codexswarm     # byteswarm.ai, gpt-5.5
```

**启动方式：**
```bash
source ~/.bashrc
codexzgc       # 推荐
```

**如果codex没装，运行：**
```bash
bash /media/$USER/DADAGAGA/add_codex.sh
source ~/.bashrc
```

---

## 五、所有相关URL汇总

### 中转站（Claude Code用）
| Channel | Base URL | Key文件 |
|---------|----------|---------|
| aipai | https://api.aipaibox.com/ | ~/.claude_aipai/settings.json |
| micu | https://www.micuapi.ai | ~/.claude_micu/settings.json |
| codesuc | https://main-new.codesuc.top/ | ~/.claude_codesuc/settings.json |
| swarm | https://byteswarm.ai/claude | ~/.claude_swarm/settings.json |
| zgc | https://www.micuapi.ai | ~/.claude_zgc/settings.json |

### 中转站（Codex用）
| Wrapper | Base URL | Auth文件 |
|---------|----------|---------|
| codexaipai | https://api.aipaibox.com/v1 | ~/.codex_aipai/auth.json |
| codexmicu | https://www.micuapi.ai/v1 | ~/.codex_micu/auth.json |
| codexcodesuc | https://main-new.codesuc.top/v1 | ~/.codex_codesuc/auth.json |
| codexswarm | https://byteswarm.ai/codex/v1 | ~/.codex_swarm/auth.json |
| codexzgc | https://www.micuapi.ai/v1 | ~/.codex_zgc/auth.json |

### 代理/工具
| 用途 | URL |
|------|-----|
| FlClash下载 | https://github.com/chen08209/FlClash/releases |
| 节点管理界面 | https://yacd.metacubex.one/#/proxies |
| Linux Clash教程 | https://fanqiang.gitbook.io/fanqiang/linux |
| EdNovas Cloud | https://ednovas.me/ |
| iKuuu订阅 | https://nqlft.no-mad-world.club/link/x1TclfN9Y6yoI65X?clash=3 |

### 知乎经验帖（群友分享）
- https://zhuanlan.zhihu.com/p/20296595525796381648
- https://blog.csdn.net/s404610154/article/details/159011279

---

## 六、U盘文件清单

```
/media/$USER/DADAGAGA/
├── install_all.sh          # Claude Code + 5 channel 一键安装
├── add_codex.sh            # Codex CLI + 5 wrapper 安装
├── EdNovasCloud_clash.yaml # 代理配置（主用）
├── iKuuu_V2.yaml           # 代理配置（备用）
├── clash订阅URL.txt         # 代理导入步骤
├── 明天Claude配置指南.md    # 本文件
├── START_HERE_Claude开工指南.md  # 科研实训开工指南
├── 补装codex.txt           # codex手动安装说明
├── 补装claudezgc.txt       # claudezgc手动补装说明
└── 带去联想电脑/            # 完整配置包
    ├── 01_SKILLS_清单与推荐.md
    ├── 02_CLAUDE配置部署文档.md
    ├── 03_考试用claude.md   # 4大范式速查（最重要！）
    └── skills_全量备份/     # 34个skill文件
```

---

## 七、踩过的坑（必读）

1. **FlClash忘点Start** → 导入订阅后必须点右下角Start
2. **开TUN需要sudo** → 不要开TUN，用System Proxy即可
3. **终端代理不走** → 浏览器通但终端不通，需手动`export HTTPS_PROXY=...`
4. **aipai一直retry** → aipai经常挂，直接换micu或zgc
5. **中文文件名无法输入** → 用英文命名脚本，或用`bash linux*.sh`通配
6. **U盘没权限执行** → 通过微信/网络传到本地再运行
7. **VSCode版本太低** → 装不了remote SSH，忽略，用终端
8. **.bashrc改完要source** → `source ~/.bashrc`或开新终端
9. **codex没有--version** → 正常，不影响使用
10. **GitHub API限流** → 60次/小时，限流了等一会

---

## 八、环境验证命令

```bash
# 检查Node
node -v

# 检查claude
claude --version

# 检查5个channel连通性
for c in claudeaipai claudemicu claudecodesuc claudeswarm claudezgc; do
  echo -n "$c: "
  $c --print "hi" 2>&1 | head -1
done

# 检查codex
codexzgc --version 2>/dev/null || echo "codex installed"

# 检查代理
curl -s --proxy http://127.0.0.1:7890 https://www.google.com -o /dev/null -w "%{http_code}\n"
```

---

## 九、开考后第一件事

```
1. source ~/.bashrc
2. claudezgc（或claudemicu）
3. 读 03_考试用claude.md（4大范式速查）
4. 等题目下发，拿到后全文粘给Claude
```

**Claude的第一句话应该是：**
> "我看完配置指南了，已就绪。题面准备好了发我，先解析题目结构再开工。"

---

*文档生成时间：2026-05-24 00:xx*
*由Mac端Claude（claude-opus-4-7）生成*

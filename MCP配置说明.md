# MCP 搜索工具配置（5个）

## 国内直接可用（无需外网）
| MCP | API Key | 搜索引擎 |
|-----|---------|---------|
| **bing-search** | 无需 | 必应中文 |
| **baidu-search** | 无需 | 百度（爬虫） |

## 需外网/代理
| MCP | API Key | 特点 |
|-----|---------|------|
| serper-search | `0538ec60...` | Google+网页抓取 |
| tavily-search | `tvly-dev-bKiHgcxw0...` | AI优化搜索 |
| **exa** | `e2b96aa7-37de-4081-85f7-357ca7a3ebb2` | 论文/代码/高质量源 |

## 安装（联想机）
```bash
bash /media/$USER/DADAGAGA/install_mcp.sh
source ~/.bashrc
# 重启 claudezgc 后生效
```

## 登录问题
**不需要登录**。所有key已写入配置文件，重启session自动生效。

## 注意
- baidu-search启动时会打印env vars到stderr，不影响功能
- exa适合搜论文、GitHub代码、高质量技术文章
- Reddit/Twitter需外网代理才能访问（bing/baidu搜不到）

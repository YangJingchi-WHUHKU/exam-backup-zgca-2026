---
name: pdf-reader-pro
description: "统一 PDF 解析入口，自动选择最佳工具。所有涉及 PDF/文档提取的任务都用这个 skill。触发词：读PDF、提取PDF、PDF转文字、PDF转markdown、解析PDF、看这个PDF、扫描件识别、OCR、read PDF、extract PDF、parse PDF、convert PDF、文档解析、批量转换、表格提取、公式识别。"
allowed-tools:
  - Bash
  - Read
  - Write
---

# PDF Reader Pro — 统一文档解析入口

所有 PDF/文档解析任务的唯一入口。根据情况自动选择下面三种工具之一。

---

## 三种工具

### 工具 A：pymupdf（本地脚本）
- **原理**：读取 PDF 内嵌文字层，纯本地
- **花销**：0，极快
- **限制**：只对数字 PDF 有效，扫描件无效
- **脚本路径**：`~/.config/agents/skills/pdf-reader-pro/scripts/batch_pdf_to_txt.py`

```bash
# 单文件
python3 ~/.config/agents/skills/pdf-reader-pro/scripts/batch_pdf_to_txt.py <file.pdf>

# 整个目录
python3 ~/.config/agents/skills/pdf-reader-pro/scripts/batch_pdf_to_txt.py <目录/> -o <输出目录/>

# 递归处理子目录
python3 ~/.config/agents/skills/pdf-reader-pro/scripts/batch_pdf_to_txt.py <目录/> -r -o <输出目录/>
```

---

### 工具 B：mineru-open-api flash-extract（云端快速）
- **原理**：调用 MinerU 云端，有 OCR，结构化输出
- **花销**：0，无需 token，IP 限频（每分钟有上限）
- **限制**：单文件 ≤10MB、≤20页；不支持表格识别；仅输出 Markdown
- **CLI**：`~/.local/bin/mineru-open-api`（已安装 v0.2.1）

```bash
# 单文件输出到对话（小文件快速读取）
mineru-open-api flash-extract "<file.pdf>"

# 保存到文件
mineru-open-api flash-extract "<file.pdf>" -o ~/MinerU-Skill/<name>/

# 指定页码
mineru-open-api flash-extract "<file.pdf>" --pages 1-10

# 中文文档（默认就是 ch）
mineru-open-api flash-extract "<file.pdf>" --language ch
```

---

### 工具 C：mineru-open-api extract（云端精准）
- **原理**：云端 MinerU 精准模式，支持表格/公式/多格式
- **花销**：0，需免费 token（https://mineru.net/apiManage/token 注册）
- **限制**：需要先 `mineru-open-api auth` 配置 token
- **适用**：>20页、>10MB、需要表格/公式/html/docx 输出

```bash
# 精准提取（表格+公式+OCR）
mineru-open-api extract "<file.pdf>" -o ~/MinerU-Skill/<name>/

# 批量提取
mineru-open-api extract *.pdf -o ~/MinerU-Skill/batch/

# 指定模型（vlm=高精度，pipeline=无幻觉）
mineru-open-api extract "<file.pdf>" --model vlm -o ~/MinerU-Skill/<name>/

# 多格式输出
mineru-open-api extract "<file.pdf>" -f md,docx -o ~/MinerU-Skill/<name>/

# 检查 token 是否配置
mineru-open-api auth --verify
```

---


## 决策路由

```
用户请求 PDF 解析
       │
       ▼
需要立刻看到结果（对话中分析、现在就用）？
  ├─ 是 → 工具 A（秒级返回，先拿到内容再说）
  │        格式差一点没关系，速度第一
  └─ 否（不急，要存文件，后续处理）↓

文件是否超过 20 页 或 10MB？
  ├─ 是 → 工具 C（extract，需 token）
  └─ 否 ↓

是否需要表格识别 / 公式 / 非 Markdown 格式？
  ├─ 是 → 工具 C（extract）
  └─ 否 → 工具 B（flash-extract，默认）
```

---

## 触发关键词 → 工具映射

| 用户说 | 路由 | 原因 |
|--------|------|------|
| "这个PDF说了什么"、"帮我看看"、"现在分析" | 工具 A | 立刻要结果，秒级 |
| "批量转TXT"、"整个目录转"、"存起来备用" | 工具 B | 不急，质量优先 |
| "转成干净的markdown"、"要格式好的" | 工具 B | 质量优先 |
| "扫描件"、"OCR识别" | 工具 B | 有 OCR |
| "超过20页"、"大文件"、"表格"、"公式" | 工具 C | 超出 flash-extract 限制 |
| "这个PDF有多少页" | 工具 A | 元数据查询，秒级 |

---

## 输出目录规则（工具 B/C 无 -o 时）

自动生成：`~/MinerU-Skill/<name>_<hash>/`

```bash
# 计算 hash（macOS）
HASH=$(echo -n "<完整路径或URL>" | md5 | cut -c1-6)
NAME=$(basename "<file>" .pdf | sed 's/[[:space:]()\[\]&'"'"'"!#$`]/_/g')
OUTPUT_DIR=~/MinerU-Skill/${NAME}_${HASH}/
```

---

## 注意事项

1. **文件路径含空格/中文**：必须加双引号 `"路径"`
2. **工具 B 被限频（HTTP 429）**：等 1 分钟或切换工具 C
3. **工具 C 无 token**：运行 `mineru-open-api auth` 或去 https://mineru.net/apiManage/token 免费申请
4. **商标图形/图片内容**：所有工具均无法提取图片形式的商标，这是 PDF 本身限制
5. **不要用 mcp__pdf-reader**：内容会直接进 context，token 消耗极大

---

## 已废弃

- ~~mcp__pdf-reader~~：token 消耗大，已停用
- ~~mineru-reader skill~~：功能已整合进本 skill
- ~~mineru-document-extractor skill~~：功能已整合进本 skill（工具 B/C）

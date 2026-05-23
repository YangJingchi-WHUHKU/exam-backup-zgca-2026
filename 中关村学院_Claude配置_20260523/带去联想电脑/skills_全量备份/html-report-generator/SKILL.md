---
name: html-report-generator
description: "HTML report generation for research and documentation. This skill should be used when the user asks to 'generate HTML report', 'create HTML output', 'output in HTML format', 'make an HTML page', '生成HTML报告', '创建HTML页面', '输出HTML格式', '做个网页报告', '弄个HTML文档', or needs analysis results formatted as clean, professional HTML."
---

# HTML Report Generator

Generate professional, clean HTML reports for research, analysis, and documentation. This skill provides a standardized paradigm for creating HTML output that avoids common formatting issues and maintains consistent styling.

## Purpose

This skill addresses the recurring need to output research findings, analysis conclusions, and knowledge documentation in HTML format. It establishes a reliable workflow and template system to eliminate trial-and-error when creating HTML reports.

## When to Use

Invoke this skill when the user requests:
- HTML output for research or analysis
- Documentation formatted as a web page
- Reports in structured, shareable HTML format
- Knowledge summaries with professional presentation

## Workflow

### Step 1: Read the Template

Load the HTML template from the assets directory:

```bash
cat assets/report-template.html
```

The template contains three placeholder variables:
- `{{REPORT_TITLE}}` - Main title of the report
- `{{DATE}}` - Generation date (format: YYYY-MM-DD)
- `{{CONTENT}}` - Main body content in HTML

### Step 2: Prepare Content

Structure the content using semantic HTML:

**Headings:**
- `<h2>` for main sections
- `<h3>` for subsections
- Never use `<h1>` (reserved for report title)

**Text elements:**
- `<p>` for paragraphs
- `<ul>` or `<ol>` for lists
- `<code>` for inline code
- `<pre><code>` for code blocks
- `<blockquote>` for quotations

**Tables:**
```html
<table>
    <thead>
        <tr>
            <th>Column 1</th>
            <th>Column 2</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>Data 1</td>
            <td>Data 2</td>
        </tr>
    </tbody>
</table>
```

**Styled boxes for emphasis:**
```html
<div class="info-box">
    <strong>信息:</strong> Important information
</div>

<div class="warning-box">
    <strong>注意:</strong> Warning or caution
</div>

<div class="success-box">
    <strong>成功:</strong> Success message
</div>

<div class="highlight">
    <strong>重点:</strong> Key takeaway
</div>
```

### Step 3: Replace Template Variables

1. Replace `{{REPORT_TITLE}}` with the actual report title
2. Replace `{{DATE}}` with current date (YYYY-MM-DD format)
3. Replace `{{CONTENT}}` with the prepared HTML content

### Step 4: Write the HTML File

Use the Write tool to create the HTML file with a descriptive name:

**Naming convention:**
- Use lowercase with hyphens
- Include date if relevant: `analysis-report-2026-02-28.html`
- Be specific: `user-behavior-analysis.html`

### Step 5: Verify Quality

Check before finalizing:
- All template variables replaced
- Proper heading hierarchy (h2 → h3)
- No broken HTML tags
- Tables have thead/tbody structure
- Code blocks use `<pre><code>` tags
- Special characters properly escaped (`&lt;`, `&gt;`, `&amp;`)

## Common Patterns

### Research Findings

```html
<h2>研究发现</h2>
<p>研究背景和目的...</p>

<h3>主要发现</h3>
<ul>
    <li>发现点 1</li>
    <li>发现点 2</li>
    <li>发现点 3</li>
</ul>

<h3>数据分析</h3>
<table>
    <thead>
        <tr>
            <th>指标</th>
            <th>数值</th>
            <th>说明</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>指标1</td>
            <td>100</td>
            <td>说明文字</td>
        </tr>
    </tbody>
</table>
```

### Analysis Conclusions

```html
<h2>分析结论</h2>

<div class="highlight">
    <strong>核心结论:</strong> 简明扼要的核心结论
</div>

<h3>详细分析</h3>
<p>详细的分析内容...</p>

<h3>建议</h3>
<ol>
    <li>建议1</li>
    <li>建议2</li>
    <li>建议3</li>
</ol>
```

## Template Features

The template includes:
- Responsive design - Works on all screen sizes
- Print-friendly - Optimized for printing
- Clean typography - System fonts for readability
- Semantic structure - Proper HTML5 elements
- No dependencies - Works in all modern browsers
- Professional styling - Subtle shadows and spacing

## Customization

To modify styling, adjust CSS variables in the template:
- Colors: Change hex values (e.g., `#007bff` for primary color)
- Fonts: Modify `font-family` values
- Spacing: Adjust `padding` and `margin` values
- Width: Change `.container` `max-width` (default: 900px)

Keep customizations minimal to maintain readability and simplicity.

## Assets

**`assets/report-template.html`** - Base HTML template with embedded CSS styling

## Notes

- Template uses Chinese language attribute (`lang="zh-CN"`) by default
- All styles are embedded (no external CSS files)
- Template is self-contained and portable
- Works offline without internet connection
- Compatible with all modern browsers (Chrome, Firefox, Safari, Edge)

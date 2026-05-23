#!/bin/bash
# cross-verify.sh — 自动交叉验证脚本
# 用法: cross-verify.sh "你的问题或代码" [--models aipai,micu,codesuc,swarm] [--context file.py]
# 默认使用 aipai + micu + codesuc + swarm 四个考试 channel

set -euo pipefail

# 解除嵌套保护，允许在 Claude Code 会话内启动子实例
unset CLAUDECODE 2>/dev/null || true

CLAUDE_BIN=$(ls -t ~/.local/share/claude/versions/* 2>/dev/null | head -1)
if [ -z "$CLAUDE_BIN" ]; then
    echo "Error: Claude binary not found" >&2
    exit 1
fi

# 默认参数
MODELS="aipai,micu,codesuc,swarm"
PROMPT=""
CONTEXT_FILE=""
OUTPUT_DIR="./cross-verify-$(date +%Y%m%d-%H%M%S)"
MAX_BUDGET="2"
MODEL_TIMEOUT=180       # 单模型超时（秒）
TOTAL_TIMEOUT=600       # 总超时 10 分钟（秒）
SYNTHESIS_TIMEOUT=240   # 合成分析超时（秒）

# 记录开始时间
START_TIME=$(date +%s)

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --models) MODELS="$2"; shift 2 ;;
        --context) CONTEXT_FILE="$2"; shift 2 ;;
        --budget) MAX_BUDGET="$2"; shift 2 ;;
        --timeout) TOTAL_TIMEOUT="$2"; shift 2 ;;
        --help)
            echo "用法: cross-verify.sh \"问题\" [选项]"
            echo ""
            echo "选项:"
            echo "  --models duck,ccodex,minimax,codex  指定参与模型 (默认: duck,ccodex,minimax,codex)"
            echo "  --context file.py                    附加上下文文件"
            echo "  --budget 2                           每个模型最大花费 (默认: 2 USD)"
            echo "  --timeout 600                        总超时秒数 (默认: 600 = 10分钟)"
            echo ""
            echo "模型映射:"
            echo "  duck    -> Claude Duck (~/.claude_duck/) [claude-opus-4-6]"
            echo "  ccodex  -> Claude Codex (~/.claude_codex/) [claude-opus-4-6]"
            echo "  minimax -> Claude MiniMax (~/.claude_minimax/) [MiniMax-M2.5]"
            echo "  codex   -> Codex CLI (codex exec) [gpt-5.4]"
            exit 0
            ;;
        *) PROMPT="$1"; shift ;;
    esac
done

if [ -z "$PROMPT" ]; then
    echo "Error: 需要提供问题/prompt" >&2
    echo "用法: cross-verify.sh \"你的问题\"" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# 如果有上下文文件，附加到 prompt
FULL_PROMPT="$PROMPT"
if [ -n "$CONTEXT_FILE" ] && [ -f "$CONTEXT_FILE" ]; then
    CONTEXT_CONTENT=$(cat "$CONTEXT_FILE")
    FULL_PROMPT="$PROMPT

--- 上下文文件: $CONTEXT_FILE ---
$CONTEXT_CONTENT"
fi

# 系统提示：要求结构化输出
SYSTEM_SUFFIX="请直接回答问题，给出你的分析和结论。保持简洁，重点突出。不要寒暄。"

# 带超时的模型调用函数
call_model_with_timeout() {
    local model_name="$1"
    local output_file="$OUTPUT_DIR/$model_name.txt"
    local timeout_sec="$MODEL_TIMEOUT"

    # 内部函数：实际调用
    _do_call() {
        case "$model_name" in
            duck)
                CLAUDE_CONFIG_DIR="$HOME/.claude_duck" "$CLAUDE_BIN" \
                    --setting-sources=user \
                    -p --output-format text \
                    --max-budget-usd "$MAX_BUDGET" \
                    --no-session-persistence \
                    --append-system-prompt "$SYSTEM_SUFFIX" \
                    "$FULL_PROMPT" > "$output_file" 2>/dev/null
                ;;
            codex)
                codex exec --skip-git-repo-check "$FULL_PROMPT" > "$output_file" 2>/dev/null
                ;;
            ccodex)
                CLAUDE_CONFIG_DIR="$HOME/.claude_codex" "$CLAUDE_BIN" \
                    --setting-sources=user \
                    -p --output-format text \
                    --max-budget-usd "$MAX_BUDGET" \
                    --no-session-persistence \
                    --append-system-prompt "$SYSTEM_SUFFIX" \
                    "$FULL_PROMPT" > "$output_file" 2>/dev/null
                ;;
            minimax)
                CLAUDE_CONFIG_DIR="$HOME/.claude_minimax" "$CLAUDE_BIN" \
                    --setting-sources=user \
                    -p --output-format text \
                    --max-budget-usd "$MAX_BUDGET" \
                    --no-session-persistence \
                    --append-system-prompt "$SYSTEM_SUFFIX" \
                    "$FULL_PROMPT" > "$output_file" 2>/dev/null
                ;;
            aipai)
                CLAUDE_CONFIG_DIR="$HOME/.claude_aipai" "$CLAUDE_BIN" \
                    --setting-sources=user \
                    -p --output-format text \
                    --max-budget-usd "$MAX_BUDGET" \
                    --no-session-persistence \
                    --append-system-prompt "$SYSTEM_SUFFIX" \
                    "$FULL_PROMPT" > "$output_file" 2>/dev/null
                ;;
            micu)
                CLAUDE_CONFIG_DIR="$HOME/.claude_micu" "$CLAUDE_BIN" \
                    --setting-sources=user \
                    -p --output-format text \
                    --max-budget-usd "$MAX_BUDGET" \
                    --no-session-persistence \
                    --append-system-prompt "$SYSTEM_SUFFIX" \
                    "$FULL_PROMPT" > "$output_file" 2>/dev/null
                ;;
            codesuc)
                CLAUDE_CONFIG_DIR="$HOME/.claude_codex" "$CLAUDE_BIN" \
                    --setting-sources=user \
                    -p --output-format text \
                    --max-budget-usd "$MAX_BUDGET" \
                    --no-session-persistence \
                    --append-system-prompt "$SYSTEM_SUFFIX" \
                    "$FULL_PROMPT" > "$output_file" 2>/dev/null
                ;;
            swarm)
                CLAUDE_CONFIG_DIR="$HOME/.claude_byteswarm" "$CLAUDE_BIN" \
                    --setting-sources=user \
                    -p --output-format text \
                    --max-budget-usd "$MAX_BUDGET" \
                    --no-session-persistence \
                    --append-system-prompt "$SYSTEM_SUFFIX" \
                    "$FULL_PROMPT" > "$output_file" 2>/dev/null
                ;;
            *)
                echo "Unknown model: $model_name" >&2
                return 1
                ;;
        esac
    }

    # 用子 shell + 后台 + sleep 实现超时
    _do_call &
    local call_pid=$!

    # 超时监控
    (
        sleep "$timeout_sec"
        if kill -0 "$call_pid" 2>/dev/null; then
            kill "$call_pid" 2>/dev/null
            echo "(超时 ${timeout_sec}s)" > "$output_file.timeout"
        fi
    ) &
    local timer_pid=$!

    # 等调用完成
    if wait "$call_pid" 2>/dev/null; then
        kill "$timer_pid" 2>/dev/null
        wait "$timer_pid" 2>/dev/null
        return 0
    else
        kill "$timer_pid" 2>/dev/null
        wait "$timer_pid" 2>/dev/null
        # 检查是超时还是报错
        if [ -f "$output_file.timeout" ]; then
            echo "⏱ $model_name 超时 (${timeout_sec}s)" > "$output_file"
            rm -f "$output_file.timeout"
        fi
        return 1
    fi
}

echo "=== 交叉验证开始 ==="
echo "问题: $PROMPT"
echo "模型: $MODELS"
echo "超时: 单模型 ${MODEL_TIMEOUT}s / 总计 ${TOTAL_TIMEOUT}s"
echo "输出目录: $OUTPUT_DIR"
echo ""

# 并行调用所有模型
IFS=',' read -ra MODEL_ARRAY <<< "$MODELS"
PIDS=()

for model in "${MODEL_ARRAY[@]}"; do
    model=$(echo "$model" | xargs)
    echo ">>> 启动 $model ..."
    call_model_with_timeout "$model" &
    PIDS+=($!)
done

# 等待所有模型完成，但不超过总超时
ELAPSED=0
ALL_DONE=false
while [ "$ELAPSED" -lt "$TOTAL_TIMEOUT" ] && [ "$ALL_DONE" = false ]; do
    ALL_DONE=true
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            ALL_DONE=false
            break
        fi
    done
    if [ "$ALL_DONE" = false ]; then
        sleep 2
        ELAPSED=$(( $(date +%s) - START_TIME ))
    fi
done

# 如果总超时到了还有模型在跑，全部杀掉
if [ "$ALL_DONE" = false ]; then
    echo ""
    echo "⏱ 总超时 ${TOTAL_TIMEOUT}s 到达，终止剩余模型"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    sleep 1
fi

# 收集结果
FAILED=()
TIMED_OUT=()
echo ""
echo "=== 各模型回答 ==="

for model in "${MODEL_ARRAY[@]}"; do
    model=$(echo "$model" | xargs)
    output_file="$OUTPUT_DIR/$model.txt"
    echo ""
    echo "--- $model ---"
    if [ -f "$output_file" ] && [ -s "$output_file" ]; then
        # 检查是否是超时标记
        if grep -q "超时" "$output_file" 2>/dev/null; then
            cat "$output_file"
            TIMED_OUT+=("$model")
        else
            cat "$output_file"
        fi
    else
        echo "(无输出或调用失败)"
        FAILED+=("$model")
    fi
done

if [ ${#FAILED[@]} -gt 0 ]; then
    echo ""
    echo "❌ 失败: ${FAILED[*]}"
fi
if [ ${#TIMED_OUT[@]} -gt 0 ]; then
    echo "⏱ 超时: ${TIMED_OUT[*]}"
fi

ELAPSED_TOTAL=$(( $(date +%s) - START_TIME ))
echo ""
echo "收集阶段耗时: ${ELAPSED_TOTAL}s"

# 检查总超时剩余时间，不够就跳过合成
REMAINING=$(( TOTAL_TIMEOUT - ELAPSED_TOTAL ))
if [ "$REMAINING" -lt 30 ]; then
    echo "⏱ 剩余时间不足 30s，跳过合成分析"
    REMAINING=0
fi

# 生成汇总文件（内部用）
SUMMARY_FILE="$OUTPUT_DIR/_raw_responses.md"
{
    echo "# 各模型原始回答"
    echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "问题: $PROMPT"
    echo ""
    for model in "${MODEL_ARRAY[@]}"; do
        model=$(echo "$model" | xargs)
        output_file="$OUTPUT_DIR/$model.txt"
        echo "## $model"
        if [ -f "$output_file" ] && [ -s "$output_file" ] && ! grep -q "超时" "$output_file" 2>/dev/null; then
            cat "$output_file"
        else
            echo "(无有效输出)"
        fi
        echo ""
    done
} > "$SUMMARY_FILE"

# 统计成功数
SUCCESS_COUNT=0
for model in "${MODEL_ARRAY[@]}"; do
    model=$(echo "$model" | xargs)
    output_file="$OUTPUT_DIR/$model.txt"
    if [ -f "$output_file" ] && [ -s "$output_file" ] && ! grep -q "超时" "$output_file" 2>/dev/null; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    fi
done

REPORT_FILE="$OUTPUT_DIR/report.md"

if [ "$SUCCESS_COUNT" -ge 2 ] && [ "$REMAINING" -gt 0 ]; then
    echo ""
    echo "=== 正在合成对比分析（超时 ${SYNTHESIS_TIMEOUT}s）==="
    SYNTHESIS_PROMPT="你是交叉验证分析员。以下是多个独立AI模型对同一问题的回答。请生成完整报告，格式如下：

# 交叉验证报告
时间: $(date '+%Y-%m-%d %H:%M:%S')
参与模型: $MODELS

## 原始问题
$PROMPT

## 各模型回答摘要
(每个模型1-2句话概括核心观点)

## 共识
(所有模型一致同意的部分)

## 分歧
(模型之间不同的观点，用表格标注哪个模型持哪个观点)

## 最终结论
(综合所有模型的分析，给出最可靠的结论)

## 可信度评估
(这次交叉验证的结果可信度：高/中/低，理由)

---

最后附上各模型的完整原始回答（用引用块包裹）。

---
以下是各模型的原始回答：

$(cat "$SUMMARY_FILE")"

    # 合成使用 aipai 做综合分析（考试用 channel）
    CLAUDE_CONFIG_DIR="$HOME/.claude_aipai" "$CLAUDE_BIN" \
        --setting-sources=user \
        -p --output-format text \
        --max-budget-usd "$MAX_BUDGET" \
        --no-session-persistence \
        "$SYNTHESIS_PROMPT" > "$REPORT_FILE" 2>/dev/null &
    SYNTH_PID=$!

    # 合成超时监控
    (
        sleep "$SYNTHESIS_TIMEOUT"
        if kill -0 "$SYNTH_PID" 2>/dev/null; then
            kill "$SYNTH_PID" 2>/dev/null
        fi
    ) &
    SYNTH_TIMER=$!

    if wait "$SYNTH_PID" 2>/dev/null; then
        kill "$SYNTH_TIMER" 2>/dev/null
        wait "$SYNTH_TIMER" 2>/dev/null
    else
        kill "$SYNTH_TIMER" 2>/dev/null
        wait "$SYNTH_TIMER" 2>/dev/null
    fi

    if [ -f "$REPORT_FILE" ] && [ -s "$REPORT_FILE" ]; then
        echo ""
        cat "$REPORT_FILE"
    else
        cp "$SUMMARY_FILE" "$REPORT_FILE"
        echo "⏱ 合成分析超时或失败，已保存原始回答到 report.md"
    fi
else
    cp "$SUMMARY_FILE" "$REPORT_FILE"
    if [ "$SUCCESS_COUNT" -lt 2 ]; then
        echo "成功模型不足2个，跳过对比分析"
    fi
fi

FINAL_ELAPSED=$(( $(date +%s) - START_TIME ))
echo ""
echo "=== 报告已保存: $REPORT_FILE ==="
echo "=== 总耗时: ${FINAL_ELAPSED}s ==="

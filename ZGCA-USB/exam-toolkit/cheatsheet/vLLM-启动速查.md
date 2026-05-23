# vLLM 启动 & 调用速查

> ⭐ RAG 题 / RL 题的 LLM 推理都靠 vLLM。这一页搞定全流程。

---

## 一、基础启动命令

```bash
# 最简启动 Qwen3-14B
vllm serve /path/to/Qwen3-14B \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.9
```

**后台启动 + 日志重定向**：
```bash
nohup vllm serve /path/to/Qwen3-14B \
    --host 0.0.0.0 --port 8000 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.9 \
    > vllm.log 2>&1 &
echo "PID: $!"

# 等启动
sleep 30
tail -f vllm.log    # 看到 "Application startup complete" 即可
```

---

## 二、常用参数表

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| `--host` | 监听 IP | `0.0.0.0`（允许外部访问）or `127.0.0.1`（本机） |
| `--port` | 端口 | `8000`（默认） |
| `--max-model-len` | 最大序列长度 | `4096`（短）/ `8192`（长） |
| `--gpu-memory-utilization` | 显存占用率 | `0.9`（独占）/ `0.7`（与训练共用） |
| `--tensor-parallel-size` | 张量并行 | `1`（单卡 A100 80G）/ `2`（双卡） |
| `--dtype` | 精度 | `bfloat16`（推荐）/ `auto` |
| `--max-num-seqs` | 最大并发请求 | `64`（默认）/ `32`（OOM 时） |
| `--max-num-batched-tokens` | 单 batch 最大 token | `4096` ~ `8192` |
| `--enable-prefix-caching` | 前缀缓存（RAG 必开） | 加这个 flag |
| `--trust-remote-code` | 自研模型 | 加这个 flag |
| `--enforce-eager` | 关 CUDA Graph（省启动时间） | 调试时加 |
| `--swap-space` | CPU swap GB | `4`（OOM 时） |

**A100 80G 调优组合**：
```bash
# RAG 推理（短 prompt 多）
vllm serve Qwen3-14B \
    --host 0.0.0.0 --port 8000 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    --max-num-seqs 32 \
    --enable-prefix-caching \
    --dtype bfloat16

# GRPO 训练（colocate 模式，与 trainer 共显存）
vllm serve Qwen2.5-7B-Instruct \
    --host 0.0.0.0 --port 8001 \
    --max-model-len 2048 \
    --gpu-memory-utilization 0.5 \
    --dtype bfloat16 \
    --enforce-eager
```

---

## 三、OpenAI 兼容 API 调用

### Python (openai client) ⭐推荐
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="EMPTY"    # vLLM 不验证，但不能为空
)

# Chat 格式
resp = client.chat.completions.create(
    model="Qwen3-14B",    # 任意名字，vLLM 忽略
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"}
    ],
    temperature=0.7,
    max_tokens=256,
    top_p=0.9,
    stop=["</s>", "User:"]
)
print(resp.choices[0].message.content)

# Completion 格式（旧）
resp = client.completions.create(
    model="Qwen3-14B",
    prompt="The capital of France is",
    max_tokens=10
)
```

### Python (requests)
```python
import requests
r = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "model": "Qwen3-14B",
        "messages": [{"role": "user", "content": "Hi"}],
        "temperature": 0.7,
        "max_tokens": 256
    }
)
print(r.json()['choices'][0]['message']['content'])
```

### curl
```bash
curl http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen3-14B",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 100
    }'
```

---

## 四、批量推理加速（async）⭐ RAG 必用

```python
import asyncio
import httpx

async def query_llm(client, prompt):
    r = await client.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "model": "Qwen3-14B",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256
        },
        timeout=60.0
    )
    return r.json()['choices'][0]['message']['content']

async def batch_query(prompts, concurrency=16):
    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(concurrency)
        async def _q(p):
            async with sem:
                return await query_llm(client, p)
        return await asyncio.gather(*[_q(p) for p in prompts])

# 用法
prompts = ["Q1", "Q2", ..., "Q50"]
answers = asyncio.run(batch_query(prompts, concurrency=16))
```

⚡ **比串行快 10×**。RAG 题 50 个问题，3 分钟 → 20 秒。

---

## 五、调试 & 健康检查

### 健康检查
```bash
curl http://localhost:8000/health
# 返回 {} 表示 OK

curl http://localhost:8000/v1/models
# 看到 model id 表示加载完成
```

### 看日志
```bash
tail -f vllm.log
# 关键字搜索：
grep -i "error" vllm.log
grep -i "oom" vllm.log
grep "Application startup complete" vllm.log    # 看到这个才能调
```

### GPU 使用率
```bash
watch -n 1 nvidia-smi    # 实时刷新
nvidia-smi pmon -c 1     # 进程级
```

### 端口占用排查
```bash
lsof -i :8000           # 看谁占用 8000
netstat -tlnp | grep 8000
# 杀进程
fuser -k 8000/tcp
```

---

## 六、退出 / 重启

```bash
# 找进程
ps aux | grep vllm
# 优雅退出
pkill -f "vllm serve"
# 强制
pkill -9 -f "vllm serve"
# 或者按 PID
kill -9 <pid>

# 重启
nohup vllm serve ... > vllm.log 2>&1 &
```

---

## 七、常见错误

| 错误 | 原因 | 修复 |
|------|------|------|
| `CUDA out of memory` | 显存不够 | 降 `--gpu-memory-utilization` 到 0.7 / 减 `--max-model-len` |
| `RuntimeError: NCCL` | tp_size 与 GPU 数不一致 | 检查 `nvidia-smi` 看可见 GPU 数 |
| `Connection refused` | 服务没起来 | 等 30 秒 / 看 vllm.log |
| `Address already in use` | 端口占用 | 换端口或 kill 旧进程 |
| 返回空字符串 | `max_tokens=0` 或 `stop` 设错 | 检查请求参数 |
| 推理慢 | 没开 prefix caching | 加 `--enable-prefix-caching` |
| 模型加载慢 | 不是 safetensors | 等 5 分钟，或转 safetensors |

---

## 八、RAG 题快速启动模板

```bash
#!/bin/bash
# run_vllm.sh

MODEL=/vepfs-readonly/problem4/models/Qwen3-14B

# 1. 启动 vLLM
nohup vllm serve "$MODEL" \
    --host 0.0.0.0 --port 8000 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    --max-num-seqs 32 \
    --enable-prefix-caching \
    --dtype bfloat16 \
    > vllm.log 2>&1 &

echo "vLLM PID: $!"
echo "等待启动..."

# 2. 等服务起来
for i in {1..60}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ vLLM ready ($i seconds)"
        break
    fi
    sleep 1
done

# 3. 测试
curl -s http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "qwen", "messages": [{"role":"user","content":"hi"}], "max_tokens":20}' \
    | python -c "import json,sys; d=json.load(sys.stdin); print(d['choices'][0]['message']['content'])"

echo "🎉 vLLM 就绪"
```

---

## 九、GRPO Colocate 模式（与 trainer 同显存）

GRPO 训练时 vLLM 和 trainer **共享显存**，必须用 colocate：

```python
# TRL GRPOConfig
config = GRPOConfig(
    use_vllm=True,
    vllm_mode='colocate',           # ⭐ 共显存
    vllm_gpu_memory_utilization=0.4,    # 给 vLLM 40%
    # trainer 自动用剩下的 60%
)
```

⚠️ **不要单独启动 vllm serve**。colocate 模式由 trainer 内部管理。

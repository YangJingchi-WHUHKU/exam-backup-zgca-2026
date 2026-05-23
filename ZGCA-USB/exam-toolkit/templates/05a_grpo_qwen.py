"""
GRPO 微调 Qwen 小模型 - 押宝今年压轴 RL 题
===========================================

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. MODEL_PATH        - 题目给的 ckpt 路径，如 /vepfs-readonly/problemX/Qwen2.5-1.5B
  2. DATASET_LOAD()    - 题目给的 dataset 接口（替换 GSM8K 示例）
  3. reward_*          - 题目要求的奖励函数（可验证奖励 / 格式奖励）
  4. OUT_DIR           - 一般 /vepfs/problemX/ckpts
  5. SUBMIT_PATH       - 题目要求的提交文件位置

依赖（现场 pip install）:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      trl peft bitsandbytes accelerate datasets

显存预算 (A100 80G):
  Qwen2.5-0.5B + QLoRA 4bit + num_generations=8 → ~12 GB
  Qwen2.5-1.5B + QLoRA 4bit + num_generations=8 → ~20 GB
  Qwen2.5-3B   + QLoRA 4bit + num_generations=4 → ~35 GB
  Qwen2.5-7B   + QLoRA 4bit + num_generations=4 → ~55 GB （边界）

运行:
  python 05a_grpo_qwen.py                      # 默认 0.5B
  python 05a_grpo_qwen.py --model_size 1.5B --steps 200
  accelerate launch 05a_grpo_qwen.py           # 多卡（考场通常单卡）

提交:
  --do_predict 阶段会自动写 predictions.jsonl 到 OUT_DIR
"""

import argparse
import json
import os
import re
from pathlib import Path

import torch
from datasets import load_dataset, Dataset
from peft import LoraConfig
from transformers import AutoTokenizer, BitsAndBytesConfig
from trl import GRPOConfig, GRPOTrainer


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
MODEL_PATH = os.environ.get("MODEL_PATH", "Qwen/Qwen2.5-0.5B-Instruct")
OUT_DIR = os.environ.get("OUT_DIR", "/vepfs/problemX/grpo_out")
SUBMIT_PATH = os.environ.get("SUBMIT_PATH", "/vepfs/problemX/predictions.jsonl")

# 必须从题面提供的 dataset 接口加载（这里给 GSM8K 当示例）
# 题目通常会给类似：
#   from problem_dataset import ProblemDataset
#   ds_train, ds_valid, ds_test = ProblemDataset.load(path)
def DATASET_LOAD():
    """CHANGE_ME: 换成题目给定的 dataset 接口"""
    ds = load_dataset("openai/gsm8k", "main", split="train[:1000]")
    def to_prompt(ex):
        return {
            "prompt": [
                {"role": "system", "content": "Reason step by step. Put final answer in \\boxed{N}."},
                {"role": "user", "content": ex["question"]},
            ],
            "gold": extract_gsm8k_answer(ex["answer"]),
        }
    return ds.map(to_prompt, remove_columns=ds.column_names)


# ============================================================
# 2) REWARD FUNCTIONS - 题目说要"可验证奖励"就照这模式写
# ============================================================
# TRL GRPO 接口: 接收 completions/prompts/**kwargs, 返回 list[float]
# 多个 reward 函数会被加权求和（默认等权），逐个独立 log

def extract_gsm8k_answer(text: str) -> str:
    """解析 GSM8K 标签里的 #### N"""
    m = re.search(r"####\s*(-?\d+(?:\.\d+)?)", text)
    return m.group(1).strip() if m else ""


def extract_boxed(text: str) -> str:
    """从模型输出里抓 \\boxed{N}"""
    m = re.search(r"\\boxed\{([^}]+)\}", text)
    return m.group(1).strip() if m else ""


def reward_correctness(completions, gold=None, **kwargs):
    """正确性奖励：数值答案匹配 → +1，否则 0"""
    rewards = []
    for c, g in zip(completions, gold):
        text = c[0]["content"] if isinstance(c, list) else c
        pred = extract_boxed(text)
        try:
            ok = abs(float(pred) - float(g)) < 1e-6
        except (ValueError, TypeError):
            ok = pred == g
        rewards.append(1.0 if ok else 0.0)
    return rewards


def reward_format(completions, **kwargs):
    """格式奖励：是否出现 \\boxed{...} → +0.2"""
    rewards = []
    for c in completions:
        text = c[0]["content"] if isinstance(c, list) else c
        rewards.append(0.2 if "\\boxed{" in text and "}" in text else 0.0)
    return rewards


def reward_length(completions, **kwargs):
    """长度奖励：鼓励 50-500 token 之间的回答"""
    rewards = []
    for c in completions:
        text = c[0]["content"] if isinstance(c, list) else c
        n = len(text.split())
        if 50 <= n <= 500:
            rewards.append(0.1)
        else:
            rewards.append(0.0)
    return rewards


# ============================================================
# 3) MODEL LOADING (QLoRA)
# ============================================================
def build_model_and_tokenizer(model_path: str, use_qlora: bool = True):
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"  # GRPO 生成需要左 padding

    quant_cfg = None
    if use_qlora:
        quant_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
    return model_path, tok, quant_cfg


def build_peft_config():
    return LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )


# ============================================================
# 4) TRAIN
# ============================================================
def train(args):
    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    model_path, tok, quant_cfg = build_model_and_tokenizer(args.model, args.qlora)
    train_ds = DATASET_LOAD()

    cfg = GRPOConfig(
        output_dir=OUT_DIR,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        num_generations=args.num_gen,             # 每个 prompt 生成几个 completion (8 是 DeepSeek 推荐)
        max_prompt_length=args.max_prompt,
        max_completion_length=args.max_completion,
        num_train_epochs=args.epochs,
        max_steps=args.steps,
        logging_steps=5,
        save_steps=100,
        save_total_limit=2,
        bf16=True,
        gradient_checkpointing=True,
        beta=0.04,                                # KL 系数，DeepSeek 默认 0.04
        # ===== vLLM 加速生成（题目不限制就开）=====
        use_vllm=args.use_vllm,
        vllm_mode="colocate" if args.use_vllm else None,
        # ===== 日志 =====
        report_to="none",
        seed=42,
    )

    trainer = GRPOTrainer(
        model=model_path,
        args=cfg,
        train_dataset=train_ds,
        reward_funcs=[reward_correctness, reward_format, reward_length],
        processing_class=tok,
        peft_config=build_peft_config() if args.qlora else None,
    )
    trainer.train()
    trainer.save_model(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    print(f"[OK] saved to {OUT_DIR}")


# ============================================================
# 5) PREDICT
# ============================================================
@torch.no_grad()
def predict(args):
    """在测试集上推理，按题目要求格式写 SUBMIT_PATH"""
    from transformers import AutoModelForCausalLM
    from peft import PeftModel

    base = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="auto",
        trust_remote_code=True,
    )
    if Path(OUT_DIR, "adapter_config.json").exists():
        model = PeftModel.from_pretrained(base, OUT_DIR)
    else:
        model = base
    tok = AutoTokenizer.from_pretrained(OUT_DIR if Path(OUT_DIR, "tokenizer_config.json").exists() else args.model,
                                       trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model.eval()

    # CHANGE_ME: 这里换成题目给的 test 集加载
    test_ds = load_dataset("openai/gsm8k", "main", split="test[:50]")
    Path(SUBMIT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(SUBMIT_PATH, "w") as f:
        for ex in test_ds:
            msgs = [
                {"role": "system", "content": "Reason step by step. Put final answer in \\boxed{N}."},
                {"role": "user", "content": ex["question"]},
            ]
            text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            inp = tok(text, return_tensors="pt").to(model.device)
            out = model.generate(**inp, max_new_tokens=512, do_sample=False)
            ans = tok.decode(out[0][inp.input_ids.shape[1]:], skip_special_tokens=True)
            f.write(json.dumps({"question": ex["question"], "answer": ans,
                                "pred": extract_boxed(ans)}, ensure_ascii=False) + "\n")
    print(f"[OK] predictions → {SUBMIT_PATH}")


# ============================================================
# 6) CLI
# ============================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=MODEL_PATH)
    p.add_argument("--model_size", choices=["0.5B", "1.5B", "3B", "7B"], default=None,
                   help="快捷选 Qwen 尺寸（覆盖 --model）")
    p.add_argument("--qlora", action="store_true", default=True)
    p.add_argument("--no_qlora", dest="qlora", action="store_false")
    p.add_argument("--use_vllm", action="store_true",
                   help="开 vLLM colocate 加速生成（强烈推荐，~3x 提速）")
    p.add_argument("--lr", type=float, default=1e-5)
    p.add_argument("--batch", type=int, default=4)
    p.add_argument("--grad_accum", type=int, default=2)
    p.add_argument("--num_gen", type=int, default=8)
    p.add_argument("--max_prompt", type=int, default=512)
    p.add_argument("--max_completion", type=int, default=512)
    p.add_argument("--epochs", type=float, default=1.0)
    p.add_argument("--steps", type=int, default=300,
                   help="DeepSeek 推荐 300+ 步开始见效")
    p.add_argument("--do_train", action="store_true", default=True)
    p.add_argument("--do_predict", action="store_true")
    args = p.parse_args()

    if args.model_size:
        args.model = f"Qwen/Qwen2.5-{args.model_size}-Instruct"

    if args.do_train:
        train(args)
    if args.do_predict:
        predict(args)


if __name__ == "__main__":
    main()

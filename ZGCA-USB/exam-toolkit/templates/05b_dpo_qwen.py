"""
DPO 微调 Qwen 小模型 - GRPO 的备选（题目给 preference pair 时用）
==============================================================

何时选 DPO 而不是 GRPO：
  - 数据是 (prompt, chosen, rejected) 三元组
  - 题目里出现 "preference" / "偏好对" / "human feedback" / "对齐"
  - 没有可验证的 reward function

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. MODEL_PATH        - 题目给的 ckpt 路径
  2. DATASET_LOAD()    - 题目给的 preference dataset 接口
  3. OUT_DIR           - 一般 /vepfs/problemX/ckpts
  4. SUBMIT_PATH       - 题目要求的提交文件位置
  5. beta              - DPO 温度（默认 0.1，越大越保守）

依赖（现场 pip install）:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      trl peft bitsandbytes accelerate datasets

显存预算 (A100 80G):
  Qwen2.5-0.5B + QLoRA 4bit + batch 8  → ~10 GB
  Qwen2.5-1.5B + QLoRA 4bit + batch 4  → ~18 GB
  Qwen2.5-3B   + QLoRA 4bit + batch 2  → ~32 GB
  Qwen2.5-7B   + QLoRA 4bit + batch 1  → ~50 GB

运行:
  python 05b_dpo_qwen.py --do_train --do_predict
  python 05b_dpo_qwen.py --model_size 1.5B --steps 500
"""

import argparse
import json
import os
from pathlib import Path

import torch
from datasets import load_dataset, Dataset
from peft import LoraConfig
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from trl import DPOTrainer, DPOConfig


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
MODEL_PATH = os.environ.get("MODEL_PATH", "Qwen/Qwen2.5-0.5B-Instruct")
OUT_DIR = os.environ.get("OUT_DIR", "/vepfs/problemX/dpo_out")
SUBMIT_PATH = os.environ.get("SUBMIT_PATH", "/vepfs/problemX/predictions.jsonl")


def DATASET_LOAD():
    """CHANGE_ME: 换成题目给定的 preference dataset 接口

    返回 datasets.Dataset，每行必须有 'prompt' / 'chosen' / 'rejected' 三列。
    'prompt' 是 raw string 或 chat-template 序列化后的 string。
    """
    # 示例：UltraFeedback
    ds = load_dataset("trl-lib/ultrafeedback_binarized", split="train[:2000]")
    # 该数据集已经是 prompt/chosen/rejected 三列，直接用
    return ds


# ============================================================
# 2) MODEL LOADING (QLoRA)
# ============================================================
def build_model_and_tokenizer(model_path: str, use_qlora: bool = True):
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    # DPO 推荐 right padding（不像 GRPO 生成需要 left）
    tok.padding_side = "right"

    quant_cfg = None
    if use_qlora:
        quant_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=quant_cfg,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    return model, tok


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
# 3) TRAIN
# ============================================================
def train(args):
    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    model, tok = build_model_and_tokenizer(args.model, args.qlora)
    train_ds = DATASET_LOAD()

    cfg = DPOConfig(
        output_dir=OUT_DIR,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        max_length=args.max_length,
        max_prompt_length=args.max_prompt,
        num_train_epochs=args.epochs,
        max_steps=args.steps,
        logging_steps=10,
        save_steps=200,
        save_total_limit=2,
        bf16=True,
        gradient_checkpointing=True,
        beta=args.beta,                   # DPO 温度，0.1 是论文默认
        loss_type=args.loss_type,         # "sigmoid"(原版) / "ipo" / "kto_pair"
        report_to="none",
        seed=42,
    )

    # ref_model=None 时 TRL 会自动 freeze 一份 base 作为 ref（QLoRA 推荐用这种）
    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=cfg,
        train_dataset=train_ds,
        processing_class=tok,
        peft_config=build_peft_config() if args.qlora else None,
    )
    trainer.train()
    trainer.save_model(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    print(f"[OK] saved to {OUT_DIR}")


# ============================================================
# 4) PREDICT
# ============================================================
@torch.no_grad()
def predict(args):
    from peft import PeftModel

    base = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="auto",
        trust_remote_code=True,
    )
    if Path(OUT_DIR, "adapter_config.json").exists():
        model = PeftModel.from_pretrained(base, OUT_DIR)
    else:
        model = base
    tok = AutoTokenizer.from_pretrained(
        OUT_DIR if Path(OUT_DIR, "tokenizer_config.json").exists() else args.model,
        trust_remote_code=True,
    )
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model.eval()

    # CHANGE_ME: 这里换成题目给的 test 集
    test_ds = load_dataset("trl-lib/ultrafeedback_binarized", split="test[:50]")
    Path(SUBMIT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(SUBMIT_PATH, "w") as f:
        for ex in test_ds:
            prompt = ex["prompt"]
            inp = tok(prompt, return_tensors="pt", truncation=True,
                      max_length=args.max_prompt).to(model.device)
            out = model.generate(**inp, max_new_tokens=512, do_sample=False)
            ans = tok.decode(out[0][inp.input_ids.shape[1]:],
                             skip_special_tokens=True)
            f.write(json.dumps({"prompt": prompt, "answer": ans},
                               ensure_ascii=False) + "\n")
    print(f"[OK] predictions → {SUBMIT_PATH}")


# ============================================================
# 5) CLI
# ============================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=MODEL_PATH)
    p.add_argument("--model_size", choices=["0.5B", "1.5B", "3B", "7B"], default=None)
    p.add_argument("--qlora", action="store_true", default=True)
    p.add_argument("--no_qlora", dest="qlora", action="store_false")
    p.add_argument("--lr", type=float, default=5e-6)
    p.add_argument("--batch", type=int, default=4)
    p.add_argument("--grad_accum", type=int, default=2)
    p.add_argument("--max_length", type=int, default=1024)
    p.add_argument("--max_prompt", type=int, default=512)
    p.add_argument("--epochs", type=float, default=1.0)
    p.add_argument("--steps", type=int, default=500)
    p.add_argument("--beta", type=float, default=0.1)
    p.add_argument("--loss_type", default="sigmoid",
                   choices=["sigmoid", "ipo", "kto_pair"])
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

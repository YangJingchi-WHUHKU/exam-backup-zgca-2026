"""
PPO 微调 Qwen 小模型 - GRPO/DPO 的备选（题目明确要 PPO 时用）
==========================================================

何时选 PPO 而不是 GRPO/DPO：
  - 题面明确说 "PPO" / "policy/value 双网络" / "actor-critic"
  - 题目给了独立的 reward model checkpoint
  - 要求复现 "InstructGPT 三阶段" 中的 RLHF 阶段

两条实现路径：
  (A) 完整 PPO：actor + critic + ref + reward 四模型同时在显存
      A100 80G 上 0.5B 模型勉强能跑（开 QLoRA 后 ~45 GB）
  (B) 简化 PPO：用 frozen reward function（规则/小模型）代替 reward model
      显存预算 ~一半，工程更稳，考场首选

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. MODEL_PATH        - SFT 后的 actor ckpt 路径
  2. REWARD_MODEL_PATH - 题目给的 reward model（路径 A）；None 时走路径 B
  3. REWARD_FN         - 自定义 reward 函数（路径 B）
  4. DATASET_LOAD()    - prompt-only 数据集
  5. OUT_DIR / SUBMIT_PATH

依赖（现场 pip install）:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      trl peft bitsandbytes accelerate datasets

显存预算 (A100 80G):
  路径 A（4 模型，QLoRA）: 0.5B → ~45 GB，1.5B → ~70 GB（边界）
  路径 B（2 模型，QLoRA）: 0.5B → ~20 GB，1.5B → ~35 GB，3B → ~60 GB

运行:
  # 路径 A（题目给了 reward model）
  python 05c_ppo_qwen.py --reward_model /path/to/rm --do_train --do_predict
  # 路径 B（自己写 reward function）
  python 05c_ppo_qwen.py --reward_fn rule --do_train --do_predict
"""

import argparse
import json
import os
import re
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
MODEL_PATH = os.environ.get("MODEL_PATH", "Qwen/Qwen2.5-0.5B-Instruct")
REWARD_MODEL_PATH = os.environ.get("REWARD_MODEL_PATH", "")  # 空 = 路径 B
OUT_DIR = os.environ.get("OUT_DIR", "/vepfs/problemX/ppo_out")
SUBMIT_PATH = os.environ.get("SUBMIT_PATH", "/vepfs/problemX/predictions.jsonl")


def DATASET_LOAD():
    """CHANGE_ME: 换成题目给的 prompt 数据集。PPO 只需要 prompt，不要 chosen/rejected。"""
    ds = load_dataset("openai/gsm8k", "main", split="train[:500]")
    def to_prompt(ex):
        return {"prompt": ex["question"], "gold": _extract_gsm8k(ex["answer"])}
    return ds.map(to_prompt, remove_columns=ds.column_names)


def _extract_gsm8k(text: str) -> str:
    m = re.search(r"####\s*(-?\d+(?:\.\d+)?)", text)
    return m.group(1).strip() if m else ""


# ============================================================
# 2) REWARD FUNCTION（路径 B）
# ============================================================
def reward_rule(prompts, completions, golds=None, **kw):
    """规则 reward：从 completion 抽 \\boxed{N} 对比 gold。

    返回 list[float]，每个 [-1, 1] 范围。PPO 需要 reward 有正有负才稳。
    """
    rewards = []
    for c, g in zip(completions, golds or [None] * len(completions)):
        m = re.search(r"\\boxed\{([^}]+)\}", c)
        if not m:
            rewards.append(-0.5)  # 格式错
            continue
        pred = m.group(1).strip()
        try:
            ok = abs(float(pred) - float(g)) < 1e-6
        except (ValueError, TypeError):
            ok = pred == g
        rewards.append(1.0 if ok else -0.2)
    return rewards


# ============================================================
# 3) MODEL LOADING
# ============================================================
def _quant_cfg():
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )


def _peft_cfg():
    return LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )


def build_actor(model_path: str, use_qlora: bool = True):
    """Actor with value head. TRL 用 AutoModelForCausalLMWithValueHead。"""
    from trl import AutoModelForCausalLMWithValueHead
    model = AutoModelForCausalLMWithValueHead.from_pretrained(
        model_path,
        quantization_config=_quant_cfg() if use_qlora else None,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        peft_config=_peft_cfg() if use_qlora else None,
        trust_remote_code=True,
    )
    return model


def build_reward_model(rm_path: str):
    """加载题目给的 reward model（一个 sequence classification head 的 backbone）。"""
    from transformers import AutoModelForSequenceClassification
    rm = AutoModelForSequenceClassification.from_pretrained(
        rm_path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        num_labels=1,
        trust_remote_code=True,
    )
    rm.eval()
    return rm


# ============================================================
# 4) TRAIN
# ============================================================
def train(args):
    """注意：TRL 的 PPO API 在版本间变动很大。

    本模板用 PPOTrainer（旧版）的接口风格写。如果 trl >= 0.13 默认是 PPOv2，
    需要把 PPOTrainer 换成 PPOv2Trainer，并加 value_model 参数。
    """
    from trl import PPOTrainer, PPOConfig

    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"  # 生成要左 padding

    actor = build_actor(args.model, args.qlora)
    rm = build_reward_model(args.reward_model) if args.reward_model else None

    cfg = PPOConfig(
        learning_rate=args.lr,
        batch_size=args.batch,
        mini_batch_size=args.mini_batch,
        ppo_epochs=args.ppo_epochs,
        cliprange=0.2,
        cliprange_value=0.2,
        vf_coef=0.1,
        kl_penalty="kl",
        init_kl_coef=0.2,
        target_kl=6.0,
        seed=42,
    )

    train_ds = DATASET_LOAD()
    trainer = PPOTrainer(
        config=cfg,
        model=actor,
        ref_model=None,                  # None → TRL 自动 frozen copy
        tokenizer=tok,
        dataset=train_ds,
    )

    gen_kwargs = dict(
        max_new_tokens=args.max_new_tokens,
        do_sample=True,
        top_p=0.9,
        temperature=1.0,
        pad_token_id=tok.eos_token_id,
    )

    step = 0
    for epoch in range(args.epochs):
        for batch in trainer.dataloader:
            queries = [tok(p, return_tensors="pt").input_ids[0].to(actor.pretrained_model.device)
                       for p in batch["prompt"]]
            # 1) generate
            responses = trainer.generate(queries, return_prompt=False, **gen_kwargs)
            decoded = [tok.decode(r, skip_special_tokens=True) for r in responses]

            # 2) reward
            if rm is not None:
                # 路径 A：reward model 打分
                texts = [p + r for p, r in zip(batch["prompt"], decoded)]
                with torch.no_grad():
                    enc = tok(texts, return_tensors="pt", padding=True, truncation=True,
                              max_length=1024).to(rm.device)
                    scores = rm(**enc).logits.squeeze(-1).float().tolist()
                rewards = [torch.tensor(s) for s in scores]
            else:
                # 路径 B：rule reward
                fn = {"rule": reward_rule}[args.reward_fn]
                scores = fn(prompts=batch["prompt"], completions=decoded,
                            golds=batch.get("gold"))
                rewards = [torch.tensor(s) for s in scores]

            # 3) PPO step
            stats = trainer.step(queries, responses, rewards)
            if step % 10 == 0:
                mean_r = sum(s for s in scores) / max(len(scores), 1)
                print(f"step={step} mean_reward={mean_r:.3f}")
            step += 1
            if args.steps and step >= args.steps:
                break
        if args.steps and step >= args.steps:
            break

    trainer.save_pretrained(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    print(f"[OK] saved to {OUT_DIR}")


# ============================================================
# 5) PREDICT
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

    test_ds = load_dataset("openai/gsm8k", "main", split="test[:50]")
    Path(SUBMIT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(SUBMIT_PATH, "w") as f:
        for ex in test_ds:
            inp = tok(ex["question"], return_tensors="pt").to(model.device)
            out = model.generate(**inp, max_new_tokens=512, do_sample=False)
            ans = tok.decode(out[0][inp.input_ids.shape[1]:],
                             skip_special_tokens=True)
            f.write(json.dumps({"question": ex["question"], "answer": ans},
                               ensure_ascii=False) + "\n")
    print(f"[OK] predictions → {SUBMIT_PATH}")


# ============================================================
# 6) CLI
# ============================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=MODEL_PATH)
    p.add_argument("--reward_model", default=REWARD_MODEL_PATH,
                   help="路径 A：题目给的 reward model 路径；空 = 用 reward_fn")
    p.add_argument("--reward_fn", default="rule", choices=["rule"],
                   help="路径 B：自定义 reward 函数名")
    p.add_argument("--qlora", action="store_true", default=True)
    p.add_argument("--lr", type=float, default=1e-5)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--mini_batch", type=int, default=2)
    p.add_argument("--ppo_epochs", type=int, default=4)
    p.add_argument("--max_new_tokens", type=int, default=256)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--steps", type=int, default=200,
                   help="PPO 总 step 数，0 = 跑完整 epoch")
    p.add_argument("--do_train", action="store_true", default=True)
    p.add_argument("--do_predict", action="store_true")
    args = p.parse_args()

    if args.do_train:
        train(args)
    if args.do_predict:
        predict(args)


if __name__ == "__main__":
    main()

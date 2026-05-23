"""
RL 微调生物序列 (蛋白/DNA) - 押宝 bio+RL 压轴组合题
=======================================================

思路：用 RL 调一个生成模型 (Qwen / ESM-style)，让它生成的序列在某个 frozen
预测器上的得分更高。两条路径任选其一：

  (A) PPO 路径 (主推)：trl.PPOTrainer + reward = frozen_predictor(seq)
  (B) Best-of-N + SFT 路径 (兜底)：sample → 评分 → 高分样本拿来 SFT
      不需要 PPO/GRPO，2 小时内必能跑完一轮

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. BASE_MODEL_PATH    - 序列生成模型（题目通常给个 Qwen 或 ESM）
  2. REWARD_MODEL_PATH  - frozen reward predictor（题目通常给个活性预测器）
  3. PROMPT_DATASET     - 起始 prompt 数据集（题目给，否则用 [BOS]）
  4. ALPHABET           - 序列字母表：蛋白 = 20AA, DNA = ACGT
  5. SEQ_LEN            - 生成序列长度（必须符合题面要求）
  6. OUT_DIR            - 输出 ckpt 目录
  7. REWARD_FN          - 怎么把生成的字符串变成 reward float（最容易写错）

依赖（现场 pip install）:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      trl peft accelerate transformers bitsandbytes datasets

显存预算 (A100 80G):
  Qwen2.5-0.5B + QLoRA + PPO + reward model 100M → ~18 GB
  Qwen2.5-1.5B + QLoRA + PPO + reward model 650M → ~32 GB
  Qwen2.5-3B   + QLoRA + PPO + reward model 1.2B → ~60 GB (边界)
  Best-of-N 路径：上面 - 10GB 左右（不用算 advantage）

运行:
  # 主路径：PPO
  python 07_rl_protein_design.py --mode ppo --steps 200

  # 兜底：Best-of-N + SFT
  python 07_rl_protein_design.py --mode bon --rounds 5 --n_samples 64 --topk 16

参考资料（toolkit 内）:
  refs/RLfinetuning_Diffusion_Bioseq/   - 生物序列 RL 综述代码
  refs/DRAKES/                          - 离散扩散 + reward 反传
"""

import argparse
import json
import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).parent))
from _common.trainer import Trainer, TrainConfig  # noqa: E402


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
BASE_MODEL_PATH = os.environ.get("BASE_MODEL_PATH", "Qwen/Qwen2.5-0.5B-Instruct")
REWARD_MODEL_PATH = os.environ.get("REWARD_MODEL_PATH", "/vepfs-readonly/problemX/reward_model")
OUT_DIR = os.environ.get("OUT_DIR", "/vepfs/problemX/rl_out")

ALPHABET_PROTEIN = "ACDEFGHIKLMNPQRSTVWY"
ALPHABET_DNA = "ACGT"
ALPHABET = ALPHABET_PROTEIN  # CHANGE_ME: 蛋白题 = PROTEIN，DNA 题 = DNA

SEQ_LEN = 100  # CHANGE_ME: 题目通常给定
PROMPT_TEMPLATE = "Design a protein sequence: "  # CHANGE_ME


# ============================================================
# 2) REWARD: 调用 frozen predictor 给生成序列打分
# ============================================================
class RewardModel:
    """
    把生成的字符串序列变成 reward float。

    CHANGE_ME: 大概率题目会给一个预训练好的预测器，按以下两种情况选：
      - HF AutoModel  → 用 transformers 加载
      - ESM-style     → 用 esm.pretrained.load_model_and_alphabet_core
    """

    def __init__(self, path: str, device: str = "cuda"):
        from transformers import AutoModel, AutoTokenizer
        self.device = device
        self.tok = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        # 通常 reward model 也是一个带回归/分类头的 backbone
        self.model = AutoModel.from_pretrained(path, trust_remote_code=True,
                                                torch_dtype=torch.bfloat16).to(device)
        self.model.eval()
        for p in self.model.parameters():
            p.requires_grad = False
        # 题目可能给的是一个 score head；这里默认用 mean pooling 后取第一维
        self.score_head = None
        head_path = Path(path) / "score_head.pt"
        if head_path.exists():
            self.score_head = torch.load(head_path, map_location=device, weights_only=False)

    @torch.no_grad()
    def score(self, sequences: list) -> torch.Tensor:
        """sequences: list[str] → tensor[B] float reward"""
        # 过滤非法字符（生成的可能含字母表外的 token）
        cleaned = ["".join(c for c in s if c in ALPHABET) for s in sequences]
        # 全空字符串给最低 reward
        rewards = torch.zeros(len(cleaned), device=self.device)
        nonempty = [i for i, s in enumerate(cleaned) if len(s) >= 5]
        if not nonempty:
            return rewards
        enc = self.tok([cleaned[i] for i in nonempty],
                        padding=True, truncation=True, max_length=512,
                        return_tensors="pt").to(self.device)
        out = self.model(**enc)
        hidden = out.last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1).float()
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
        if self.score_head is not None:
            scores = self.score_head(pooled).squeeze(-1)
        else:
            # 兜底：取 pooled 第一维当 reward；现场建议改成真的 head
            scores = pooled[:, 0].float()
        for i, idx in enumerate(nonempty):
            rewards[idx] = scores[i]
        return rewards


# ============================================================
# 3) GENERATOR: 序列生成模型
# ============================================================
def build_generator(model_path: str, use_qlora: bool = True):
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"  # 生成必须左 padding

    qcfg = None
    if use_qlora:
        qcfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
    model = AutoModelForCausalLM.from_pretrained(
        model_path, trust_remote_code=True,
        quantization_config=qcfg, device_map="auto",
        torch_dtype=torch.bfloat16 if not use_qlora else None,
    )
    return model, tok


def extract_sequence(generated_text: str) -> str:
    """从模型输出抽取生物序列：保留字母表内字符"""
    return "".join(c for c in generated_text.upper() if c in ALPHABET)


# ============================================================
# 4) PATH A: PPO  (主推)
# ============================================================
def run_ppo(args):
    """
    用 TRL PPOTrainer。注意 TRL 0.11+ 接口 vs 旧版 0.7 接口差异较大；
    这里写 0.11+ 接口，旧版 README 改一下 import 即可。
    """
    from trl import PPOConfig, PPOTrainer
    from peft import LoraConfig

    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    model, tok = build_generator(args.base_model, use_qlora=args.qlora)
    reward = RewardModel(args.reward_model, device="cuda")

    # 起始 prompt：CHANGE_ME 如果题目给了 prompt 数据集
    prompts = [PROMPT_TEMPLATE] * args.batch * args.steps

    cfg = PPOConfig(
        output_dir=OUT_DIR,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch,
        mini_batch_size=args.batch,
        num_ppo_epochs=4,
        kl_coef=0.05,
        seed=42,
        bf16=True,
        report_to="none",
    )

    peft_cfg = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    ) if args.qlora else None

    trainer = PPOTrainer(
        config=cfg,
        model=model,
        tokenizer=tok,
        reward_model=None,  # 用回调式 reward
        peft_config=peft_cfg,
    )

    # 简化循环：rollout → score → step
    # 旧版/新版 TRL 接口差异极大，这里给"自己写循环"的写法，更稳
    gen_kwargs = dict(
        max_new_tokens=args.seq_len,
        do_sample=True, top_p=0.95, top_k=50,
        temperature=1.0, pad_token_id=tok.pad_token_id,
    )

    for step in range(args.steps):
        batch_prompts = prompts[step * args.batch:(step + 1) * args.batch]
        inputs = tok(batch_prompts, return_tensors="pt", padding=True).to(model.device)
        out_ids = model.generate(**inputs, **gen_kwargs)
        gen_text = tok.batch_decode(out_ids[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)
        sequences = [extract_sequence(t) for t in gen_text]
        rewards = reward.score(sequences).tolist()

        # TRL 新接口：直接喂 ids + rewards
        # （为了兼容，这里走 .step 接口；如果版本不匹配会报错，README 里降级到 vanilla REINFORCE）
        try:
            stats = trainer.step(
                [inputs.input_ids[i] for i in range(len(batch_prompts))],
                [out_ids[i, inputs.input_ids.shape[1]:] for i in range(len(batch_prompts))],
                [torch.tensor(r) for r in rewards],
            )
            if step % 10 == 0:
                print(f"[ppo] step={step} | reward_mean={sum(rewards)/len(rewards):.4f} "
                      f"| reward_max={max(rewards):.4f} | sample={sequences[0][:30]}...")
        except Exception as e:
            print(f"[ppo] step={step} 失败 ({e})，建议切到 --mode bon")
            break

    trainer.save_model(OUT_DIR)
    print(f"[OK] saved → {OUT_DIR}")


# ============================================================
# 5) PATH B: Best-of-N + SFT  (兜底，最稳)
# ============================================================
class _BoNDataset(Dataset):
    def __init__(self, samples):
        self.samples = samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]


def run_bon_sft(args):
    """
    每轮：
      1. 用当前模型生成 N 个序列
      2. reward 打分
      3. 取 top-K
      4. 在 top-K 上做 SFT 1 个 epoch
    比 PPO 简单 10 倍，且没有 KL 爆炸问题。reward 在 5 轮内通常单调上升。
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    model, tok = build_generator(args.base_model, use_qlora=args.qlora)
    reward = RewardModel(args.reward_model, device="cuda")

    history = []
    for rnd in range(args.rounds):
        # 1) 生成 N
        prompts = [PROMPT_TEMPLATE] * args.n_samples
        all_samples = []
        for i in range(0, args.n_samples, args.batch):
            batch = prompts[i:i + args.batch]
            inputs = tok(batch, return_tensors="pt", padding=True).to(model.device)
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_new_tokens=args.seq_len,
                    do_sample=True, top_p=0.95, top_k=50, temperature=1.0,
                    pad_token_id=tok.pad_token_id,
                )
            gen_text = tok.batch_decode(out[:, inputs.input_ids.shape[1]:],
                                         skip_special_tokens=True)
            sequences = [extract_sequence(t) for t in gen_text]
            rewards = reward.score(sequences).tolist()
            all_samples.extend(zip(sequences, rewards))

        # 2) 取 top-K
        all_samples.sort(key=lambda x: x[1], reverse=True)
        topk = all_samples[:args.topk]
        r_mean = sum(r for _, r in all_samples) / len(all_samples)
        r_top = sum(r for _, r in topk) / len(topk)
        history.append({"round": rnd, "r_mean_all": r_mean, "r_mean_top": r_top})
        print(f"[bon] round={rnd} | r_mean_all={r_mean:.4f} | r_mean_top{args.topk}={r_top:.4f}")

        # 3) SFT on top-K（用 trainer.py 通用循环）
        sft_texts = [PROMPT_TEMPLATE + seq for seq, _ in topk]

        def collate(batch):
            enc = tok(batch, return_tensors="pt", padding=True, truncation=True,
                      max_length=512)
            enc["labels"] = enc["input_ids"].clone()
            enc["labels"][enc["attention_mask"] == 0] = -100
            return enc

        loader = DataLoader(_BoNDataset(sft_texts), batch_size=args.batch,
                             shuffle=True, collate_fn=collate)

        def compute_loss(model, batch):
            batch = {k: v.to(model.device) for k, v in batch.items()}
            out = model(**batch)
            return out.loss, out.logits

        cfg = TrainConfig(
            out_dir=str(Path(OUT_DIR) / f"round_{rnd}"),
            epochs=1, lr=args.lr, warmup_ratio=0.0, scheduler="constant",
            amp=True, amp_dtype="bf16", grad_clip=1.0, log_every=5,
            eval_every_epoch=False, save_best=False,
        )
        Trainer(model, loader, None, compute_loss=compute_loss, eval_fn=None,
                cfg=cfg, device=model.device.type).fit()

    # 保存最终模型 + 历史
    model.save_pretrained(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    with open(Path(OUT_DIR) / "bon_history.json", "w") as f:
        json.dump(history, f, indent=2)
    print(f"[OK] BoN done → {OUT_DIR}")


# ============================================================
# 6) MAIN
# ============================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["ppo", "bon"], default="bon",
                   help="bon = Best-of-N + SFT（推荐，稳）；ppo = TRL PPO（更猛但易爆）")
    p.add_argument("--base_model", default=BASE_MODEL_PATH)
    p.add_argument("--reward_model", default=REWARD_MODEL_PATH)
    p.add_argument("--qlora", action="store_true", default=True)
    p.add_argument("--no_qlora", dest="qlora", action="store_false")
    p.add_argument("--lr", type=float, default=1e-5)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--seq_len", type=int, default=SEQ_LEN)
    # ppo only
    p.add_argument("--steps", type=int, default=200)
    # bon only
    p.add_argument("--rounds", type=int, default=5)
    p.add_argument("--n_samples", type=int, default=64)
    p.add_argument("--topk", type=int, default=16)
    args = p.parse_args()

    if args.mode == "ppo":
        run_ppo(args)
    else:
        run_bon_sft(args)


if __name__ == "__main__":
    main()

"""
DDPO 微调 Stable Diffusion - 押宝 Image + RL 组合题
======================================================

考场可改清单 (CTRL-F 找 "CHANGE_ME"):
  1. BASE_MODEL_PATH   - 题目给的 SD ckpt，如 /vepfs-readonly/problemX/stable-diffusion-v1-5
  2. REWARD_TYPE       - "aesthetic" | "compressibility" | "custom"
  3. EXTERNAL_REWARD   - 如果 REWARD_TYPE="custom"，把题目给的 reward 接口接进来
  4. PROMPT_FN()       - 题目给的 prompt 分布
  5. OUT_DIR           - 一般 /vepfs/problemX/

依赖（现场 pip install）:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      trl peft diffusers accelerate transformers
  # 若用 aesthetic predictor，再加:
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
      open_clip_torch

显存预算 (A100 80G):
  SD 1.5 + LoRA + train_batch_size=4 + sample_batch_size=8 → ~28-32 GB
  SDXL + LoRA + train_batch_size=2 + sample_batch_size=4   → ~55-60 GB
  OOM 时优先降 sample_batch_size，再降 sample_num_steps，最后 train_batch_size

运行:
  python 06_ddpo_diffusion.py --reward_type compressibility --epochs 20
  python 06_ddpo_diffusion.py --reward_type aesthetic --epochs 30
  python 06_ddpo_diffusion.py --reward_type custom

设计要点（README 必写）:
  - DDPO = 把扩散采样视为 MDP，用 PPO 风格 policy gradient 优化 reward
  - LoRA 必开（全量微调显存不够，且容易塌）
  - KL 约束由 PPO clip 隐式提供（DDPO 默认 ratio clip = 1e-4）
  - reward 三种范式: aesthetic / compressibility / 题目给的 custom

参考: refs/ddpo-pytorch/ + HF blog: trl-ddpo
"""

import argparse
import io
import os
from pathlib import Path
from typing import Callable, List

import numpy as np
import torch
from PIL import Image


# ============================================================
# 1) CONFIG - CHANGE_ME
# ============================================================
BASE_MODEL_PATH = os.environ.get("BASE_MODEL_PATH", "runwayml/stable-diffusion-v1-5")
OUT_DIR = os.environ.get("OUT_DIR", "/vepfs/problemX/ddpo_out")
REWARD_TYPE = os.environ.get("REWARD_TYPE", "compressibility")  # 最稳, 不依赖外部权重


# 题目通常给一个固定 prompt 列表或可调用对象。这里给一个简单示例。
DEFAULT_PROMPTS = [
    "a photograph of a cat",
    "a photograph of a dog",
    "a painting of a horse running on the beach",
    "an astronaut riding a horse on mars",
    "a vase of flowers on a wooden table",
    "a mountain landscape at sunset",
    "a robot playing chess in a library",
    "a steaming bowl of ramen on a kitchen counter",
]


def PROMPT_FN():
    """
    DDPO 要求传一个返回 (prompt, prompt_metadata) 的函数。
    CHANGE_ME: 换成题目给的 prompt 分布。
    """
    p = np.random.choice(DEFAULT_PROMPTS)
    return p, {}


# ============================================================
# 2) REWARD FUNCTIONS
# ============================================================
# 所有 reward fn 接口: fn(images, prompts, prompt_metadata) -> (rewards, info_dict)
#   images: List[PIL.Image] 或 (B, H, W, 3) uint8 numpy
#   返回 rewards: numpy 数组 / list，每条样本一个 scalar

def reward_compressibility(images, prompts, metadata):
    """
    JPEG 可压缩度 = -filesize（越小越好，所以取负数让 DDPO 朝"难压缩"方向走）
    经典 DDPO 论文里的稳定 reward，不依赖外部模型。
    如果题面要"鼓励简洁画面"，把符号改回 +filesize 即可。
    """
    rewards = []
    for img in images:
        if isinstance(img, np.ndarray):
            img = Image.fromarray(img)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        rewards.append(-len(buf.getvalue()) / 1024.0)  # 单位 KB
    return np.array(rewards, dtype=np.float32), {}


_AES_MODEL = None  # lazy load


def reward_aesthetic(images, prompts, metadata):
    """
    LAION aesthetic predictor: 在 CLIP ViT-L/14 之上跑一个 MLP 打 [1,10] 美学分。
    需要题目允许 pip install open_clip_torch + 提供 aesthetic 权重。
    CHANGE_ME: AES_WEIGHT_PATH
    """
    global _AES_MODEL
    if _AES_MODEL is None:
        # 这里写一个最小可用的 stub，考场要换成 LAION 官方权重
        import open_clip
        clip_model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-L-14", pretrained="openai")
        clip_model = clip_model.cuda().eval()
        mlp = torch.nn.Sequential(
            torch.nn.Linear(768, 1024), torch.nn.Dropout(0.2),
            torch.nn.Linear(1024, 128), torch.nn.Dropout(0.2),
            torch.nn.Linear(128, 64), torch.nn.Dropout(0.1),
            torch.nn.Linear(64, 16), torch.nn.Linear(16, 1),
        ).cuda().eval()
        # CHANGE_ME: 加载 LAION aesthetic predictor 权重
        # mlp.load_state_dict(torch.load("AES_WEIGHT_PATH"))
        _AES_MODEL = (clip_model, preprocess, mlp)

    clip_model, preprocess, mlp = _AES_MODEL
    rewards = []
    with torch.no_grad():
        for img in images:
            if isinstance(img, np.ndarray):
                img = Image.fromarray(img)
            inp = preprocess(img).unsqueeze(0).cuda()
            feat = clip_model.encode_image(inp)
            feat = feat / feat.norm(dim=-1, keepdim=True)
            score = mlp(feat.float()).item()
            rewards.append(score)
    return np.array(rewards, dtype=np.float32), {}


def reward_custom(images, prompts, metadata):
    """
    CHANGE_ME: 题目通常会给一个 reward_model / scorer 接口。
    示例: external_score(image, prompt) -> float
    """
    # ----- 把题目接口接到这里 -----
    # from problem_reward import external_score
    # rewards = [external_score(img, p) for img, p in zip(images, prompts)]
    rewards = [0.0 for _ in images]   # 占位，避免 import 失败
    return np.array(rewards, dtype=np.float32), {}


REWARD_REGISTRY = {
    "compressibility": reward_compressibility,
    "aesthetic": reward_aesthetic,
    "custom": reward_custom,
}


def make_multi_reward(weights: dict) -> Callable:
    """组合多 reward, weights={"compressibility": 1.0, "aesthetic": 0.5}。"""
    fns = [(REWARD_REGISTRY[k], w) for k, w in weights.items()]

    def combined(images, prompts, metadata):
        total = None
        info = {}
        for fn, w in fns:
            r, sub_info = fn(images, prompts, metadata)
            total = r * w if total is None else total + r * w
            info.update({f"{fn.__name__}/{k}": v for k, v in sub_info.items()})
        return total, info

    return combined


# ============================================================
# 3) MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", default=BASE_MODEL_PATH)
    parser.add_argument("--out_dir", default=OUT_DIR)
    parser.add_argument("--reward_type", default=REWARD_TYPE,
                        choices=["compressibility", "aesthetic", "custom"])
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--sample_num_steps", type=int, default=50)
    parser.add_argument("--train_batch_size", type=int, default=4)
    parser.add_argument("--sample_batch_size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--lora_rank", type=int, default=4)
    parser.add_argument("--use_lora", action="store_true", default=True)
    args = parser.parse_args()

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    # 延迟 import：trl/diffusers 装包可能慢
    from trl import DDPOConfig, DDPOTrainer, DefaultDDPOStableDiffusionPipeline

    pipeline = DefaultDDPOStableDiffusionPipeline(
        args.base_model,
        pretrained_model_revision="main",
        use_lora=args.use_lora,
    )

    cfg = DDPOConfig(
        num_epochs=args.epochs,
        train_gradient_accumulation_steps=1,
        sample_num_steps=args.sample_num_steps,
        sample_batch_size=args.sample_batch_size,
        train_batch_size=args.train_batch_size,
        sample_num_batches_per_epoch=4,
        per_prompt_stat_tracking=True,
        per_prompt_stat_tracking_buffer_size=32,
        tracker_project_name="ddpo_exam",
        log_with=None,
        project_kwargs={"logging_dir": args.out_dir},
        train_learning_rate=args.lr,
        # PPO clip = 隐式 KL 约束（DDPO 论文做法）
        train_cfg=1.0,           # classifier-free guidance scale during sampling
    )

    reward_fn = REWARD_REGISTRY[args.reward_type]
    print(f"[reward] using {args.reward_type}")

    trainer = DDPOTrainer(
        cfg,
        reward_function=reward_fn,
        prompt_function=PROMPT_FN,
        sd_pipeline=pipeline,
    )
    trainer.train()

    save_dir = Path(args.out_dir) / "lora_final"
    trainer.save_pretrained(str(save_dir))
    print(f"[OK] DDPO LoRA → {save_dir}")


if __name__ == "__main__":
    main()

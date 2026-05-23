"""
通用训练循环 - 所有非 RL 题共用
====================================
用法（在你的题模板里）:
    from _common.trainer import Trainer, TrainConfig
    trainer = Trainer(model, optimizer, scheduler, criterion,
                      train_loader, val_loader,
                      cfg=TrainConfig(epochs=5, amp=True, ...))
    trainer.fit()

特性:
  - AdamW + warmup + 余弦/线性退火
  - AMP (bf16/fp16) + GradScaler
  - 梯度裁剪
  - 双格式日志 (train.log + 控制台)
  - 最优 checkpoint 自动保存
  - 验证集指标可配置 (返回 dict, 通常含 "metric" 键)
"""

import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import LambdaLR
from torch.utils.data import DataLoader


@dataclass
class TrainConfig:
    out_dir: str = "./ckpts"
    epochs: int = 5
    lr: float = 3e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.05
    scheduler: str = "cosine"           # "cosine" | "linear" | "constant"
    amp: bool = True
    amp_dtype: str = "bf16"             # "bf16" | "fp16" - A100 推荐 bf16
    grad_clip: float = 1.0
    log_every: int = 20
    eval_every_epoch: bool = True
    save_best: bool = True
    metric_higher_better: bool = True   # accuracy/pearson → True; loss → False
    log_file: str = "train.log"


def get_scheduler(optimizer, total_steps: int, cfg: TrainConfig) -> LambdaLR:
    warmup = max(1, int(cfg.warmup_ratio * total_steps))

    def lr_lambda(step):
        if step < warmup:
            return step / warmup
        progress = (step - warmup) / max(1, total_steps - warmup)
        if cfg.scheduler == "cosine":
            return 0.5 * (1 + math.cos(math.pi * progress))
        if cfg.scheduler == "linear":
            return max(0.0, 1 - progress)
        return 1.0

    return LambdaLR(optimizer, lr_lambda)


def setup_logger(log_path: str) -> logging.Logger:
    logger = logging.getLogger("trainer")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s",
                            datefmt="%H:%M:%S")
    fh = logging.FileHandler(log_path, mode="w")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


class Trainer:
    def __init__(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: Optional[DataLoader],
        compute_loss: Callable,            # fn(model, batch) -> (loss, logits)
        eval_fn: Optional[Callable] = None,  # fn(model, val_loader, device) -> dict
        cfg: TrainConfig = TrainConfig(),
        device: str = "cuda",
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.compute_loss = compute_loss
        self.eval_fn = eval_fn
        self.cfg = cfg
        self.device = device

        Path(cfg.out_dir).mkdir(parents=True, exist_ok=True)
        self.log = setup_logger(str(Path(cfg.out_dir) / cfg.log_file))

        # Optimizer：把 no_decay 参数分组
        no_decay = ("bias", "LayerNorm.weight", "layer_norm.weight")
        groups = [
            {"params": [p for n, p in model.named_parameters()
                        if p.requires_grad and not any(nd in n for nd in no_decay)],
             "weight_decay": cfg.weight_decay},
            {"params": [p for n, p in model.named_parameters()
                        if p.requires_grad and any(nd in n for nd in no_decay)],
             "weight_decay": 0.0},
        ]
        self.optimizer = AdamW(groups, lr=cfg.lr)

        total_steps = len(train_loader) * cfg.epochs
        self.scheduler = get_scheduler(self.optimizer, total_steps, cfg)

        self.scaler = torch.amp.GradScaler("cuda") if cfg.amp and cfg.amp_dtype == "fp16" else None
        self.amp_dtype = torch.bfloat16 if cfg.amp_dtype == "bf16" else torch.float16

        self.best_metric = -float("inf") if cfg.metric_higher_better else float("inf")
        self.global_step = 0

    def _amp_ctx(self):
        if self.cfg.amp:
            return torch.amp.autocast("cuda", dtype=self.amp_dtype)
        return torch.cuda.amp.autocast(enabled=False)

    def train_step(self, batch) -> float:
        self.model.train()
        self.optimizer.zero_grad()
        with self._amp_ctx():
            loss, _ = self.compute_loss(self.model, batch)

        if self.scaler:
            self.scaler.scale(loss).backward()
            self.scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.cfg.grad_clip)
            self.scaler.step(self.optimizer)
            self.scaler.update()
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.cfg.grad_clip)
            self.optimizer.step()
        self.scheduler.step()
        return loss.item()

    def fit(self):
        t0 = time.time()
        self.log.info(f"start: epochs={self.cfg.epochs}, steps_per_epoch={len(self.train_loader)}, "
                      f"lr={self.cfg.lr}, amp={self.cfg.amp_dtype if self.cfg.amp else 'off'}")

        for epoch in range(self.cfg.epochs):
            running = 0.0
            for i, batch in enumerate(self.train_loader):
                loss = self.train_step(batch)
                running += loss
                self.global_step += 1
                if self.global_step % self.cfg.log_every == 0:
                    avg = running / self.cfg.log_every
                    lr = self.scheduler.get_last_lr()[0]
                    self.log.info(f"ep {epoch} step {self.global_step} | loss {avg:.4f} | lr {lr:.2e}")
                    running = 0.0

            if self.cfg.eval_every_epoch and self.val_loader is not None and self.eval_fn:
                metrics = self.eval_fn(self.model, self.val_loader, self.device)
                self.log.info(f"ep {epoch} eval | " +
                              " | ".join(f"{k} {v:.4f}" for k, v in metrics.items()))
                self._maybe_save(metrics)

        self.log.info(f"done in {time.time() - t0:.1f}s")

    def _maybe_save(self, metrics: dict):
        if not self.cfg.save_best:
            return
        m = metrics.get("metric", list(metrics.values())[0])
        improved = (m > self.best_metric) if self.cfg.metric_higher_better else (m < self.best_metric)
        if improved:
            self.best_metric = m
            path = Path(self.cfg.out_dir) / "best.pt"
            torch.save({
                "model_state": self.model.state_dict(),
                "metric": m,
                "step": self.global_step,
            }, path)
            self.log.info(f"saved best → {path} (metric={m:.4f})")

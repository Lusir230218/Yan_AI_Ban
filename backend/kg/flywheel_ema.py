"""阶段五·2D 飞轮：EMA + 时间衰减校准核心。

替代主方案的线性 `confidence += 0.05`：
- 无冷却：100 次赞不会涨到 1.0 封顶
- 时间衰减：14 天前的信号权重减半
- 平滑负反馈：踩不会一次扣 0.10

公式：
    new_conf = (1 - α(t)) * old_conf + α(t) * signal
    α(t)     = base_lr * exp(-Δdays / half_life_days)

根据累计用户量切换 base_lr：
    < 10    → 0.0   （噪声过大，直接关闭）
    10-50  → 0.02  （半数学习率）
    ≥ 50    → 0.05  （全速）

最后夹断到 [floor=0.05, ceil=0.95]。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EMAConfig:
    base_lr: float = 0.05
    half_life_days: float = 14.0
    signal_pos: float = 1.0
    signal_neg: float = 0.0
    floor: float = 0.05
    ceil: float = 0.95


# 按用户量阶梯决定学习率
LR_BY_USER_COUNT: list[tuple[float, float]] = [
    (10, 0.0),                # < 10 关闭
    (50, 0.02),               # 10-50 减半
    (float("inf"), 0.05),     # >= 50 全速
]


def learning_rate(user_count: int, cfg: EMAConfig | None = None) -> float:
    """根据累计用户量决定 base_lr。"""
    cfg = cfg or EMAConfig()
    for cap, lr in LR_BY_USER_COUNT:
        if user_count < cap:
            return lr
    # 兜底：理论上 LR_BY_USER_COUNT 已经覆盖到 inf
    return cfg.base_lr


def time_decay(days_since: float, half_life_days: float) -> float:
    """指数半衰期：half_life_days 处的权重 = 0.5。

    实现：2^(-Δdays / half_life_days)。
    注意：exp(-Δdays / half_life_days) 是 e-folding time（半衰期处 = e^-1 ≈ 0.368），
    不是真正的"半衰期"。题目里"half_life"语义要求严格减半，所以用 2 的幂。
    """
    if half_life_days <= 0:
        return 1.0  # 防御：half_life_days 无效时无衰减
    return math.pow(2.0, -days_since / half_life_days)


def update(
    old_conf: float,
    signal: float,
    days_since_last: float,
    user_count: int,
    cfg: EMAConfig | None = None,
) -> float:
    """单条信号的 EMA 更新。

    Args:
        old_conf: 当前 confidence
        signal:   1.0（赞）/ 0.0（踩）/ 0.5（无信号）
        days_since_last: 上次 confidence 更新距今的天数
        user_count: 累计用户量（决定是否启用 / 学习率多大）

    Returns:
        新的 confidence，夹断到 [cfg.floor, cfg.ceil]
    """
    cfg = cfg or EMAConfig()
    lr = learning_rate(user_count, cfg)
    if lr == 0.0:
        return old_conf
    decay = time_decay(days_since_last, cfg.half_life_days)
    alpha = lr * decay
    new_conf = (1 - alpha) * old_conf + alpha * signal
    return max(cfg.floor, min(cfg.ceil, new_conf))


def batch_update(
    old_conf: float,
    signals: list[tuple[float, datetime]],
    now: datetime,
    user_count: int,
    cfg: EMAConfig | None = None,
) -> float:
    """多条信号按时间顺序依次 EMA 更新。

    Args:
        old_conf: 起始 confidence
        signals:  [(signal, occurred_at), ...]  不要求时间有序
        now:      "当前时间"，所有信号按相对此值算 Δdays
        user_count: 累计用户量

    Returns:
        新的 confidence
    """
    cfg = cfg or EMAConfig()
    lr = learning_rate(user_count, cfg)
    if lr == 0.0:
        return old_conf
    cur = old_conf
    # 按时间先后依次更新（older → newer）
    for sig, occurred in sorted(signals, key=lambda x: x[1]):
        days_since = (now - occurred).total_seconds() / 86400.0
        # 时间不能为负（clock skew 时 fallback 0）
        days_since = max(days_since, 0.0)
        alpha = lr * time_decay(days_since, cfg.half_life_days)
        cur = (1 - alpha) * cur + alpha * sig
    return max(cfg.floor, min(cfg.ceil, cur))
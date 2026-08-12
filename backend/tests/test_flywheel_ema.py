"""flywheel_ema 单测 — 不依赖任何 DB，纯计算验证。"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from kg.flywheel_ema import (
    EMAConfig, batch_update, learning_rate, time_decay, update,
)


# ─────────── learning_rate 阶梯 ───────────


class TestLearningRate:
    def test_lt10_returns_zero(self):
        assert learning_rate(5, EMAConfig()) == 0.0
        assert learning_rate(0, EMAConfig()) == 0.0
        assert learning_rate(9, EMAConfig()) == 0.0

    def test_10_to_50_returns_half(self):
        assert learning_rate(10, EMAConfig()) == 0.02
        assert learning_rate(30, EMAConfig()) == 0.02
        assert learning_rate(49, EMAConfig()) == 0.02

    def test_ge50_returns_full(self):
        assert learning_rate(50, EMAConfig()) == 0.05
        assert learning_rate(100, EMAConfig()) == 0.05
        assert learning_rate(10_000, EMAConfig()) == 0.05


# ─────────── time_decay ───────────


class TestTimeDecay:
    def test_zero_days_is_1(self):
        assert math.isclose(time_decay(0, 14), 1.0)

    def test_half_life_is_half(self):
        assert math.isclose(time_decay(14, 14), 0.5, abs_tol=0.01)

    def test_two_half_lives_is_quarter(self):
        assert math.isclose(time_decay(28, 14), 0.25, abs_tol=0.01)


# ─────────── update 单条信号 ───────────


class TestUpdate:
    def test_positive_signal_lifts(self):
        new = update(0.5, signal=1.0, days_since_last=0, user_count=100)
        # (1-0.05)*0.5 + 0.05*1.0 = 0.475 + 0.05 = 0.525
        assert math.isclose(new, 0.525, abs_tol=1e-9)

    def test_negative_signal_lowers(self):
        new = update(0.5, signal=0.0, days_since_last=0, user_count=100)
        # (1-0.05)*0.5 + 0.05*0.0 = 0.475
        assert math.isclose(new, 0.475, abs_tol=1e-9)

    def test_old_signal_decayed(self):
        new_old = update(0.5, signal=1.0, days_since_last=14, user_count=100)
        new_new = update(0.5, signal=1.0, days_since_last=0, user_count=100)
        assert new_old < new_new

    def test_disabled_when_lt10_users(self):
        for uc in (0, 5, 9):
            assert update(0.5, signal=1.0, days_since_last=0, user_count=uc) == 0.5

    def test_floor_ceiling_applied(self):
        cur = 0.5
        # 100 次正信号 → 应被 ceil=0.95 夹断
        for _ in range(100):
            cur = update(cur, signal=1.0, days_since_last=0, user_count=100)
        assert 0.05 <= cur <= 0.95
        # 公式本身会收敛到 1.0；clamp 把它压回 0.95
        assert cur == 0.95

    def test_floor_ceiling_lower_bound(self):
        cur = 0.5
        for _ in range(100):
            cur = update(cur, signal=0.0, days_since_last=0, user_count=100)
        assert 0.05 <= cur <= 0.95
        # 公式本身会收敛到 0.0；clamp 把它抬到 floor=0.05
        assert cur == 0.05


# ─────────── batch_update 多条信号 ───────────


class TestBatchUpdate:
    def test_multiple_signals_apply_sequentially(self):
        now = datetime(2026, 8, 2, 12, 0, 0)
        signals = [
            (1.0, now - timedelta(days=2)),
            (0.0, now - timedelta(days=1)),
        ]
        new = batch_update(0.5, signals, now, user_count=100)
        # 顺序更新两条，最终值应回到 0.5 附近
        assert 0.45 < new < 0.55

    def test_empty_signals_returns_old(self):
        assert batch_update(0.5, [], datetime.utcnow(), user_count=100) == 0.5

    def test_out_of_order_input_is_sorted(self):
        now = datetime(2026, 8, 2, 12, 0, 0)
        # 输入乱序
        signals = [
            (0.0, now - timedelta(days=1)),
            (1.0, now - timedelta(days=5)),
            (1.0, now - timedelta(days=3)),
        ]
        new = batch_update(0.5, signals, now, user_count=100)
        reordered = [
            (1.0, now - timedelta(days=5)),
            (0.0, now - timedelta(days=1)),
            (1.0, now - timedelta(days=3)),
        ]
        new2 = batch_update(0.5, reordered, now, user_count=100)
        assert math.isclose(new, new2, abs_tol=1e-9)

    def test_lt10_users_short_circuits(self):
        now = datetime.utcnow()
        signals = [(1.0, now), (1.0, now), (1.0, now)]
        assert batch_update(0.5, signals, now, user_count=5) == 0.5

    def test_clamped_in_batch(self):
        now = datetime.utcnow()
        signals = [(1.0, now - timedelta(seconds=i)) for i in range(50)]
        new = batch_update(0.5, signals, now, user_count=100)
        assert 0.05 <= new <= 0.95

    def test_negative_days_clamped(self):
        """clock skew：occurred > now 不应 crash，应 clamp 到 0。"""
        now = datetime(2026, 8, 2, 12, 0, 0)
        signals = [(1.0, now + timedelta(minutes=5))]
        new = batch_update(0.5, signals, now, user_count=100)
        assert new > 0.5
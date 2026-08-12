"""阶段五·2D 飞轮：Prometheus 指标。

通过 prometheus_client 单例暴露给 /metrics 端点（main.py 挂载）。

4 个核心指标：
- kg_flywheel_runs_total          Counter    飞轮周跑累计次数
- kg_signals_total                Counter    信号处理总数（按 kind 分桶）
- kg_disputes_exported_total      Counter    导到 review queue 的关系数
- kg_concepts_confidence_avg      Gauge      平均 concept confidence（实时刷新）

依赖缺失（prometheus_client 未装）时降级为 no-op stub —
dev / 测试环境不必强制装 metrics 包也能跑飞轮。
"""
from __future__ import annotations


class _NoopMetric:
    """任何方法都不做事的占位指标。"""

    def inc(self, amount: float = 1.0) -> None:  # noqa: ARG002
        return None

    def set(self, value: float) -> None:  # noqa: ARG002
        return None

    def labels(self, **labels) -> "_NoopMetric":  # noqa: ARG002
        return self


class _NoopMetricFamily:
    """模拟 prometheus_client 的 Counter / Gauge 双层调用：family.labels(...).inc()"""

    def __init__(self, *args, **kwargs):
        pass

    def labels(self, **labels) -> _NoopMetric:
        return _NoopMetric()

    def inc(self, amount: float = 1.0) -> None:
        return None

    def set(self, value: float) -> None:
        return None


try:
    from prometheus_client import Counter, Gauge

    flywheel_runs_total = Counter(
        "kg_flywheel_runs_total", "Flywheel weekly run counter",
    )
    signals_total = Counter(
        "kg_signals_total", "Signals processed by source", ["kind"],
    )
    disputes_exported_total = Counter(
        "kg_disputes_exported_total", "Disputed relations exported for human review",
    )
    concepts_confidence_avg = Gauge(
        "kg_concepts_confidence_avg", "Average concept confidence",
    )
except Exception:
    # prometheus_client 未装 — 用 stub 兜底，不影响 flywheel 主流程
    flywheel_runs_total = _NoopMetricFamily()
    signals_total = _NoopMetricFamily()
    disputes_exported_total = _NoopMetricFamily()
    concepts_confidence_avg = _NoopMetricFamily()
"""token_budget 单测：priority 排序 + 截断 + mastery 加权。

不依赖 DB / Neo4j，纯函数测试。
"""
import pytest

from kg.graph_rag import RetrievedNode
from kg.token_budget import (
    compute_priority,
    prioritize_and_truncate,
)


def _node(
    id_: str,
    name: str,
    type_: str = "Method",
    score: float = 0.9,
    conf: float = 0.5,
    pg_kp_id: int | None = None,
    mastery: dict | None = None,
    subject: str = "math-calc",
) -> RetrievedNode:
    return RetrievedNode(
        id=id_, name=name, type=type_, subject=subject,
        pg_kp_id=pg_kp_id, vector_score=score, confidence=conf,
        mastery=mastery,
    )


def test_priority_weak_mastery_up():
    """薄弱 mastery 提升 priority > 未知 > 已掌握（设计意图）。"""
    # 用低 vector_score + 低 conf 让 mastery_relevance 真正影响 priority
    weak = _node("a", "A", score=0.1, conf=0.1, mastery={"status": "weak"})
    no_mastery = _node("c", "C", score=0.1, conf=0.1)
    mastered = _node("b", "B", score=0.1, conf=0.1, mastery={"status": "mastered"})
    assert (
        compute_priority(weak)
        > compute_priority(no_mastery)
        > compute_priority(mastered)
    )


def test_priority_mastery_full_breakdown():
    """验证各 mastery 状态在 vector_score=0 时差异最大。"""
    # mastery_relevance: weak=1.0, in_progress=0.5, no_mastery=0.5, mastered=0.3
    # vector_score=0, conf=0 → 纯 mastery 差
    weak = _node("a", "A", score=0.0, conf=0.0, mastery={"status": "weak"})
    in_progress = _node("i", "I", score=0.0, conf=0.0, mastery={"status": "in_progress"})
    no_mastery = _node("c", "C", score=0.0, conf=0.0)
    mastered = _node("b", "B", score=0.0, conf=0.0, mastery={"status": "mastered"})

    p_weak = compute_priority(weak)
    p_ip = compute_priority(in_progress)
    p_none = compute_priority(no_mastery)
    p_mas = compute_priority(mastered)

    assert p_weak > p_ip  # 1.0 > 0.5
    assert abs(p_ip - p_none) < 1e-9  # in_progress 和 no_mastery 都是 0.5
    assert p_none > p_mas  # 0.5 > 0.3


def test_priority_formula_breakdown():
    """验证公式：score*0.6 + conf*0.2 + mastery_rel*0.2。"""
    node = _node("x", "X", score=1.0, conf=0.0, mastery={"status": "weak"})
    # score=1.0 → 0.6; conf=0.0 → 0.0; weak → 1.0 → 0.2 → 总 0.8
    assert abs(compute_priority(node) - 0.8) < 1e-9


def test_priority_in_progress_is_neutral():
    """in_progress mastery_relevance = 0.5（中性）。"""
    in_progress = _node("i", "I", score=0.5, conf=0.5, mastery={"status": "in_progress"})
    # 0.5*0.6 + 0.5*0.2 + 0.5*0.2 = 0.3 + 0.1 + 0.1 = 0.5
    assert abs(compute_priority(in_progress) - 0.5) < 1e-9


def test_truncate_respects_budget():
    """超 budget 时跳过，不能超出 max_tokens。"""
    seeds = [
        _node(f"s{i}", f"Name{i}", score=1.0 - i * 0.01)
        for i in range(20)
    ]
    expanded = [
        _node(f"e{i}", f"ExpName{i}", conf=0.5)
        for i in range(50)
    ]
    out = prioritize_and_truncate(seeds, expanded, {}, max_tokens=50)
    assert out.used_tokens <= 50
    # seeds 优先放
    assert all(n.id.startswith("s") for n in out.seeds)


def test_truncate_seeds_first():
    """seeds 全部装得下时，expanded 应被截断或部分保留。"""
    seeds = [_node("s1", "Alpha"), _node("s2", "Beta")]
    expanded = [_node(f"e{i}", f"Gamma{i}") for i in range(100)]
    out = prioritize_and_truncate(seeds, expanded, {}, max_tokens=30)
    # seeds 全部保留（cost < 30），expanded 应该几乎都被截断
    assert len(out.seeds) == 2
    assert out.used_tokens <= 30


def test_mastery_injected_from_user_state():
    """传 user_state 后节点 mastery 字段会被注入。"""
    seeds = [_node("s1", "A", pg_kp_id=42)]
    user_state = {42: {"score": 0.3, "status": "weak", "correct_rate": 0.3}}
    out = prioritize_and_truncate(seeds, [], user_state, max_tokens=100)
    assert out.seeds[0].mastery is not None
    assert out.seeds[0].mastery["status"] == "weak"


def test_empty_inputs():
    """空输入 → 空输出。"""
    out = prioritize_and_truncate([], [], {}, max_tokens=3000)
    assert out.seeds == []
    assert out.expanded == []
    assert out.used_tokens == 0
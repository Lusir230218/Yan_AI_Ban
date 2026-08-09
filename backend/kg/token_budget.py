"""Context token 预算：按 priority 排序 + 截断到 max_tokens。

priority = vector_sim * 0.6 + confidence * 0.2 + mastery_relevance * 0.2
- vector_sim: 0..1，向量召回的相似度（expanded 节点记 0）
- confidence: 0..1，节点或关系的置信度
- mastery_relevance: 0..1
  - 用户薄弱（status="weak"）→ 1.0（最该复习）
  - 用户已掌握（status="mastered"）→ 0.3
  - 未知 → 0.5（中性）

截断策略：先放 seeds（按 priority 降序），再放 expanded；超 budget 跳过。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kg.graph_rag import RetrievedNode


# 每节点的固定开销（prompt 模板里的 "- id=... | ... (相似度 X.XX, conf Y.YY) [...]" 框架）
_OVERHEAD_TOKENS = 5


def _node_text_token_estimate(node: "RetrievedNode") -> int:
    """粗估一个节点在 prompt 里占的 token 数（按字符/2 估算）。"""
    name_t = len(node.name) // 2
    type_t = len(node.type) // 2
    return max(name_t + type_t, 5)


def _mastery_relevance(node: "RetrievedNode") -> float:
    """学生薄弱点优先曝光（更值得在 context 里强调）。"""
    if not node.mastery:
        return 0.5
    status = node.mastery.get("status")
    if status == "weak":
        return 1.0
    if status == "mastered":
        return 0.3
    return 0.5


def compute_priority(node: "RetrievedNode") -> float:
    return (
        node.vector_score * 0.6
        + node.confidence * 0.2
        + _mastery_relevance(node) * 0.2
    )


@dataclass
class PrioritizedContext:
    """prioritize_and_truncate 返回值。"""
    seeds: list
    expanded: list
    used_tokens: int
    max_tokens: int


def prioritize_and_truncate(
    seeds: list,
    expanded: list,
    user_state: dict[int, dict],
    max_tokens: int,
) -> PrioritizedContext:
    """按 priority 排序 + token 截断。

    Args:
        seeds: 向量召回的节点列表（RetrievedNode 列表）
        expanded: 1 跳图扩展的节点列表
        user_state: pg_kp_id → mastery dict（来自 _fetch_user_state）
        max_tokens: 总 token 上限（默认 3000）
    """
    # 先把 mastery 注入每个节点（如果 user_state 有的话）
    for n in seeds + expanded:
        if n.pg_kp_id and n.pg_kp_id in user_state:
            n.mastery = user_state[n.pg_kp_id]

    seeds_sorted = sorted(seeds, key=compute_priority, reverse=True)
    expanded_sorted = sorted(expanded, key=compute_priority, reverse=True)

    used = 0
    keep_seeds: list = []
    keep_expanded: list = []

    for n in seeds_sorted:
        cost = _node_text_token_estimate(n) + _OVERHEAD_TOKENS
        if used + cost > max_tokens:
            continue
        keep_seeds.append(n)
        used += cost

    for n in expanded_sorted:
        cost = _node_text_token_estimate(n) + _OVERHEAD_TOKENS
        if used + cost > max_tokens:
            continue
        keep_expanded.append(n)
        used += cost

    return PrioritizedContext(
        seeds=keep_seeds,
        expanded=keep_expanded,
        used_tokens=used,
        max_tokens=max_tokens,
    )
"""GraphRAG prompt 构造。

强制 LLM 输出 JSON: {answer, cited: [{id, name, type}]}
- answer: 200-500 字回答（中文）
- cited: 引用的概念 id/name/type 列表；id 必须严格出现在上下文列表中

设计要点：
1. 上下文分两块："核心概念"（seeds，向量召回）+ "关联知识"（expanded，1 跳扩展）
2. 学生掌握度作为 emoji 标签（🔴薄弱/🟡学习中/🟢已掌握）暴露给 LLM
3. 输出 JSON 强制结构化，避免字符串解析脆弱
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kg.token_budget import PrioritizedContext
    from kg.graph_rag import RetrievedNode


_MASTERY_TAGS = {
    "weak": "🔴薄弱",
    "in_progress": "🟡学习中",
    "mastered": "🟢已掌握",
}


def _format_mastery(node: "RetrievedNode") -> str:
    if not node.mastery:
        return ""
    tag = _MASTERY_TAGS.get(node.mastery.get("status", ""), "")
    return f" [{tag}]" if tag else ""


def _seed_lines(nodes: list) -> list[str]:
    lines: list[str] = []
    for n in nodes:
        state = _format_mastery(n)
        lines.append(
            f"- id={n.id} | {n.type}: {n.name} "
            f"(相似度 {n.vector_score:.2f}, conf {n.confidence:.2f}){state}"
        )
    return lines


def _expanded_lines(nodes: list) -> list[str]:
    lines: list[str] = []
    for n in nodes:
        state = _format_mastery(n)
        lines.append(
            f"- id={n.id} | {n.type}: {n.name} (conf {n.confidence:.2f}){state}"
        )
    return lines


def build_rag_prompt(query: str, ctx: "PrioritizedContext") -> str:
    """拼出 GraphRAG 的 user prompt。

    ctx 是 token_budget.prioritize_and_truncate 返回的对象：
    - ctx.seeds: 核心概念（向量召回到的）
    - ctx.expanded: 关联知识（图谱扩展）
    """
    seed_text = "\n".join(_seed_lines(ctx.seeds)) or "（无）"
    expanded_text = "\n".join(_expanded_lines(ctx.expanded)) or "（无）"

    return f"""你是考研辅导 AI。基于以下知识图谱上下文与学生状态回答问题。

## 学生问题
{query}

## 核心概念（向量召回到的）
{seed_text}

## 关联知识（图谱扩展：前置 + 错因 + 对比）
{expanded_text}

## 回答要求
1. 基于图谱中的概念推理，不要瞎编
2. 涉及学生薄弱点时，明确指出
3. 给出可操作建议
4. 在 cited 字段输出引用（格式见下）

## 输出格式（严格 JSON）
{{
  "answer": "你的回答（200-500 字）",
  "cited": [
    {{"id": "kp:MA-INT-001", "name": "不定积分", "type": "KP"}},
    {{"id": "method:u-sub", "name": "换元积分法", "type": "Method"}}
  ]
}}

## 重要
- cited 的 id **必须**严格出现在上面"核心概念"或"关联知识"列表中
- 至少引用 1 条；如果没引用对得上，就返回空 cited
"""
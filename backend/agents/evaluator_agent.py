"""Evaluator Agent — 学习评估与分数预测

节点：gather_records → gather_mastery → llm_predict → save_report

用法：
  from agents.evaluator_agent import run_evaluation
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.study import StudyRecord, KnowledgePoint
from models.assessment import EvaluationReport

logger = logging.getLogger("evaluator_agent")
logger.setLevel(logging.DEBUG)


class EvaluatorState(TypedDict):
    user_id: int
    diagnosis: dict | None

    study_records: list[dict]
    knowledge_mastery: dict              # {kp_name: mastery_score}

    predicted_scores: dict               # {math, english, politics, total}
    weak_points: list[dict]              # [{kp_name, mastery_pct, priority}]
    suggestions: list[str]

    report_id: int | None

    _db_session: AsyncSession | None

    error: str | None


SUBJECT_MAX_SCORES = {"数学": 150, "英语": 100, "政治": 100}


async def gather_records(state: EvaluatorState) -> dict:
    """从 PG 查询用户学习记录"""
    from core.database import async_session

    user_id = state.get("user_id")

    async with async_session() as session:
        result = await session.execute(
            select(StudyRecord).where(StudyRecord.user_id == user_id).limit(200)
        )
        records = result.scalars().all()

    records_data = [
        {
            "id": r.id,
            "subject": r.subject,
            "knowledge_point_id": r.knowledge_point_id,
            "is_correct": r.is_correct,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]

    return {"study_records": records_data}


async def gather_mastery(state: EvaluatorState) -> dict:
    """从 Neo4j 查询用户知识点掌握状态（降级为 PG fallback）"""
    try:
        from kg.neo4j_client import get_kg_driver
        driver = await get_kg_driver()
        if driver:
            user_id = state.get("user_id")
            query = """
                MATCH (u:User {id: $user_id})-[r:MASTERED|WEAK]->(kp:KnowledgePoint)
                RETURN kp.name AS name, type(r) AS status
            """
            records, _, _ = await driver.execute_query(query, {"user_id": user_id})
            mastery = {}
            for rec in records:
                mastery[rec["name"]] = 1.0 if rec["status"] == "MASTERED" else 0.3
            if mastery:
                return {"knowledge_mastery": mastery}
    except Exception as e:
        logger.warning(f"Neo4j query failed, using PG fallback: {e}")

    # PG fallback: 根据 StudyRecord 聚合正确率
    records = state.get("study_records", [])
    from core.database import async_session

    kp_stats: dict[int, list[bool]] = {}
    for r in records:
        kp_id = r.get("knowledge_point_id")
        is_correct = r.get("is_correct")
        if kp_id and is_correct is not None:
            kp_stats.setdefault(kp_id, []).append(is_correct)

    mastery = {}
    if kp_stats:
        async with async_session() as session:
            result = await session.execute(
                select(KnowledgePoint).where(KnowledgePoint.id.in_(list(kp_stats.keys())))
            )
            kps = {kp.id: kp.name for kp in result.scalars().all()}

        for kp_id, results in kp_stats.items():
            name = kps.get(kp_id, f"KP-{kp_id}")
            mastery[name] = round(sum(results) / len(results), 2)

    return {"knowledge_mastery": mastery}


async def llm_predict(state: EvaluatorState) -> dict:
    """规则预测各科分数 + 薄弱点（不调 LLM，保证仪表盘快速响应）"""
    records = state.get("study_records", [])
    mastery = state.get("knowledge_mastery", {})

    if not records:
        return {
            "predicted_scores": {},
            "weak_points": [],
            "suggestions": ["先完成一些练习题后再来评估吧！"],
        }

    # 按科目计算加权正确率 → 预测分数
    subject_correct: dict[str, list[bool]] = {}
    for r in records:
        subj = r.get("subject", "")
        is_correct = r.get("is_correct")
        if subj and is_correct is not None:
            subject_correct.setdefault(subj, []).append(is_correct)

    scores = {}
    for subj, results in subject_correct.items():
        rate = sum(results) / len(results) if results else 0
        scores[subj] = round(rate * SUBJECT_MAX_SCORES.get(subj, 100))
    scores["total"] = sum(scores.values())

    # 薄弱点：掌握率最低的 5 个
    weak_sorted = sorted(mastery.items(), key=lambda x: x[1])[:5]
    weak_points = [
        {"name": name, "mastery_pct": int(pct * 100), "priority": i + 1}
        for i, (name, pct) in enumerate(weak_sorted) if pct < 0.6
    ]

    # 建议
    suggestions = []
    if weak_points:
        top_weak = weak_points[0]["name"]
        suggestions.append(f"建议加强「{top_weak}」的专项练习")

    return {
        "predicted_scores": scores,
        "weak_points": weak_points,
        "suggestions": suggestions,
    }


async def save_report(state: EvaluatorState) -> dict:
    """写入 evaluation_reports 表"""
    db = state.get("_db_session")
    if not db:
        return {}

    user_id = state.get("user_id")
    scores = state.get("predicted_scores", {})
    weak = state.get("weak_points", [])
    suggestions = state.get("suggestions", [])

    report = EvaluationReport(
        user_id=user_id,
        period="auto",
        predicted_score=scores.get("total", 0),
        weak_points=json.dumps(weak, ensure_ascii=False),
        suggestions=json.dumps(suggestions, ensure_ascii=False),
    )
    db.add(report)
    await db.flush()

    return {"report_id": report.id}


def build_evaluator_graph() -> StateGraph:
    workflow = StateGraph(EvaluatorState)

    workflow.add_node("gather_records", gather_records)
    workflow.add_node("gather_mastery", gather_mastery)
    workflow.add_node("llm_predict", llm_predict)
    workflow.add_node("save_report", save_report)

    workflow.set_entry_point("gather_records")
    workflow.add_edge("gather_records", "gather_mastery")
    workflow.add_edge("gather_mastery", "llm_predict")
    workflow.add_edge("llm_predict", "save_report")
    workflow.add_edge("save_report", END)

    return workflow


evaluator_app = build_evaluator_graph().compile()


class EvaluatorInput(TypedDict, total=False):
    user_id: int
    diagnosis: dict | None


class EvaluatorOutput(TypedDict):
    predicted_scores: dict
    weak_points: list[dict]
    suggestions: list[str]
    report_id: int | None
    error: str | None


async def run_evaluation(
    inputs: EvaluatorInput,
    db: AsyncSession | None = None,
) -> EvaluatorOutput:
    """外部入口 — 执行完整评估"""
    logger.info(f"run_evaluation — user_id={inputs.get('user_id')}")

    initial: EvaluatorState = {
        "user_id": inputs.get("user_id"),
        "diagnosis": inputs.get("diagnosis"),
        "study_records": [],
        "knowledge_mastery": {},
        "predicted_scores": {},
        "weak_points": [],
        "suggestions": [],
        "report_id": None,
        "_db_session": db,
        "error": None,
    }

    try:
        result = await evaluator_app.ainvoke(initial)
    except Exception as e:
        logger.error(f"evaluation failed: {e}")
        return EvaluatorOutput(predicted_scores={}, weak_points=[], suggestions=[], report_id=None, error=str(e))

    if result.get("error"):
        return EvaluatorOutput(predicted_scores={}, weak_points=[], suggestions=[], report_id=None, error=result["error"])

    if db:
        await db.commit()

    return EvaluatorOutput(
        predicted_scores=result.get("predicted_scores", {}),
        weak_points=result.get("weak_points", []),
        suggestions=result.get("suggestions", []),
        report_id=result.get("report_id"),
        error=None,
    )

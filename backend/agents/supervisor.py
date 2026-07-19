"""Supervisor 编排器 — 多 Agent 调度中心

节点：intent_router → call_tutor / call_evaluator / call_encourager / call_planner → aggregate
支持单意图路由和多意图并行分发。

用法：
  from agents.supervisor import run_supervisor
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from llm.gateway import llm_chat

logger = logging.getLogger("supervisor")
logger.setLevel(logging.DEBUG)


class SupervisorState(TypedDict):
    user_id: int
    user_input: str
    intent: str                       # tutor / evaluate / encourage / plan / multi
    diagnosis: dict | None

    # 子 Agent 输出
    tutor_response: dict | None
    evaluator_response: dict | None
    encourager_response: dict | None
    planner_response: dict | None

    # 聚合结果
    final_response: dict | None

    # 内部
    _db_session: AsyncSession | None

    error: str | None


INTENT_PROMPT = """你是考研辅导助手的意图识别模块。分析用户输入，判断意图类型。

意图类型：
- tutor: 用户想解答/理解某道题目，关键词：这题怎么做、帮我看看、不会做、解题、讲解、分析一下这道题
- evaluate: 用户想评估自己的水平/预测分数，关键词：我能考多少分、水平如何、评估、预测、摸底、薄弱
- encourage: 用户表现出挫败、焦虑、需要鼓励，关键词：好难、学不进去、焦虑、坚持不下去了、好累、不想学
- plan: 用户想制定/调整学习计划，关键词：计划、安排、规划、时间不够、怎么复习、进度

规则：
- 如果同时包含多个意图（如"看看这题顺便评估下我的水平"），返回 "multi"
- 如果无法判断，返回 "tutor"

只返回一个词：tutor / evaluate / encourage / plan / multi。不要其他内容。"""


async def intent_router(state: SupervisorState) -> dict:
    """LLM 分析用户输入，判断意图类型"""
    user_input = state.get("user_input", "")

    resp = await llm_chat(
        messages=[
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": user_input},
        ],
        temperature=0.1,
        max_tokens=20,
    )

    intent = resp.text.strip().lower()
    valid = {"tutor", "evaluate", "encourage", "plan", "multi"}
    if intent not in valid:
        intent = "tutor"

    logger.info(f"intent_router: user_input='{user_input[:50]}...' → intent={intent}")
    return {"intent": intent}


async def call_tutor(state: SupervisorState) -> dict:
    """调用 Tutor Agent（轻量内联版本 — 文本回复引导）"""
    user_input = state.get("user_input", "")

    prompt = (
        f"学生提问：{user_input}\n\n"
        "你是考研辅导专家。不要直接给答案，用苏格拉底式教学法引导思考。"
        "先问学生：这道题在问什么？已知条件有哪些？涉及哪个知识点？"
        "控制在150字以内。"
    )

    resp = await llm_chat(
        messages=[
            {"role": "system", "content": "你是考研辅导专家，用引导式教学。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=512,
    )

    return {"tutor_response": {"message": resp.text.strip(), "type": "tutor_guide"}}


async def call_evaluator(state: SupervisorState) -> dict:
    """调用 Evaluator Agent（轻量内联版本）"""
    from core.database import async_session
    from sqlalchemy import select
    from models.study import StudyRecord

    user_id = state.get("user_id")
    diagnosis = state.get("diagnosis") or {}

    async with async_session() as session:
        result = await session.execute(
            select(StudyRecord).where(StudyRecord.user_id == user_id).limit(100)
        )
        records = result.scalars().all()

    if not records:
        return {"evaluator_response": {"message": "还没有学习记录，先做几道题再评估吧！", "type": "no_data"}}

    subject_correct: dict[str, list[bool]] = {}
    for r in records:
        if r.is_correct is not None:
            subject_correct.setdefault(r.subject, []).append(r.is_correct)

    predictions = {}
    max_scores = {"数学": 150, "英语": 100, "政治": 100}
    for subj, results in subject_correct.items():
        rate = sum(results) / len(results) if results else 0
        predictions[subj] = round(rate * max_scores.get(subj, 100))

    prompt = (
        f"用户学习数据：\n"
        f"{json.dumps({s: {'正确率': f'{sum(r)/len(r)*100:.0f}%', '预测分': predictions.get(s)} for s, r in subject_correct.items()}, ensure_ascii=False)}\n"
        f"用户目标：{diagnosis.get('target_school', '未知')} {diagnosis.get('target_major', '')}\n\n"
        "请简短评估：1.各科水平 2.最薄弱环节建议 3.鼓励一句话。控制在150字以内。"
    )

    resp = await llm_chat(
        messages=[
            {"role": "system", "content": "你是考研评估专家，简洁评估学习水平。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=512,
    )

    return {"evaluator_response": {
        "message": resp.text.strip(),
        "predictions": predictions,
        "type": "evaluation",
    }}


async def call_encourager(state: SupervisorState) -> dict:
    """调用 Encourager Agent（轻量内联版本）"""
    user_input = state.get("user_input", "")
    diagnosis = state.get("diagnosis") or {}
    nickname = diagnosis.get("nickname", "同学")

    prompt = (
        f"学生{nickname}说：{user_input}\n\n"
        "学生表现出消极情绪，需要鼓励。请简短回复（100字以内）："
        "1.共情（理解这种感受是正常的）"
        "2.提醒已经取得的进步"
        "3.给一个小而具体的下一步行动建议"
        "语气要温暖真诚。"
    )

    resp = await llm_chat(
        messages=[
            {"role": "system", "content": "你是考研鼓励师，温暖、真诚、有共情力。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=512,
    )

    return {"encourager_response": {"message": resp.text.strip(), "type": "encourage"}}


async def call_planner(state: SupervisorState) -> dict:
    """调用 Planner Agent"""
    from agents.planner_agent import run_plan

    diagnosis = state.get("diagnosis") or {}
    result = await run_plan({
        "user_id": state.get("user_id"),
        "diagnosis": diagnosis,
        "kg_context": [],
    })

    return {"planner_response": {"plan_text": result.get("plan_text"), "phases": result.get("phases"), "type": "plan"}}


async def aggregate(state: SupervisorState) -> dict:
    """合并所有被调用 Agent 的输出"""
    parts = []

    if state.get("tutor_response"):
        parts.append(state["tutor_response"]["message"])
    if state.get("evaluator_response"):
        parts.append(state["evaluator_response"]["message"])
    if state.get("encourager_response"):
        parts.append(state["encourager_response"]["message"])
    if state.get("planner_response"):
        parts.append(state["planner_response"].get("plan_text", ""))

    final = {
        "intent": state.get("intent"),
        "message": "  ".join(parts),
        "details": {
            "tutor": state.get("tutor_response"),
            "evaluator": state.get("evaluator_response"),
            "encourager": state.get("encourager_response"),
            "planner": state.get("planner_response"),
        },
    }

    return {"final_response": final}


def _route_by_intent(state: SupervisorState) -> list[str]:
    """根据意图决定调用哪些 Agent"""
    intent = state.get("intent", "tutor")
    routes = {
        "tutor": ["call_tutor"],
        "evaluate": ["call_evaluator"],
        "encourage": ["call_encourager"],
        "plan": ["call_planner"],
        "multi": ["call_tutor", "call_evaluator", "call_encourager", "call_planner"],
    }
    return routes.get(intent, ["call_tutor"])


def build_supervisor_graph() -> StateGraph:
    workflow = StateGraph(SupervisorState)

    workflow.add_node("intent_router", intent_router)
    workflow.add_node("call_tutor", call_tutor)
    workflow.add_node("call_evaluator", call_evaluator)
    workflow.add_node("call_encourager", call_encourager)
    workflow.add_node("call_planner", call_planner)
    workflow.add_node("aggregate", aggregate)

    workflow.set_entry_point("intent_router")

    for agent_node in ["call_tutor", "call_evaluator", "call_encourager", "call_planner"]:
        workflow.add_edge(agent_node, "aggregate")

    workflow.add_edge("aggregate", END)

    return workflow


supervisor_app = build_supervisor_graph().compile()


class SupervisorInput(TypedDict, total=False):
    user_id: int
    user_input: str
    diagnosis: dict | None


class SupervisorOutput(TypedDict):
    intent: str
    message: str
    details: dict
    error: str | None


async def run_supervisor(
    inputs: SupervisorInput,
    db: AsyncSession,
) -> SupervisorOutput:
    """统一对话入口"""
    user_input = inputs.get("user_input", "")
    logger.info(f"run_supervisor — user_id={inputs.get('user_id')}, input='{user_input[:50]}...'")

    initial: SupervisorState = {
        "user_id": inputs.get("user_id"),
        "user_input": user_input,
        "intent": "tutor",
        "diagnosis": inputs.get("diagnosis"),
        "tutor_response": None,
        "evaluator_response": None,
        "encourager_response": None,
        "planner_response": None,
        "final_response": None,
        "_db_session": db,
        "error": None,
    }

    try:
        route_result = await intent_router(initial)
        intent = route_result.get("intent", "tutor")
        logger.info(f"Intent: {intent}")

        routes = _route_by_intent({"intent": intent, **initial})

        async def call_agent(name: str) -> tuple[str, dict]:
            if name == "call_tutor":
                r = await call_tutor(initial)
                return ("tutor_response", r)
            elif name == "call_evaluator":
                r = await call_evaluator(initial)
                return ("evaluator_response", r)
            elif name == "call_encourager":
                r = await call_encourager(initial)
                return ("encourager_response", r)
            elif name == "call_planner":
                r = await call_planner(initial)
                return ("planner_response", r)
            return (name, {})

        tasks = [call_agent(r) for r in routes]
        results = await asyncio.gather(*tasks)

        merged = dict(initial)
        for key, val in results:
            merged[key] = val
        merged["intent"] = intent

        agg_result = await aggregate(merged)
        final = agg_result.get("final_response", {})

    except Exception as e:
        logger.error(f"run_supervisor failed: {e}")
        return SupervisorOutput(intent="tutor", message="", details={}, error=str(e))

    return SupervisorOutput(
        intent=final.get("intent", intent),
        message=final.get("message", ""),
        details=final.get("details", {}),
        error=None,
    )

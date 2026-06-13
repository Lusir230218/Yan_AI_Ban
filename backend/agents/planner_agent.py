"""Planner Agent — 学习规划师

根据用户的考研诊断信息 + 知识图谱，生成个性化学习计划。
入口函数 run() 被 LangGraph 节点调用，也可直接作为 API 调用。
"""

from __future__ import annotations

from typing import TypedDict, Any
from datetime import date, timedelta

from langgraph.graph import StateGraph, END

from config import settings
from llm.gateway import llm_chat


# ---------- State ----------

class PlannerState(TypedDict):
    user_id: int | None
    diagnosis: dict[str, Any]       # 用户画像
    kg_context: list[dict]          # 知识图谱相关数据
    plan_text: str | None           # LLM 生成的计划文本
    structured_plan: list[dict] | None  # 结构化的计划列表


# ---------- Input / Output ----------

class PlannerInput(TypedDict, total=False):
    user_id: int
    diagnosis: dict[str, Any]
    kg_context: list[dict]


class PlannerOutput(TypedDict):
    plan_text: str
    phases: list[dict]


# ---------- Nodes ----------

async def gather_kg_context(state: PlannerState) -> dict:
    """从 Neo4j 知识图谱获取考研大纲结构"""
    from kg.neo4j_client import get_kg_driver

    driver = await get_kg_driver()
    context = []
    async with driver.session() as session:
        result = await session.run(
            "MATCH (s:Subject) ORDER BY s.name RETURN s.name AS subject"
        )
        async for row in result:
            subject = row["subject"]
            chapters = []
            ch_result = await session.run(
                "MATCH (s:Subject {name: $name})-[:HAS_CHAPTER]->(c:Chapter) "
                "ORDER BY c.name RETURN c.name AS chapter",
                name=subject,
            )
            async for ch_row in ch_result:
                chapters.append(ch_row["chapter"])
            context.append({"subject": subject, "chapters": chapters})
    return {"kg_context": context}


async def generate_plan(state: PlannerState) -> dict:
    """调用 LLM 生成个性化学习计划"""
    diag = state.get("diagnosis", {})
    kg = state.get("kg_context", [])
    now = date.today()

    # 将知识图谱结构转为文本
    kg_text = "\n".join(
        f"{s['subject']}：{'、'.join(s['chapters'])}" for s in kg
    ) if kg else "暂无科目数据"

    prompt = f"""你是考研学习规划师。根据以下用户画像和考纲结构，生成一份学习计划。

用户画像：
- 目标院校：{diag.get('target_school', '未知')}
- 目标专业：{diag.get('target_major', '未知')}
- 当前水平（0-100）：{diag.get('current_level', '未知')}
- 每天可用学习时长（小时）：{diag.get('available_hours', '未知')}
- 学习风格偏好：{diag.get('learning_style', '未知')}

考纲科目结构：
{kg_text}

要求：
1. 将从现在（{now.isoformat()}）到考研前分为 3 个阶段（基础/强化/冲刺）
2. 每阶段给出：阶段名称、起止日期、重点科目、每日任务概览
3. 根据当前水平调整各阶段时长
4. 用中文返回，简洁清晰

输出格式为 JSON 数组：
[
  {{
    "phase": "基础阶段",
    "start_date": "2026-06-10",
    "end_date": "2026-08-31",
    "focus": "数学+英语",
    "daily_tasks": "每天3h数学+2h英语+1h政治",
    "status": "active"
  }},
  ...
]"""

    try:
        resp = await llm_chat(
            messages=[
                {"role": "system", "content": "你是专业的考研学习规划师，擅长根据用户画像制定个性化学习计划。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2048,
        )
        plan_text = resp.text
    except Exception as e:
        plan_text = f"LLM 调用失败，使用默认计划。({e})"

    return {"plan_text": plan_text}


def parse_plan(state: PlannerState) -> dict:
    """解析 LLM 返回的 JSON 计划，兜底生成默认计划"""
    import json
    text = state.get("plan_text", "")
    try:
        # 尝试提取 JSON 数组
        start = text.index("[")
        end = text.rindex("]") + 1
        phases = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        # 兜底：用默认计划
        now = date.today()
        phases = [
            {"phase": "基础阶段", "start_date": now.isoformat(), "end_date": (now + timedelta(days=90)).isoformat(),
             "focus": "数学+英语", "daily_tasks": "每天3h数学+2h英语+1h政治", "status": "active"},
            {"phase": "强化阶段", "start_date": (now + timedelta(days=91)).isoformat(), "end_date": (now + timedelta(days=180)).isoformat(),
             "focus": "全科+真题", "daily_tasks": "每天4h数学+2h英语+2h政治+专业1h", "status": "pending"},
            {"phase": "冲刺阶段", "start_date": (now + timedelta(days=181)).isoformat(), "end_date": (now + timedelta(days=270)).isoformat(),
             "focus": "模考+查漏补缺", "daily_tasks": "每天5h全科模考+错题复盘", "status": "pending"},
        ]
    return {"structured_plan": phases}


# ---------- Workflow ----------

def build_planner_graph() -> StateGraph:
    workflow = StateGraph(PlannerState)

    workflow.add_node("gather_kg", gather_kg_context)
    workflow.add_node("generate", generate_plan)
    workflow.add_node("parse", parse_plan)

    workflow.set_entry_point("gather_kg")
    workflow.add_edge("gather_kg", "generate")
    workflow.add_edge("generate", "parse")
    workflow.add_edge("parse", END)

    return workflow


# 编译为可执行应用
planner_app = build_planner_graph().compile()


# ---------- Public API ----------

async def run_plan(inputs: PlannerInput) -> PlannerOutput:
    """外部统一入口：接收诊断信息 → 返回结构化计划"""
    initial: PlannerState = {
        "user_id": inputs.get("user_id"),
        "diagnosis": inputs.get("diagnosis", {}),
        "kg_context": inputs.get("kg_context", []),
        "plan_text": None,
        "structured_plan": None,
    }
    result = await planner_app.ainvoke(initial)
    return PlannerOutput(
        plan_text=result.get("plan_text", ""),
        phases=result.get("structured_plan", []),
    )

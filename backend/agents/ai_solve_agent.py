"""AI 解答/批改 Agent — LangGraph 工作流

流程：
  image → [多模态模式 ? vision_extract : ocr_extract] → llm_structurize
  → route_decision → solve_agent / grade_agent → knowledge_matcher → save_result → format_response

用法：
  from agents.ai_solve_agent import run_ai_solve
  result = await run_ai_solve(inputs, db, user_id)
"""

from __future__ import annotations

import base64
import json
import logging
import re
import traceback
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from llm.gateway import llm_chat, llm_vision_chat
from models.study import KnowledgePoint, Question, StudyRecord

logger = logging.getLogger("ai_solve_agent")
logger.setLevel(logging.DEBUG)


# ── State ──


class AiSolveState(TypedDict):
    # 输入
    image_data: bytes | None       # 原始图片 bytes
    raw_text: str | None           # 用户输入的文本
    multi_modal: bool              # True → GPT-4o Vision, False → OCR

    # OCR 中间结果
    ocr_text: str | None           # OCR 提取的原始文本

    # LLM 结构化后
    stem: str | None
    options: str | None            # JSON 字符串
    question_type: str | None      # choice / multi_choice / fill_blank / essay / true_false
    subject: str | None
    exam_variant: str | None
    user_answer: str | None        # 从输入中提取的用户作答
    difficulty: int | None

    # 知识点匹配
    knowledge_point_id: int | None

    # 解答/批改结果
    correct_answer: str | None
    explanation: str | None
    is_correct: bool | None
    errors: list[str] | None

    # 持久化
    image_url: str | None
    created_by: int | None         # 当前用户 ID
    saved_question_id: int | None
    saved_record_id: int | None

    # 内部
    _db_session: AsyncSession | None


    # 错误
    error: str | None


# ── 节点函数 ──


async def vision_extract(state: AiSolveState) -> dict:
    """多模态模式：调用 GPT-4o Vision 直接从图片提取题目"""
    if not state.get("image_data"):
        return {"error": "多模态模式需要上传图片"}

    img_b64 = base64.b64encode(state["image_data"]).decode("utf-8")
    prompt = (
        "你是考研题目提取专家。从图片中提取题目信息，以 JSON 格式返回。\n\n"
        "字段说明：\n"
        "- stem: 题目正文（含 LaTeX 公式用 $...$ 包裹）\n"
        "- options: 选项数组 JSON 字符串，如 [\"A. xxx\", \"B. xxx\"]，无选项则为 []\n"
        "- question_type: choice / multi_choice / fill_blank / essay / true_false\n"
        "- subject: 科目（数学/英语/政治）\n"
        "- exam_variant: 考试变体（数一/数二/数三/英一/英二/null）\n"
        "- user_answer: 如果图片中包含了用户的作答答案则提取，否则为 null\n"
        "- difficulty: 难度 1-5\n\n"
        "只返回 JSON，不要多余文字。"
    )

    resp = await llm_vision_chat(prompt, img_b64, temperature=0.3)
    return _parse_structured_output(resp.text)


async def ocr_extract(state: AiSolveState) -> dict:
    """OCR 模式：调用 PaddleOCR + LaTeX-OCR 双引擎提取文字与公式"""
    if not state.get("image_data"):
        return {"error": "OCR 模式需要上传图片"}

    try:
        from paddleocr import PaddleOCR
    except ImportError:
        return {"error": "PaddleOCR 未安装，请执行 pip install paddlepaddle paddleocr"}

    try:
        from PIL import Image
        from pix2tex.cli import LaTeXOCR
        latex_ocr = LaTeXOCR()
        has_latex_ocr = True
    except ImportError:
        has_latex_ocr = False

    import io
    import os
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(state["image_data"])
    tmp_path = tmp.name
    tmp.close()

    pil_image = Image.open(io.BytesIO(state["image_data"]))

    FORMULA_KEYWORDS = {"lim", "∫", "∑", "√", "→", "∞", "π", "θ", "α", "β",
                        "sin", "cos", "tan", "log", "ln", "dx", "dy", "∂"}

    def is_formula_line(text: str) -> bool:
        text_lower = text.lower()
        for kw in FORMULA_KEYWORDS:
            if kw in text_lower:
                return True
        if re.search(r'\d+/\d+', text):
            return True
        if '=' in text and len(text) < 80:
            return True
        return False

    try:
        ocr = PaddleOCR(use_angle_cls=True, lang="ch")
        result = ocr.ocr(tmp_path, cls=True)
        lines_with_coords: list[tuple[str, tuple[float, float, float, float], bool]] = []

        for page in result:
            for line_info in page:
                bbox = line_info[0]
                text = line_info[1][0]
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
                is_formula = is_formula_line(text)
                lines_with_coords.append((text, (left, top, right, bottom), is_formula))

        final_lines: list[str] = []
        for text, coords, is_formula in lines_with_coords:
            if is_formula and has_latex_ocr:
                left, top, right, bottom = coords
                pad = 5
                crop = pil_image.crop((
                    max(0, left - pad), max(0, top - pad),
                    min(pil_image.width, right + pad),
                    min(pil_image.height, bottom + pad),
                ))
                try:
                    latex_code = latex_ocr(crop)
                    final_lines.append(latex_code)
                except Exception:
                    final_lines.append(text)
            else:
                final_lines.append(text)

        raw = "\n".join(final_lines)
    except Exception as e:
        raw = f"OCR 识别失败: {e}"
    finally:
        os.unlink(tmp_path)

    return {"ocr_text": raw}


async def llm_structurize(state: AiSolveState) -> dict:
    """将 OCR 文本或用户输入文本结构化。若已从 vision_extract 获取结构化数据则跳过。"""
    if state.get("stem"):
        return {}

    source_text = state.get("ocr_text") or state.get("raw_text")
    if not source_text:
        return {"error": "没有可处理的文本"}

    prompt = (
        "你是考研题目结构化专家。将以下文本整理为标准格式。\n\n"
        f"原始文本：\n{source_text}\n\n"
        "以 JSON 格式返回：\n"
        "- stem: 题目正文（LaTeX 公式用 $...$ 包裹）\n"
        "- options: 选项 JSON 字符串，如 [\"A. xxx\", \"B. xxx\"]\n"
        "- question_type: choice / multi_choice / fill_blank / essay / true_false\n"
        "- subject: 科目（数学/英语/政治）\n"
        "- exam_variant: 考试变体（数一/数二/数三/英一/英二/null）\n"
        "- user_answer: 如果文本包含用户作答则提取，否则为 null\n"
        "- difficulty: 难度 1-5\n\n"
        "只返回 JSON，不要多余文字。"
    )

    resp = await llm_chat(
        messages=[
            {"role": "system", "content": "你是考研题目结构化专家，擅长整理题目文本。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return _parse_structured_output(resp.text)


def _parse_structured_output(text: str) -> dict:
    """从 LLM 输出中提取 JSON 并映射到 state 字段"""
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"error": f"LLM 输出解析失败: {text[:200]}"}

    return {
        "stem": data.get("stem"),
        "options": json.dumps(data.get("options", []), ensure_ascii=False),
        "question_type": data.get("question_type"),
        "subject": data.get("subject"),
        "exam_variant": data.get("exam_variant"),
        "user_answer": data.get("user_answer"),
        "difficulty": data.get("difficulty", 3),
    }


def _route(state: AiSolveState) -> str:
    return "grade_agent" if state.get("user_answer") else "solve_agent"


async def solve_agent(state: AiSolveState) -> dict:
    """AI 解题 + 生成解析"""
    if not state.get("stem"):
        return {"error": "缺少题目内容"}

    prompt = (
        f"题目：{state['stem']}\n"
        f"选项：{state.get('options', '[]')}\n"
        f"题型：{state.get('question_type', '未知')}\n"
        f"科目：{state.get('subject', '未知')}\n\n"
        "请回答：\n"
        "1. 正确答案是什么？\n"
        "2. 给出详细解析\n\n"
        "以 JSON 格式返回：\n"
        '{{"correct_answer": "A", "explanation": "解析内容...", "difficulty": 3}}'
    )

    resp = await llm_chat(
        messages=[
            {"role": "system", "content": "你是考研辅导专家，擅长解题和解析。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=2048,
    )

    try:
        text = resp.text
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        return {
            "correct_answer": data.get("correct_answer", ""),
            "explanation": data.get("explanation", ""),
            "difficulty": data.get("difficulty", state.get("difficulty", 3)),
        }
    except (ValueError, json.JSONDecodeError):
        return {
            "correct_answer": "",
            "explanation": resp.text,
            "difficulty": state.get("difficulty", 3),
        }


async def grade_agent(state: AiSolveState) -> dict:
    """对比用户答案批改 + 错题分析"""
    if not state.get("stem") or not state.get("user_answer"):
        return {"error": "缺少题目或用户答案"}

    prompt = (
        f"题目：{state['stem']}\n"
        f"选项：{state.get('options', '[]')}\n"
        f"题型：{state.get('question_type', '未知')}\n"
        f"科目：{state.get('subject', '未知')}\n"
        f"用户答案：{state['user_answer']}\n\n"
        "请批改：\n"
        "1. 正确答案是什么？\n"
        "2. 用户答对了吗？\n"
        "3. 错因分析（如果答错）\n"
        "4. 给出详细解析\n\n"
        "以 JSON 格式返回：\n"
        '{{"correct_answer": "B", "is_correct": false, "errors": ["知识点理解有误"], "explanation": "解析内容...", "difficulty": 3}}'
    )

    resp = await llm_chat(
        messages=[
            {"role": "system", "content": "你是考研批改专家，擅长批改和错题分析。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=2048,
    )

    try:
        text = resp.text
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        return {
            "correct_answer": data.get("correct_answer", ""),
            "is_correct": data.get("is_correct"),
            "errors": data.get("errors", []),
            "explanation": data.get("explanation", ""),
            "difficulty": data.get("difficulty", state.get("difficulty", 3)),
        }
    except (ValueError, json.JSONDecodeError):
        return {
            "correct_answer": "",
            "is_correct": None,
            "errors": [],
            "explanation": resp.text,
            "difficulty": state.get("difficulty", 3),
        }


async def knowledge_matcher(state: AiSolveState) -> dict:
    """根据科目 + 题目内容匹配知识点"""
    from core.database import async_session

    subject = state.get("subject")
    if not subject:
        return {}

    async with async_session() as session:
        result = await session.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.subject == subject,
                KnowledgePoint.level == 2,
            ).limit(20)
        )
        points = result.scalars().all()

    if not points:
        return {}

    points_text = "\n".join(f"{p.id}: {p.name}" for p in points)
    prompt = (
        f"题目：{state.get('stem', '')}\n"
        f"科目：{subject}\n\n"
        f"可选知识点：\n{points_text}\n\n"
        "返回最匹配的知识点 ID，只输出数字。"
    )

    try:
        resp = await llm_chat(
            messages=[
                {"role": "system", "content": "你只输出知识点 ID 数字，不要其他文字。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=10,
        )
        match = re.search(r"\d+", resp.text.strip())
        if match:
            kp_id = int(match.group())
            if any(p.id == kp_id for p in points):
                return {"knowledge_point_id": kp_id}
    except Exception:
        pass

    return {"knowledge_point_id": points[0].id}


async def save_result(state: AiSolveState) -> dict:
    """将题目保存到 questions 表 + 创建 StudyRecord"""
    db = state.get("_db_session")
    if not db:
        return {"error": "缺少数据库会话"}

    user_id = state.get("created_by")
    if not user_id:
        return {"error": "缺少用户信息"}

    stem = state.get("stem", "").strip()
    if not stem:
        return {"error": "缺少题目内容"}

    try:
        existing = await db.execute(select(Question).where(Question.stem == stem))
        question = existing.scalar_one_or_none()

        if not question:
            question = Question(
                question_type=state.get("question_type", "choice"),
                subject=state.get("subject", ""),
                exam_variant=state.get("exam_variant"),
                knowledge_point_id=state.get("knowledge_point_id"),
                stem=stem,
                options=state.get("options", "[]"),
                correct_answer=state.get("correct_answer", ""),
                explanation=state.get("explanation"),
                difficulty=state.get("difficulty", 3),
                images=state.get("image_url"),
                created_by=user_id,
            )
            db.add(question)
            await db.flush()

        record = StudyRecord(
            user_id=user_id,
            subject=state.get("subject", ""),
            knowledge_point_id=state.get("knowledge_point_id"),
            question_id=question.id,
            is_correct=state.get("is_correct"),
            duration_seconds=0,
        )
        db.add(record)
        await db.flush()

        return {
            "saved_question_id": question.id,
            "saved_record_id": record.id,
        }
    except Exception as e:
        return {"error": f"保存失败: {e}"}


async def format_response(state: AiSolveState) -> dict:
    """组装最终响应（终端节点，不做转换）"""
    return {}


# ── Workflow ──


def build_ai_solve_graph() -> StateGraph:
    workflow = StateGraph(AiSolveState)

    workflow.add_node("vision_extract", vision_extract)
    workflow.add_node("ocr_extract", ocr_extract)
    workflow.add_node("llm_structurize", llm_structurize)
    workflow.add_node("solve_agent", solve_agent)
    workflow.add_node("grade_agent", grade_agent)
    workflow.add_node("knowledge_matcher", knowledge_matcher)
    workflow.add_node("save_result", save_result)
    workflow.add_node("format_response", format_response)

    workflow.set_conditional_entry_point(
        _entry_route,
        {
            "vision_extract": "vision_extract",
            "ocr_extract": "ocr_extract",
            "llm_structurize": "llm_structurize",
        },
    )

    workflow.add_edge("vision_extract", "llm_structurize")
    workflow.add_edge("ocr_extract", "llm_structurize")

    workflow.add_conditional_edges(
        "llm_structurize",
        _route,
        {"solve_agent": "solve_agent", "grade_agent": "grade_agent"},
    )

    workflow.add_edge("solve_agent", "knowledge_matcher")
    workflow.add_edge("grade_agent", "knowledge_matcher")
    workflow.add_edge("knowledge_matcher", "save_result")
    workflow.add_edge("save_result", "format_response")
    workflow.add_edge("format_response", END)

    return workflow


def _entry_route(state: AiSolveState) -> str:
    if state.get("raw_text"):
        return "llm_structurize"
    if state.get("multi_modal"):
        return "vision_extract"
    return "ocr_extract"


ai_solve_app = build_ai_solve_graph().compile()


# ── 公共入口 ──


class AiSolveInput(TypedDict, total=False):
    image_data: bytes | None
    raw_text: str | None
    multi_modal: bool
    subject: str | None
    exam_variant: str | None


class AiSolveOutput(TypedDict):
    question: dict | None
    explanation: str | None
    user_answer: str | None
    correct_answer: str | None
    is_correct: bool | None
    errors: list[str] | None
    record: dict | None
    error: str | None


async def run_ai_solve(
    inputs: AiSolveInput,
    db: AsyncSession,
    user_id: int,
) -> AiSolveOutput:
    """外部统一入口"""
    logger.info(f"run_ai_solve start — user_id={user_id}, has_image={inputs.get('image_data') is not None}, raw_text_len={len(inputs.get('raw_text') or '')}, multi_modal={inputs.get('multi_modal')}")

    initial: AiSolveState = {
        "image_data": inputs.get("image_data"),
        "raw_text": inputs.get("raw_text"),
        "multi_modal": inputs.get("multi_modal", False),
        "ocr_text": None,
        "stem": None,
        "options": None,
        "question_type": None,
        "subject": inputs.get("subject"),
        "exam_variant": inputs.get("exam_variant"),
        "user_answer": None,
        "difficulty": None,
        "knowledge_point_id": None,
        "correct_answer": None,
        "explanation": None,
        "is_correct": None,
        "errors": None,
        "image_url": None,
        "created_by": user_id,
        "saved_question_id": None,
        "saved_record_id": None,
        "_db_session": db,
        "error": None,
    }

    try:
        result = await ai_solve_app.ainvoke(initial)
        logger.info(f"ainvoke completed — saved_question_id={result.get('saved_question_id')}, error={result.get('error')}")
    except Exception as e:
        logger.error(f"ainvoke failed: {e}\n{traceback.format_exc()}")
        return AiSolveOutput(error=f"Agent 执行失败: {e}")

    if result.get("error"):
        return AiSolveOutput(error=result["error"])

    question_data = None
    if result.get("saved_question_id"):
        question_data = {
            "id": result["saved_question_id"],
            "stem": result.get("stem"),
            "options": result.get("options"),
            "question_type": result.get("question_type"),
            "subject": result.get("subject"),
            "exam_variant": result.get("exam_variant"),
            "difficulty": result.get("difficulty"),
            "knowledge_point_id": result.get("knowledge_point_id"),
            "image_url": result.get("image_url"),
        }

    record_data = None
    if result.get("saved_record_id"):
        record_data = {
            "id": result["saved_record_id"],
            "is_correct": result.get("is_correct"),
            "subject": result.get("subject"),
            "knowledge_point_id": result.get("knowledge_point_id"),
        }

    return AiSolveOutput(
        question=question_data,
        explanation=result.get("explanation"),
        user_answer=result.get("user_answer"),
        correct_answer=result.get("correct_answer"),
        is_correct=result.get("is_correct"),
        errors=result.get("errors"),
        record=record_data,
        error=None,
    )

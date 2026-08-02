"""AI 解答/批改 Agent — LangGraph 工作流

流程：
  image → [多模态模式 ? vision_extract : ocr_extract] → llm_structurize
  → route_decision → solve_agent / grade_agent → knowledge_matcher → save_result → format_response

Tutor 多轮引导流程：
  首轮: image/text → extract → structure → tutor_guide(hint=1) → save_tutor_session → format
  续接: load_tutor_session → tutor_guide(next hint) → save_tutor_session → format
  索答: load_tutor_session → solve_agent → knowledge_matcher → save_result → save_tutor_session(completed) → format

用法：
  from agents.ai_solve_agent import run_ai_solve, run_tutor_start, run_tutor_continue, run_tutor_reveal
"""

from __future__ import annotations

import base64
import json
import logging
import re
import traceback
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from llm.gateway import llm_chat, llm_vision_chat
from models.study import KnowledgePoint, Question, StudyRecord
from models.tutor import TutorSession
from services.user_state import record_user_state

logger = logging.getLogger("ai_solve_agent")
logger.setLevel(logging.DEBUG)


# ── State ──


class AiSolveState(TypedDict):
    # 输入
    image_data: bytes | None
    raw_text: str | None
    multi_modal: bool

    # OCR 中间结果
    ocr_text: str | None

    # LLM 结构化后
    stem: str | None
    options: str | None
    question_type: str | None
    subject: str | None
    exam_variant: str | None
    user_answer: str | None
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
    created_by: int | None
    saved_question_id: int | None
    saved_record_id: int | None

    # 内部
    _db_session: AsyncSession | None

    # Tutor 多轮引导
    session_id: int | None
    tutor_mode: str | None           # "start" / "continue" / "reveal" / None
    conversation_round: int           # 当前轮次 (0-3)
    hint_level: int                   # 提示层级 (1-4)
    conversation_history: list[dict]  # 从 messages JSONB 恢复
    should_reveal_answer: bool
    tutor_message: str | None         # 当前轮的 AI 引导语

    # 错误
    error: str | None


# ── Prompt 模板 ──

TUTOR_PROMPTS = {
    1: """你是一位考研辅导专家，正在用苏格拉底式教学法引导学生思考。请仔细阅读题目，一步步引导学生自己发现答案，不要直接给出答案。

现在只做第1层引导——审题：
请引导学生回答以下问题：
1. 这道题在问什么？（用一句话概括）
2. 题目中给出了哪些已知条件？
3. 这道题可能涉及哪个知识点？

语气要温和鼓励，先让学生自己想一想，然后告诉他你的理解。不要继续下一层引导，停在审题这一步。""",

    2: """你是一位考研辅导专家，正在用苏格拉底式教学法引导学生思考。

学生已经完成了审题（上一轮），现在做第2层引导——思路：
学生已经知道这道题考察的是哪个知识点。现在请引导学生思考：
1. 解决这类问题通常用什么方法/公式？
2. 已知条件可以如何转化？

根据学生上一轮的回复给予肯定或纠正，然后引导学生试着把第一步思路写出来，不用算出最终结果。不要继续下一层引导。""",

    3: """你是一位考研辅导专家，正在用苏格拉底式教学法引导学生思考。

学生已经理解了思路（前两轮），现在做第3层引导——计算：
学生的大方向是对的。现在引导他：
1. 把公式代入已知条件
2. 指出可能的易错点，提醒注意
3. 请学生写出计算过程

语气要具体，指出他当前思路中哪个地方容易出错。不要继续下一层引导，不要给最终答案。""",

    4: """你是一位考研辅导专家。学生已经尝试了多轮思考，现在给出完整解析。

请提供：
1. **正确答案**：清晰写出
2. **详细步骤**：分步列出解题过程
3. **思路反馈**：指出学生思考中值得肯定的地方和需要改进的地方

语气要既专业又温暖，肯定学生的努力。""",
}


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
    if state.get("tutor_mode") == "start":
        return "tutor_guide"
    if state.get("user_answer"):
        return "grade_agent"
    return "solve_agent"


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
        '{"correct_answer": "A", "explanation": "解析内容...", "difficulty": 3}'
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
        '{"correct_answer": "B", "is_correct": false, "errors": ["知识点理解有误"], "explanation": "解析内容...", "difficulty": 3}'
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


async def tutor_guide(state: AiSolveState) -> dict:
    """苏格拉底式分步引导 — 根据 hint_level 生成对应引导语"""
    hint_level = state.get("hint_level", 1)
    prompt_template = TUTOR_PROMPTS.get(hint_level, TUTOR_PROMPTS[1])

    stem = state.get("stem", "")
    options = state.get("options", "[]")
    question_type = state.get("question_type", "未知")
    subject = state.get("subject", "未知")

    history_text = ""
    history = state.get("conversation_history", [])
    if history:
        history_text = "\n\n## 之前的对话历史\n"
        for msg in history:
            role_label = "AI引导" if msg["role"] == "assistant" else "学生回答"
            history_text += f"[第{msg['round']+1}轮 {role_label}]: {msg['content']}\n"

    prompt = (
        f"## 题目信息\n"
        f"题目：{stem}\n"
        f"选项：{options}\n"
        f"题型：{question_type}\n"
        f"科目：{subject}\n"
        f"{history_text}\n"
        f"## 当前任务\n"
        f"{prompt_template}\n\n"
        f"只输出引导语，用温暖鼓励的语气，控制在200字以内。不要用JSON格式。"
    )

    resp = await llm_chat(
        messages=[
            {"role": "system", "content": "你是考研辅导专家，用苏格拉底式教学法引导学生。不要直接给答案，不要用JSON格式回复。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1024,
    )

    return {"tutor_message": resp.text.strip()}


async def load_tutor_session(state: AiSolveState) -> dict:
    """从 DB 加载 tutor_session，恢复题目快照和对话历史"""
    db = state.get("_db_session")
    session_id = state.get("session_id")
    if not db or not session_id:
        return {"error": "缺少数据库会话或 session_id"}

    result = await db.execute(select(TutorSession).where(TutorSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        return {"error": f"会话 {session_id} 不存在"}

    snapshot = session.question_snapshot or {}
    messages = session.messages or []

    return {
        "stem": snapshot.get("stem"),
        "options": snapshot.get("options"),
        "question_type": snapshot.get("question_type"),
        "subject": snapshot.get("subject"),
        "exam_variant": snapshot.get("exam_variant"),
        "difficulty": snapshot.get("difficulty"),
        "knowledge_point_id": snapshot.get("knowledge_point_id"),
        "correct_answer": snapshot.get("correct_answer"),
        "explanation": snapshot.get("explanation"),
        "conversation_round": session.current_round + 1,  # 进入新轮次
        "hint_level": session.hint_level,
        "conversation_history": messages,
        "created_by": session.user_id,
    }


async def save_tutor_session(state: AiSolveState) -> dict:
    """创建或更新 tutor_session"""
    db = state.get("_db_session")
    if not db:
        return {"error": "缺少数据库会话"}

    session_id = state.get("session_id")
    hint_level = state.get("hint_level", 1)
    current_round = state.get("conversation_round", 0)
    tutor_mode = state.get("tutor_mode", "")
    should_reveal = state.get("should_reveal_answer", False)

    is_completed = (hint_level >= 4 and current_round >= 3) or should_reveal
    new_status = "completed" if is_completed else "active"

    if session_id and (tutor_mode in ("continue", "reveal")):
        result = await db.execute(select(TutorSession).where(TutorSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            return {"error": f"会话 {session_id} 不存在"}

        messages = list(session.messages or [])

        user_input = state.get("raw_text")
        if user_input and tutor_mode == "continue":
            messages.append({
                "role": "user",
                "content": user_input,
                "round": current_round - 1,
                "hint_level": hint_level - 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        ai_message = state.get("tutor_message")
        if not ai_message and state.get("explanation"):
            # solve/reveal 路径没有 tutor_message，用最终答案组装一条消息以便持久化
            correct = state.get("correct_answer")
            parts = []
            if correct:
                parts.append(f"【正确答案】{correct}")
            parts.append(state["explanation"])
            ai_message = "\n\n".join(parts)

        if ai_message:
            messages.append({
                "role": "assistant",
                "content": ai_message,
                "round": current_round,
                "hint_level": hint_level,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        session.messages = messages
        session.current_round = current_round
        session.hint_level = hint_level + 1 if hint_level < 4 else 4
        session.status = new_status

        if state.get("saved_question_id"):
            session.question_id = state["saved_question_id"]

        await db.flush()
        return {"session_id": session.id}

    else:
        now = datetime.now(timezone.utc).isoformat()
        messages = []

        ai_message = state.get("tutor_message")
        if ai_message:
            messages.append({
                "role": "assistant",
                "content": ai_message,
                "round": 0,
                "hint_level": 1,
                "created_at": now,
            })

        snapshot = {
            "stem": state.get("stem"),
            "options": state.get("options"),
            "question_type": state.get("question_type"),
            "subject": state.get("subject"),
            "exam_variant": state.get("exam_variant"),
            "difficulty": state.get("difficulty"),
            "knowledge_point_id": state.get("knowledge_point_id"),
            "correct_answer": state.get("correct_answer"),
            "explanation": state.get("explanation"),
        }

        session = TutorSession(
            user_id=state.get("created_by"),
            question_id=state.get("saved_question_id"),
            current_round=0,
            hint_level=2,
            status="active",
            messages=messages,
            question_snapshot=snapshot,
        )
        db.add(session)
        await db.flush()
        return {"session_id": session.id}


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
    """将题目保存到 questions 表 + 调用 record_user_state 写用户状态（4 表 UPSERT）"""
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

        # 从 LLM 输出的 errors 列表取第一条作为 error_category
        errors = state.get("errors") or []
        error_category = errors[0].strip()[:64] if errors else None

        record = await record_user_state(
            db,
            user_id=user_id,
            kp_id=state.get("knowledge_point_id"),
            is_correct=state.get("is_correct"),
            error_category=error_category,
            source="ai",  # AI 辅导路径固定标 ai
            subject=state.get("subject", ""),
            question_id=question.id,
            duration_seconds=0,
        )
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


# ── 图构建 ──


def build_ai_solve_graph() -> StateGraph:
    """主图：支持单次解答/批改 + Tutor 首轮"""
    workflow = StateGraph(AiSolveState)

    workflow.add_node("vision_extract", vision_extract)
    workflow.add_node("ocr_extract", ocr_extract)
    workflow.add_node("llm_structurize", llm_structurize)
    workflow.add_node("solve_agent", solve_agent)
    workflow.add_node("grade_agent", grade_agent)
    workflow.add_node("tutor_guide", tutor_guide)
    workflow.add_node("knowledge_matcher", knowledge_matcher)
    workflow.add_node("save_result", save_result)
    workflow.add_node("save_tutor_session", save_tutor_session)
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
        {
            "solve_agent": "solve_agent",
            "grade_agent": "grade_agent",
            "tutor_guide": "tutor_guide",
        },
    )

    # 非 tutor 路径
    workflow.add_edge("solve_agent", "knowledge_matcher")
    workflow.add_edge("grade_agent", "knowledge_matcher")
    workflow.add_edge("knowledge_matcher", "save_result")
    workflow.add_edge("save_result", "format_response")

    # tutor 首轮路径
    workflow.add_edge("tutor_guide", "save_tutor_session")
    workflow.add_edge("save_tutor_session", "format_response")

    workflow.add_edge("format_response", END)

    return workflow


def build_tutor_continue_graph() -> StateGraph:
    """Tutor 续接图：从 session 恢复后继续引导"""
    workflow = StateGraph(AiSolveState)

    workflow.add_node("load_tutor_session", load_tutor_session)
    workflow.add_node("tutor_guide", tutor_guide)
    workflow.add_node("solve_agent", solve_agent)
    workflow.add_node("knowledge_matcher", knowledge_matcher)
    workflow.add_node("save_result", save_result)
    workflow.add_node("save_tutor_session", save_tutor_session)
    workflow.add_node("format_response", format_response)

    workflow.set_entry_point("load_tutor_session")

    workflow.add_conditional_edges(
        "load_tutor_session",
        _tutor_continue_route,
        {
            "tutor_guide": "tutor_guide",
            "solve_agent": "solve_agent",
        },
    )

    # 继续引导路径
    workflow.add_edge("tutor_guide", "save_tutor_session")
    workflow.add_edge("save_tutor_session", "format_response")

    # 索要答案路径
    workflow.add_edge("solve_agent", "knowledge_matcher")
    workflow.add_edge("knowledge_matcher", "save_result")
    workflow.add_edge("save_result", "save_tutor_session")

    workflow.add_edge("format_response", END)

    return workflow


def _entry_route(state: AiSolveState) -> str:
    if state.get("raw_text"):
        return "llm_structurize"
    if state.get("multi_modal"):
        return "vision_extract"
    return "ocr_extract"


def _tutor_continue_route(state: AiSolveState) -> str:
    if state.get("should_reveal_answer") or state.get("conversation_round", 0) >= 3:
        return "solve_agent"
    return "tutor_guide"


ai_solve_app = build_ai_solve_graph().compile()
tutor_continue_app = build_tutor_continue_graph().compile()


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


class TutorStartOutput(TypedDict):
    session_id: int
    message: str
    current_round: int
    hint_level: int
    status: str
    error: str | None


class TutorContinueOutput(TypedDict):
    session_id: int
    message: str
    current_round: int
    hint_level: int
    status: str
    error: str | None


async def run_ai_solve(
    inputs: AiSolveInput,
    db: AsyncSession,
    user_id: int,
) -> AiSolveOutput:
    """外部统一入口 — 单次解答/批改"""
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
        "session_id": None,
        "tutor_mode": None,
        "conversation_round": 0,
        "hint_level": 1,
        "conversation_history": [],
        "should_reveal_answer": False,
        "tutor_message": None,
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


async def run_tutor_start(
    inputs: AiSolveInput,
    db: AsyncSession,
    user_id: int,
) -> TutorStartOutput:
    """Tutor 首轮：提取题目 → 创建 session → 返回第1层引导语"""
    logger.info(f"run_tutor_start — user_id={user_id}")

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
        "session_id": None,
        "tutor_mode": "start",
        "conversation_round": 0,
        "hint_level": 1,
        "conversation_history": [],
        "should_reveal_answer": False,
        "tutor_message": None,
        "error": None,
    }

    try:
        result = await ai_solve_app.ainvoke(initial)
    except Exception as e:
        logger.error(f"tutor_start failed: {e}\n{traceback.format_exc()}")
        return TutorStartOutput(session_id=0, message="", current_round=0, hint_level=1, status="error", error=str(e))

    if result.get("error"):
        return TutorStartOutput(session_id=0, message="", current_round=0, hint_level=1, status="error", error=result["error"])

    await db.commit()

    return TutorStartOutput(
        session_id=result.get("session_id", 0),
        message=result.get("tutor_message", ""),
        current_round=0,
        hint_level=1,
        status="active",
        error=None,
    )


async def run_tutor_continue(
    session_id: int,
    user_input: str,
    db: AsyncSession,
    user_id: int,
) -> TutorContinueOutput:
    """Tutor 续接：读取 session → 推进到下一轮引导"""
    logger.info(f"run_tutor_continue — session_id={session_id}")

    initial: AiSolveState = {
        "image_data": None,
        "raw_text": user_input,
        "multi_modal": False,
        "ocr_text": None,
        "stem": None,
        "options": None,
        "question_type": None,
        "subject": None,
        "exam_variant": None,
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
        "session_id": session_id,
        "tutor_mode": "continue",
        "conversation_round": 0,
        "hint_level": 1,
        "conversation_history": [],
        "should_reveal_answer": False,
        "tutor_message": None,
        "error": None,
    }

    try:
        result = await tutor_continue_app.ainvoke(initial)
    except Exception as e:
        logger.error(f"tutor_continue failed: {e}\n{traceback.format_exc()}")
        return TutorContinueOutput(session_id=session_id, message="", current_round=0, hint_level=1, status="error", error=str(e))

    if result.get("error"):
        return TutorContinueOutput(session_id=session_id, message="", current_round=0, hint_level=1, status="error", error=result["error"])

    await db.commit()

    next_hint = result.get("hint_level", 1)
    status = "completed" if result.get("conversation_round", 0) >= 3 else "active"

    return TutorContinueOutput(
        session_id=session_id,
        message=result.get("tutor_message", ""),
        current_round=result.get("conversation_round", 0),
        hint_level=next_hint,
        status=status,
        error=None,
    )


async def run_tutor_reveal(
    session_id: int,
    db: AsyncSession,
    user_id: int,
) -> TutorContinueOutput:
    """Tutor 索要答案：加载 session → 直接给完整解析"""
    logger.info(f"run_tutor_reveal — session_id={session_id}")

    initial: AiSolveState = {
        "image_data": None,
        "raw_text": None,
        "multi_modal": False,
        "ocr_text": None,
        "stem": None,
        "options": None,
        "question_type": None,
        "subject": None,
        "exam_variant": None,
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
        "session_id": session_id,
        "tutor_mode": "reveal",
        "conversation_round": 3,
        "hint_level": 4,
        "conversation_history": [],
        "should_reveal_answer": True,
        "tutor_message": None,
        "error": None,
    }

    try:
        result = await tutor_continue_app.ainvoke(initial)
    except Exception as e:
        logger.error(f"tutor_reveal failed: {e}\n{traceback.format_exc()}")
        return TutorContinueOutput(session_id=session_id, message="", current_round=0, hint_level=1, status="error", error=str(e))

    if result.get("error"):
        return TutorContinueOutput(session_id=session_id, message="", current_round=0, hint_level=1, status="error", error=result["error"])

    await db.commit()

    return TutorContinueOutput(
        session_id=session_id,
        message=result.get("explanation") or result.get("tutor_message", ""),
        current_round=result.get("conversation_round", 3),
        hint_level=4,
        status="completed",
        error=None,
    )

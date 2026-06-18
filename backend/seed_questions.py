"""题库种子数据 — python -m seed_questions"""
import asyncio
import json

from sqlalchemy import select, func

from core.database import engine, async_session, Base
import models.user  # ensure users table is registered in metadata
from models.study import Question, QuestionGroup, KnowledgePoint


# ── 知识点 ——

MATH_KNOWLEDGE = [
    # 高等数学 (MA)
    {"code": "MA", "name": "高等数学", "subject": "数学", "parent_id": None, "level": 1, "sort_order": 1, "applicable_variants": "数一,数二,数三"},
    {"code": "MA-C1", "name": "函数、极限、连续", "subject": "数学", "level": 2, "sort_order": 101, "applicable_variants": "数一,数二,数三"},
    {"code": "MA-C2", "name": "一元函数微分学", "subject": "数学", "level": 2, "sort_order": 102, "applicable_variants": "数一,数二,数三"},
    {"code": "MA-C3", "name": "一元函数积分学", "subject": "数学", "level": 2, "sort_order": 103, "applicable_variants": "数一,数二,数三"},
    {"code": "MA-C4", "name": "向量代数与空间解析几何", "subject": "数学", "level": 2, "sort_order": 104, "applicable_variants": "数一"},
    {"code": "MA-C5", "name": "多元函数微分学", "subject": "数学", "level": 2, "sort_order": 105, "applicable_variants": "数一,数二,数三"},
    {"code": "MA-C6", "name": "多元函数积分学", "subject": "数学", "level": 2, "sort_order": 106, "applicable_variants": "数一"},
    {"code": "MA-C7", "name": "无穷级数", "subject": "数学", "level": 2, "sort_order": 107, "applicable_variants": "数一,数三"},
    {"code": "MA-C7-F", "name": "无穷级数—傅里叶级数", "subject": "数学", "level": 3, "sort_order": 1071, "applicable_variants": "数一"},
    {"code": "MA-C8", "name": "常微分方程", "subject": "数学", "level": 2, "sort_order": 108, "applicable_variants": "数一,数二,数三"},
    {"code": "MA-C8-DE", "name": "常微分方程与差分方程", "subject": "数学", "level": 3, "sort_order": 1081, "applicable_variants": "数三"},
    # 线性代数 (LA)
    {"code": "LA", "name": "线性代数", "subject": "数学", "parent_id": None, "level": 1, "sort_order": 200, "applicable_variants": "数一,数二,数三"},
    {"code": "LA-C1", "name": "行列式", "subject": "数学", "level": 2, "sort_order": 201, "applicable_variants": "数一,数二,数三"},
    {"code": "LA-C2", "name": "矩阵", "subject": "数学", "level": 2, "sort_order": 202, "applicable_variants": "数一,数二,数三"},
    {"code": "LA-C3", "name": "向量", "subject": "数学", "level": 2, "sort_order": 203, "applicable_variants": "数一,数二,数三"},
    {"code": "LA-C4", "name": "线性方程组", "subject": "数学", "level": 2, "sort_order": 204, "applicable_variants": "数一,数二,数三"},
    {"code": "LA-C5", "name": "矩阵的特征值和特征向量", "subject": "数学", "level": 2, "sort_order": 205, "applicable_variants": "数一,数二,数三"},
    {"code": "LA-C6", "name": "二次型", "subject": "数学", "level": 2, "sort_order": 206, "applicable_variants": "数一,数二,数三"},
    # 概率统计 (PS) — 仅数一数三
    {"code": "PS", "name": "概率论与数理统计", "subject": "数学", "parent_id": None, "level": 1, "sort_order": 300, "applicable_variants": "数一,数三"},
    {"code": "PS-C1", "name": "随机事件和概率", "subject": "数学", "level": 2, "sort_order": 301, "applicable_variants": "数一,数三"},
    {"code": "PS-C2", "name": "随机变量及其分布", "subject": "数学", "level": 2, "sort_order": 302, "applicable_variants": "数一,数三"},
    {"code": "PS-C3", "name": "多维随机变量及其分布", "subject": "数学", "level": 2, "sort_order": 303, "applicable_variants": "数一,数三"},
    {"code": "PS-C4", "name": "随机变量的数字特征", "subject": "数学", "level": 2, "sort_order": 304, "applicable_variants": "数一,数三"},
    {"code": "PS-C5", "name": "大数定律与中心极限定理", "subject": "数学", "level": 2, "sort_order": 305, "applicable_variants": "数一,数三"},
    {"code": "PS-C6", "name": "数理统计基本概念", "subject": "数学", "level": 2, "sort_order": 306, "applicable_variants": "数一,数三"},
    {"code": "PS-C7", "name": "参数估计", "subject": "数学", "level": 2, "sort_order": 307, "applicable_variants": "数一,数三"},
    {"code": "PS-C8", "name": "假设检验", "subject": "数学", "level": 2, "sort_order": 308, "applicable_variants": "数一,数三"},
    # 英语
    {"code": "EN", "name": "英语", "subject": "英语", "parent_id": None, "level": 1, "sort_order": 1},
    {"code": "EN-C1", "name": "阅读理解", "subject": "英语", "level": 2, "sort_order": 101},
    {"code": "EN-C2", "name": "完形填空", "subject": "英语", "level": 2, "sort_order": 102},
    {"code": "EN-C3", "name": "翻译", "subject": "英语", "level": 2, "sort_order": 103},
    {"code": "EN-C4", "name": "写作", "subject": "英语", "level": 2, "sort_order": 104},
    # 政治
    {"code": "PO", "name": "政治", "subject": "政治", "parent_id": None, "level": 1, "sort_order": 1},
    {"code": "PO-C1", "name": "马克思主义基本原理", "subject": "政治", "level": 2, "sort_order": 101},
    {"code": "PO-C2", "name": "毛泽东思想和中国特色社会主义理论", "subject": "政治", "level": 2, "sort_order": 102},
    {"code": "PO-C3", "name": "中国近现代史纲要", "subject": "政治", "level": 2, "sort_order": 103},
    {"code": "PO-C4", "name": "思想道德修养与法律基础", "subject": "政治", "level": 2, "sort_order": 104},
    {"code": "PO-C4-MA", "name": "材料分析题", "subject": "政治", "level": 3, "sort_order": 1041},
]


QUESTIONS = [
    # ── 数学一 ──
    {
        "question_type": "choice", "subject": "数学", "exam_variant": "数一",
        "knowledge_point_code": "MA-C1",
        "stem": "极限 $\\lim_{x \\to 0} \\frac{\\sin x}{x}$ 的值是？",
        "options": json.dumps(["A. 0", "B. 1", "C. ∞", "D. 不存在"], ensure_ascii=False),
        "correct_answer": "B", "difficulty": 2,
        "explanation": "由重要极限公式，$\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1$。",
    },
    {
        "question_type": "choice", "subject": "数学", "exam_variant": "数一",
        "knowledge_point_code": "LA-C2",
        "stem": "设 $A$ 为 $n$ 阶方阵，且 $|A| = 0$，则以下哪个结论正确？",
        "options": json.dumps(["A. A 可逆", "B. A 的秩为 n", "C. A 的列向量线性相关", "D. A 是正交矩阵"], ensure_ascii=False),
        "correct_answer": "C", "difficulty": 3,
        "explanation": "行列式为 0 的矩阵不可逆，列向量线性相关。",
    },
    {
        "question_type": "choice", "subject": "数学", "exam_variant": "数一",
        "knowledge_point_code": "PS-C4",
        "stem": "随机变量 $X \\sim N(0,1)$，则 $P(|X| < 1.96)$ 约等于？",
        "options": json.dumps(["A. 0.68", "B. 0.90", "C. 0.95", "D. 0.99"], ensure_ascii=False),
        "correct_answer": "C", "difficulty": 3,
        "explanation": "标准正态分布的 95% 置信区间为 ±1.96。",
    },
    {
        "question_type": "fill_blank", "subject": "数学", "exam_variant": "数一",
        "knowledge_point_code": "MA-C4",
        "stem": "平面 $2x + 3y - z = 5$ 的法向量为 __________。",
        "options": "[]",
        "correct_answer": "(2,3,-1)", "difficulty": 2,
        "explanation": "平面 $Ax+By+Cz=D$ 的法向量为 $(A,B,C)$。",
    },
    {
        "question_type": "essay", "subject": "数学", "exam_variant": "数一",
        "knowledge_point_code": "MA-C6",
        "stem": "计算曲线积分 $\\oint_L (x^2+y^2)\\,ds$，其中 $L$ 为圆周 $x^2+y^2=a^2$。",
        "options": "[]",
        "correct_answer": "2πa³", "difficulty": 4,
        "explanation": "在圆周上 $x^2+y^2=a^2$，被积函数为常数 $a^2$，弧长为 $2\\pi a$，结果 $2\\pi a^3$。",
    },
    # ── 数学三独有 ──
    {
        "question_type": "choice", "subject": "数学", "exam_variant": "数三",
        "knowledge_point_code": "MA-C8-DE",
        "stem": "差分方程 $y_{t+1} - y_t = 3$ 的通解是？",
        "options": json.dumps(["A. $y_t = 3t + C$", "B. $y_t = 3^t + C$", "C. $y_t = t^3 + C$", "D. $y_t = e^{3t} + C$"], ensure_ascii=False),
        "correct_answer": "A", "difficulty": 3,
        "explanation": "一阶线性差分方程 $y_{t+1} - y_t = 3$ 的通解为 $y_t = 3t + C$。",
    },
    # ── 英语 ──
    {
        "question_type": "choice", "subject": "英语", "exam_variant": "英一",
        "knowledge_point_code": "EN-C1",
        "stem": 'The word "ubiquitous" most nearly means:',
        "options": json.dumps(['A. rare', 'B. everywhere', 'C. harmful', 'D. unknown'], ensure_ascii=False),
        "correct_answer": "B", "difficulty": 2,
        "explanation": '"Ubiquitous" 意为“无处不在的”，与 everywhere 同义。',
    },
    {
        "question_type": "choice", "subject": "英语", "exam_variant": "英一",
        "knowledge_point_code": "EN-C2",
        "stem": 'Which of the following sentences contains a dangling modifier?',
        "options": json.dumps([
            "A. Walking to school, the rain began to fall.",
            "B. While walking to school, I felt the rain begin to fall.",
            "C. The rain began to fall as I walked to school.",
            "D. I felt the rain begin to fall while walking to school.",
        ], ensure_ascii=False),
        "correct_answer": "A", "difficulty": 4,
        "explanation": "A 中的主语是 rain，但 rain 不能 walking，修饰语 dangling。B/D 主语是 I，C 结构正确。",
    },
    # ── 政治 ──
    {
        "question_type": "choice", "subject": "政治", "exam_variant": None,
        "knowledge_point_code": "PO-C1",
        "stem": "马克思主义最鲜明的政治立场是（  ）",
        "options": json.dumps(["A. 实现共产主义", "B. 实现人的自由全面发展", "C. 人民至上", "D. 实现最广大人民群众的利益"], ensure_ascii=False),
        "correct_answer": "D", "difficulty": 3,
        "explanation": "马克思主义政党致力于实现最广大人民的根本利益，这是最鲜明的政治立场。",
    },
    {
        "question_type": "multi_choice", "subject": "政治", "exam_variant": None,
        "knowledge_point_code": "PO-C1",
        "stem": "下列属于唯物辩证法的基本规律的有（多选）",
        "options": json.dumps(["A. 对立统一规律", "B. 质量互变规律", "C. 否定之否定规律", "D. 价值规律"], ensure_ascii=False),
        "correct_answer": "ABC", "difficulty": 2,
        "explanation": "唯物辩证法三大规律：对立统一、质量互变、否定之否定。价值规律是政治经济学范畴。",
    },
    # ── 政治材料分析题 ──
    {
        "question_type": "material_analysis", "subject": "政治", "exam_variant": None,
        "knowledge_point_code": "PO-C4-MA",
        "group_index": 0, "group_order": 1,
        "stem": "运用矛盾分析法，分析上述材料中“绿水青山”与“金山银山”的关系。",
        "options": "[]",
        "correct_answer": "矛盾即对立统一。经济发展与生态环境保护是对立统一的辩证关系，要坚持两点论与重点论统一。",
        "difficulty": 4,
        "explanation": "要点：(1)承认矛盾的普遍性 (2)分析矛盾的特殊性 (3)坚持两点论与重点论的统一 (4)具体问题具体分析。",
    },
]


GROUPS = [
    {
        "subject": "政治",
        "title": "材料分析题·生态文明",
        "content": (
            "材料1：习近平总书记指出：“我们既要绿水青山，也要金山银山。"
            "宁要绿水青山，不要金山银山，而且绿水青山就是金山银山。”\n\n"
            "材料2：某地过去以采矿业为主，生态环境遭到严重破坏。近年来，"
            "该地转变发展方式，依托良好的生态环境发展生态旅游和绿色农业，"
            "实现了经济与生态的双赢。"
        ),
    },
]


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        q_count = await session.execute(select(func.count(Question.id)))
        if q_count.scalar() > 0:
            print(f"题库已有 {q_count.scalar()} 道题，跳过 seed")
            await engine.dispose()
            return

        # 1. 写入知识点
        kp_by_code: dict[str, int] = {}
        for kp in MATH_KNOWLEDGE:
            parent_id = kp.get("parent_id")
            # 自动映射 level 2 的 parent
            if parent_id is None and kp["level"] == 2:
                prefix = kp["code"].split("-")[0]
                parent_id = kp_by_code.get(prefix)
            elif kp["level"] == 3:
                parent_code = kp["code"].rsplit("-", 1)[0]
                parent_id = kp_by_code.get(parent_code)

            item = KnowledgePoint(
                code=kp["code"],
                name=kp["name"],
                subject=kp["subject"],
                parent_id=parent_id,
                level=kp["level"],
                sort_order=kp["sort_order"],
                applicable_variants=kp.get("applicable_variants"),
            )
            session.add(item)
            await session.flush()
            kp_by_code[kp["code"]] = item.id

        print(f"写入 {len(MATH_KNOWLEDGE)} 个知识点")

        # 2. 写入 group
        group_ids: list[int] = []
        for g in GROUPS:
            grp = QuestionGroup(**g)
            session.add(grp)
            await session.flush()
            group_ids.append(grp.id)

        # 3. 写入题目
        for q in QUESTIONS:
            code = q.pop("knowledge_point_code", None)
            kp_id = kp_by_code.get(code) if code else None
            gi = q.pop("group_index", None)
            gid = group_ids[gi] if gi is not None and gi < len(group_ids) else None

            session.add(Question(
                question_type=q["question_type"],
                subject=q["subject"],
                exam_variant=q.get("exam_variant"),
                knowledge_point_id=kp_id,
                group_id=gid,
                group_order=q.get("group_order"),
                stem=q["stem"],
                options=q["options"],
                correct_answer=q["correct_answer"],
                explanation=q.get("explanation"),
                difficulty=q.get("difficulty", 1),
            ))

        await session.commit()
        print(f"插入 {len(GROUPS)} 个分组 + {len(QUESTIONS)} 道题完成")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

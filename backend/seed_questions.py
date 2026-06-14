"""题库种子数据 — python -m seed_questions"""
import asyncio
import json

from sqlalchemy import select, func

from core.database import engine, async_session, Base
from models.study import Question, KnowledgePoint


QUESTIONS = [
    # 数学 (4)
    {
        "question_type": "single_choice",
        "subject": "数学",
        "stem": "极限 $\\lim_{x \\to 0} \\frac{\\sin x}{x}$ 的值是？",
        "options": json.dumps(["A. 0", "B. 1", "C. ∞", "D. 不存在"]),
        "correct_answer": "B",
        "explanation": "由重要极限公式，$\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1$。",
        "difficulty": 2,
    },
    {
        "question_type": "single_choice",
        "subject": "数学",
        "stem": "设 $A$ 为 $n$ 阶方阵，且 $|A| = 0$，则以下哪个结论正确？",
        "options": json.dumps(["A. A 可逆", "B. A 的秩为 n", "C. A 的列向量线性相关", "D. A 是正交矩阵"]),
        "correct_answer": "C",
        "explanation": "行列式为 0 的矩阵不可逆，列向量线性相关。",
        "difficulty": 3,
    },
    {
        "question_type": "multi_choice",
        "subject": "数学",
        "stem": "下列哪些函数在 $(-\\infty, +\\infty)$ 上有定义且连续？（多选）",
        "options": json.dumps(["A. $f(x)=|x|$", "B. $f(x)=\\frac{1}{x}$", "C. $f(x)=e^x$", "D. $f(x)=\\ln x$"]),
        "correct_answer": "AC",
        "explanation": "A: 绝对值函数处处连续；C: 指数函数处处连续。B 在 x=0 处无定义，D 定义域为 (0,+∞)。",
        "difficulty": 3,
    },
    {
        "question_type": "single_choice",
        "subject": "数学",
        "stem": "随机变量 $X \\sim N(0,1)$，则 $P(|X| < 1.96)$ 约等于？",
        "options": json.dumps(["A. 0.68", "B. 0.90", "C. 0.95", "D. 0.99"]),
        "correct_answer": "C",
        "explanation": "标准正态分布的 95% 置信区间为 ±1.96。",
        "difficulty": 3,
    },
    # 英语 (3)
    {
        "question_type": "single_choice",
        "subject": "英语",
        "stem": 'The word "ubiquitous" most nearly means:',
        "options": json.dumps(['A. rare', 'B. everywhere', 'C. harmful', 'D. unknown']),
        "correct_answer": "B",
        "explanation": '"Ubiquitous" 意为"无处不在的"，与 everywhere 同义。',
        "difficulty": 2,
    },
    {
        "question_type": "single_choice",
        "subject": "英语",
        "stem": 'Which of the following sentences contains a dangling modifier?',
        "options": json.dumps([
            "A. Walking to school, the rain began to fall.",
            "B. While walking to school, I felt the rain begin to fall.",
            "C. The rain began to fall as I walked to school.",
            "D. I felt the rain begin to fall while walking to school.",
        ]),
        "correct_answer": "A",
        "explanation": "A 中的主语是 rain，但 rain 不能 walking，修饰语 dangling。B/D 主语是 I，C 结构正确。",
        "difficulty": 4,
    },
    {
        "question_type": "true_false",
        "subject": "英语",
        "stem": '判断正误：在考研英语阅读中，作者观点通常出现在段落首句或尾句。',
        "options": json.dumps(["A. 正确", "B. 错误"]),
        "correct_answer": "A",
        "explanation": "考研英语议论文中，topic sentence 通常在段首或段尾，是快速把握作者观点的关键。",
        "difficulty": 2,
    },
    # 政治 (3)
    {
        "question_type": "single_choice",
        "subject": "政治",
        "stem": "马克思主义最鲜明的政治立场是（  ）",
        "options": json.dumps(["A. 实现共产主义", "B. 实现人的自由全面发展", "C. 人民至上", "D. 实现无产阶级和广大人民群众的利益"]),
        "correct_answer": "D",
        "explanation": "马克思主义政党的一切理论和奋斗都致力于实现最广大人民的根本利益，这是马克思主义最鲜明的政治立场。",
        "difficulty": 3,
    },
    {
        "question_type": "multi_choice",
        "subject": "政治",
        "stem": "下列属于唯物辩证法的基本规律的有（多选）",
        "options": json.dumps(["A. 对立统一规律", "B. 质量互变规律", "C. 否定之否定规律", "D. 价值规律"]),
        "correct_answer": "ABC",
        "explanation": "唯物辩证法三大规律：对立统一、质量互变、否定之否定。价值规律是政治经济学范畴。",
        "difficulty": 2,
    },
    {
        "question_type": "true_false",
        "subject": "政治",
        "stem": "判断：毛泽东思想是中国特色社会主义理论体系的重要组成部分。",
        "options": json.dumps(["A. 正确", "B. 错误"]),
        "correct_answer": "B",
        "explanation": "毛泽东思想是马克思主义中国化的第一次历史性飞跃，中国特色社会主义理论体系包括邓小平理论、三个代表、科学发展观、习近平新时代中国特色社会主义思想。",
        "difficulty": 3,
    },
]


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # 跳过已有题目的写入
        result = await session.execute(select(func.count(Question.id)))
        if result.scalar() > 0:
            print(f"题库已有 {result.scalar()} 道题，跳过 seed")
            return

        for q in QUESTIONS:
            session.add(Question(**q))
        await session.commit()
        print(f"插入 {len(QUESTIONS)} 道题完成")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

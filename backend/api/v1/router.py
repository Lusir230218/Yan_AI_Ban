from fastapi import APIRouter

from api.v1 import (
    ai_solve,
    analytics,
    auth,
    encourager,
    evaluation,
    feedback,
    kg_admin,
    knowledge_graph,
    questions,
    study,
    supervisor,
    users,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router, prefix="/auth", tags=["认证"])
router.include_router(users.router, prefix="/users", tags=["用户"])
router.include_router(study.router, prefix="/study", tags=["学习"])
router.include_router(questions.router, prefix="/questions", tags=["题库"])
router.include_router(ai_solve.router, prefix="", tags=["AI 解答"])
router.include_router(evaluation.router, prefix="", tags=["评估"])
router.include_router(encourager.router, prefix="", tags=["鼓励"])
router.include_router(supervisor.router, prefix="", tags=["对话"])
router.include_router(analytics.router, prefix="/analytics", tags=["学习分析"])
# 阶段五·2C
# knowledge_graph.router 内部已声明 prefix="/kg"，父级不再加，避免 /api/v1/kg/kg/...
router.include_router(knowledge_graph.router)
router.include_router(feedback.router, tags=["用户反馈"])
# 阶段五·2D 飞轮 admin
# kg_admin.router 内部已声明 prefix="/kg/admin/flywheel"，父级不再加。
router.include_router(kg_admin.router)

from fastapi import APIRouter

from api.v1 import auth, users, study

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router, prefix="/auth", tags=["认证"])
router.include_router(users.router, prefix="/users", tags=["用户"])
router.include_router(study.router, prefix="/study", tags=["学习"])

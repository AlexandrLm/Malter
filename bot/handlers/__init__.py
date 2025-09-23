from aiogram import Router

from .commands import router as commands_router
from .profile import router as profile_router
from .messages import router as messages_router

router = Router()
router.include_router(commands_router)
router.include_router(profile_router)
router.include_router(messages_router)
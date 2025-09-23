import asyncio
import logging
import httpx
from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from config import DAILY_MESSAGE_LIMIT
from ..services.api_client import make_api_request, handle_api_errors
from .profile import ProfileStates

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
@handle_api_errors
async def command_start(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    user_id = message.from_user.id
    response = await make_api_request(client, "get", f"/profile/{user_id}")
    if response.status_code == 200 and response.json() is not None:
        await message.answer("Привет, милый. Я так рада, что ты написал. Уже успела соскучиться.")
        await state.clear()
    else:
        await message.answer("Привет, как тебя зовут?")
        await state.set_state(ProfileStates.name)

@router.message(Command("reset"))
@handle_api_errors
async def command_reset(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    user_id = message.from_user.id
    await make_api_request(client, "delete", f"/profile/{user_id}")
    await message.answer("Хм, хочешь начать все с чистого листа? Хорошо...")
    await asyncio.sleep(1)
    await message.answer("Давай начнем сначала. Как тебя зовут?")
    await state.set_state(ProfileStates.name)

@router.message(Command("status"))
@handle_api_errors
async def command_status(message: types.Message, client: httpx.AsyncClient):
    user_id = message.from_user.id
    response = await make_api_request(client, "get", f"/profile/status/{user_id}")
    if response.status_code == 200:
        data = response.json()
        if data:
            plan = data['subscription_plan']
            expires = data['subscription_expires']
            count = data['daily_message_count']
            limit = DAILY_MESSAGE_LIMIT
            
            status_text = f"Твой тариф: *{plan.capitalize()}\n"
            if plan == 'premium' and expires:
                status_text += f"Подписка действует до: {expires.split('T')[0]}\n"
            elif plan == 'free':
                status_text += f"Сообщений сегодня: {count}/{limit}\n"
                status_text += "Премиум-пользователи не имеют ограничений по сообщениям и получают доступ к продвинутым функциям!"
            
            await message.answer(status_text, parse_mode='Markdown')
        else:
            await message.answer("Профиль не найден. Пожалуйста, используй /start.")
    else:
        await message.answer("Не удалось получить статус. Попробуй позже.")

@router.message(Command("premium"))
async def command_premium(message: types.Message):
    premium_info = (
        "✨ *Премиум-подписка EvolveAI* ✨\n\n"
        "Разблокируй все возможности общения!\n\n"
        f" Unlimited общение без дневных лимитов (бесплатные пользователи могут отправлять до {DAILY_MESSAGE_LIMIT} сообщений в день).\n"
        " 🧠 Продвинутую память (суммаризация диалогов).\n"
        " 📷 Возможность отправлять фото и получать комментарии.\n"
        " 🎙️ Голосовые сообщения от ИИ-компаньона.\n"
        " 💬 Приоритет в обработке запросов.\n\n"
        "Сейчас эта функция в разработке. Следи за обновлениями!"
    )
    await message.answer(premium_info, parse_mode='Markdown')
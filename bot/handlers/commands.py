import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple

import httpx
from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from config import DAILY_MESSAGE_LIMIT
from ..services.api_client import get_token, make_api_request
from .keyboards import get_profile_keyboard
from .profile import ProfileStates

router = Router()
logger = logging.getLogger(__name__)

# Admin user IDs (можно вынести в config)
ADMIN_USER_IDS = set()  # Добавьте ID администраторов


def calculate_relationship_progress(level: int, score: int) -> Tuple[int, float, str]:
    """
    Рассчитывает прогресс отношений.
    
    Args:
        level: Текущий уровень отношений
        score: Накопленные очки
        
    Returns:
        tuple: (max_score, progress, progress_bar)
    """
    max_score = level * 100
    progress = score / max_score if max_score > 0 else 0
    bar_length = 10
    filled = int(progress * bar_length)
    bar = '█' * filled + '░' * (bar_length - filled)
    return max_score, progress, bar

@router.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext, client: httpx.AsyncClient) -> None:
    """Обработчик команды /start."""
    user_id = message.from_user.id
    response = await make_api_request(client, "get", f"/profile/{user_id}", user_id=user_id)
    data = response.json()
    if data is not None:
        await message.answer("Привет, милый. Я так рада, что ты написал. Уже успела соскучиться.")
        await state.clear()
    else:
        await message.answer("Привет, как тебя зовут?")
        await state.set_state(ProfileStates.name)

@router.message(Command("reset"))
async def command_reset(message: types.Message, state: FSMContext, client: httpx.AsyncClient) -> None:
    """Обработчик команды /reset - сброс профиля."""
    user_id = message.from_user.id
    await make_api_request(client, "delete", f"/profile/{user_id}", user_id=user_id)
    await message.answer("Хм, хочешь начать все с чистого листа? Хорошо...")
    await asyncio.sleep(1)
    await message.answer("Давай начнем сначала. Как тебя зовут?")
    await state.set_state(ProfileStates.name)

@router.message(Command("status"))
async def command_status(message: types.Message, client: httpx.AsyncClient) -> None:
    """Обработчик команды /status - показывает статус подписки."""
    user_id = message.from_user.id
    response = await make_api_request(client, "get", f"/profile/status/{user_id}", user_id=user_id)
    data = response.json()
    
    if not data:
        await message.answer("Профиль не найден. Пожалуйста, используй /start.")
        return
    
    plan = data.get('subscription_plan', 'free')
    expires = data.get('subscription_expires')
    count = data.get('daily_message_count', 0)
    limit = DAILY_MESSAGE_LIMIT
    
    status_text = "*Статус подписки*\n\n"
    
    if plan == 'premium' and expires:
        try:
            exp_date = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            days_left = (exp_date - datetime.now()).days
            
            status_text += "✨ *Премиум подписка*\n"
            status_text += f"Действует до: {expires.split('T')[0]}\n"
            status_text += f"Осталось дней: {max(0, days_left)}\n\n"
            status_text += "💎 *Преимущества:*\n"
            status_text += "• Unlimited сообщений ✅\n"
            status_text += "• Продвинутая память ✅\n"
            status_text += "• Голосовые сообщения ✅\n"
            status_text += "• Доступ к платным уровням ✅"
            
            if days_left <= 7:
                status_text += "\n\n⚠️ Подписка скоро истекает! Продлите для продолжения премиум функций."
        except Exception as e:
            logger.error(f"Error parsing subscription expiry date for user {user_id}: {e}")
            status_text += "✨ *Премиум подписка*\n"
            status_text += f"Действует до: {expires.split('T')[0]}\n"
            status_text += "Unlimited сообщений ✅"
    else:
        status_text += "🆓 *Бесплатный план*\n"
        status_text += f"Сообщений сегодня: {count}/{limit}\n"
        status_text += f"Осталось: {max(0, limit - count)}\n\n"
        
        if count >= limit * 0.8:
            status_text += f"⚠️ Вы использовали {count}/{limit} сообщений!\n"
        
        status_text += "💎 *Премиум включает:*\n"
        status_text += "• Unlimited сообщений\n"
        status_text += "• Продвинутая память\n"
        status_text += "• Голосовые сообщения\n"
        status_text += "• Доступ к платным уровням отношений\n\n"
        status_text += "Используйте /buy_premium для покупки!"
    
    await message.answer(status_text, parse_mode='Markdown')

@router.message(Command("premium"))
async def command_premium(message: types.Message) -> None:
    """Обработчик команды /premium - информация о премиум подписке."""
    premium_info = (
        "✨ *Премиум-подписка EvolveAI* ✨\n\n"
        "Разблокируй все возможности общения!\n\n"
        "*Что включено:*\n"
        f"• Unlimited общение без дневных лимитов (бесплатные пользователи могут отправлять до {DAILY_MESSAGE_LIMIT} сообщений в день)\n"
        "• Продвинутая память и суммаризация диалогов\n"
        "• Голосовые сообщения от ИИ-компаньона\n"
        "• Доступ к платным уровням отношений (8-14)\n"
        "• Приоритетная обработка запросов\n"
        "• Обработка изображений\n\n"
        "*Скидки за длительную подписку:*\n"
        "• 1 месяц: 990₽\n"
        "• 3 месяца: 2490₽ (-16%)\n"
        "• 6 месяцев: 3990₽ (-33%)\n"
        "• 12 месяцев: 6990₽ (-41%)\n\n"
        "Используйте /buy_premium для покупки!"
    )
    await message.answer(premium_info, parse_mode='Markdown')
@router.message(Command("test_premium"))
async def test_premium_command(message: types.Message, client: httpx.AsyncClient) -> None:
    """
    Тестовая активация премиум-подписки на 30 дней.
    ТОЛЬКО ДЛЯ АДМИНИСТРАТОРОВ!
    """
    user_id = message.from_user.id
    
    # Проверка прав администратора
    if ADMIN_USER_IDS and user_id not in ADMIN_USER_IDS:
        logger.warning(f"Unauthorized test_premium attempt from user {user_id}")
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    try:
        # Получаем JWT токен для авторизации
        token = await get_token(client, user_id)
        
        response = await make_api_request(
            client,
            "post",
            "/activate_premium",
            user_id=user_id,
            token=token,
            json={"user_id": user_id, "duration_days": 30}
        )
        
        await message.answer(
            "🎉 Тестовая премиум-подписка активирована на 30 дней!\n\n"
            "Теперь у вас безлимитные сообщения и все преимущества премиум."
        )
        logger.info(f"Test premium activated for user {user_id}")
    except Exception as e:
        logger.error(f"Error activating test premium for user {user_id}: {e}")
        await message.answer("❌ Ошибка активации тестовой подписки.")


@router.message(Command("profile"))
async def command_profile(message: types.Message, client: httpx.AsyncClient) -> None:
    """Обработчик команды /profile - показывает профиль пользователя."""
    user_id = message.from_user.id
    response = await make_api_request(client, "get", f"/profile/{user_id}", user_id=user_id)
    data = response.json()
    
    if not data:
        await message.answer("Профиль не найден. Используйте /start для создания профиля.")
        return
    
    name = data.get('name', 'Не указано')
    level = data.get('relationship_level', 1)
    score = data.get('relationship_score', 0)
    
    max_score, progress, bar = calculate_relationship_progress(level, score)
    
    profile_text = (
        "📋 *Ваш профиль*\n\n"
        f"👤 Имя: {name}\n"
        f"📍 Город: {data.get('city', 'Не указан')}\n"
        f"⏰ Часовой пояс: {data.get('timezone', 'UTC')}\n\n"
        "❤️ *Отношения*\n"
        f"Уровень: {level}\n"
        f"Очки: {score}\n"
        f"Прогресс до следующего: {bar} ({score}/{max_score})"
    )
    
    await message.answer(profile_text, parse_mode='Markdown', reply_markup=get_profile_keyboard())
@router.callback_query(F.data == "back_to_chat")
async def back_to_chat_callback(callback: types.CallbackQuery) -> None:
    """Обработчик кнопки 'Назад в чат'."""
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Вернулись в чат! 😊")


@router.callback_query(F.data == "show_progress")
async def show_progress_callback(callback: types.CallbackQuery, client: httpx.AsyncClient) -> None:
    """Обработчик кнопки 'Показать прогресс отношений'."""
    user_id = callback.from_user.id
    response = await make_api_request(client, "get", f"/profile/{user_id}", user_id=user_id)
    data = response.json()
    
    if not data:
        await callback.answer("Профиль не найден.")
        return
    
    level = data.get('relationship_level', 1)
    score = data.get('relationship_score', 0)
    max_score = level * 100
    progress = score / max_score if max_score > 0 else 0
    bar_length = 20
    filled = int(progress * bar_length)
    bar = '❤️' * filled + '🖤' * (bar_length - filled)
    
    progress_text = (
        "📊 *Детальный прогресс отношений*\n\n"
        f"Текущий уровень: {level}\n"
        f"Накоплено очков: {score}\n"
        f"До следующего уровня: {max_score - score} очков\n\n"
        f"Прогресс:\n{bar}\n"
        f"({int(progress * 100)}%)"
    )
    
    await callback.message.edit_text(progress_text, parse_mode='Markdown')
    await callback.answer()
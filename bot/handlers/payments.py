import logging
import httpx
from aiogram import Router, types, F
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import PAYMENT_PROVIDER_TOKEN
from ..services.api_client import make_api_request, handle_api_errors
from collections import defaultdict
from datetime import datetime, timedelta

router = Router()
logger = logging.getLogger(__name__)

# Цены для разных типов подписок (в копейках)
SUBSCRIPTION_PRICES = {
    "1_month": 99000,    # 990 рублей
    "3_months": 249000,  # 2490 рублей (скидка ~16%)
    "6_months": 399000,  # 3990 рублей (скидка ~33%)
    "12_months": 699000  # 6990 рублей (скидка ~41%)
}

# FSM States для платежей
class PaymentStates(StatesGroup):
    choosing_plan = State()
    pending_payment = State()

# Rate limiting для платежных операций
payment_attempts = defaultdict(list)  # user_id: [timestamp1, timestamp2, ...]
MAX_PAYMENT_ATTEMPTS = 3  # Максимум 3 попытки в час
PAYMENT_RATE_LIMIT_HOURS = 1

def check_payment_rate_limit(user_id: int) -> tuple[bool, int]:
    """
    Проверяет rate limit для платежных операций.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        tuple: (allowed: bool, remaining_attempts: int)
    """
    now = datetime.now()
    time_window = timedelta(hours=PAYMENT_RATE_LIMIT_HOURS)
    
    # Очищаем старые попытки
    payment_attempts[user_id] = [
        t for t in payment_attempts[user_id]
        if now - t < time_window
    ]
    
    current_attempts = len(payment_attempts[user_id])
    remaining = MAX_PAYMENT_ATTEMPTS - current_attempts
    
    return (remaining > 0, remaining)


def record_payment_attempt(user_id: int):
    """Записывает попытку платежа."""
    payment_attempts[user_id].append(datetime.now())


@router.message(Command("buy_premium"))
async def buy_premium_command(message: types.Message, state: FSMContext):
    """Показывает варианты премиум подписки с rate limiting"""
    user_id = message.from_user.id
    
    if not PAYMENT_PROVIDER_TOKEN:
        await message.answer("💳 Платежи временно недоступны. Попробуйте позже.")
        return
    
    # Проверяем rate limit
    allowed, remaining = check_payment_rate_limit(user_id)
    if not allowed:
        logger.warning(f"Payment rate limit exceeded for user {user_id}")
        await message.answer(
            "⚠️ Превышен лимит попыток оплаты.\n"
            f"Попробуйте через {PAYMENT_RATE_LIMIT_HOURS} час(а)."
        )
        return
    
    # Устанавливаем FSM состояние
    await state.set_state(PaymentStates.choosing_plan)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="1 месяц - 990₽", callback_data="buy_1_month"),
            types.InlineKeyboardButton(text="3 месяца - 2490₽", callback_data="buy_3_months")
        ],
        [
            types.InlineKeyboardButton(text="6 месяцев - 3990₽", callback_data="buy_6_months"),
            types.InlineKeyboardButton(text="12 месяцев - 6990₽", callback_data="buy_12_months")
        ],
        [
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")
        ]
    ])
    
    premium_info = (
        "💎 *Выберите тариф премиум подписки*\n\n"
        "✨ *Что включено:*\n"
        "• Unlimited сообщения без ограничений\n"
        "• Продвинутая память и контекст\n"
        "• Голосовые сообщения от ИИ\n"
        "• Приоритетная обработка запросов\n"
        "• Доступ к платным уровням отношений\n"
        "• Обработка изображений\n\n"
        "🎁 *Скидки за длительную подписку!*"
    )
    
    await message.answer(premium_info, reply_markup=keyboard, parse_mode='MarkdownV2')

@router.callback_query(F.data.startswith("buy_"))
async def handle_subscription_choice(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора тарифа подписки с валидацией"""
    user_id = callback.from_user.id
    
    if not PAYMENT_PROVIDER_TOKEN:
        await callback.answer("Платежи временно недоступны", show_alert=True)
        return
    
    # Проверяем, что пользователь в правильном состоянии
    current_state = await state.get_state()
    if current_state != PaymentStates.choosing_plan:
        logger.warning(f"Invalid state for payment callback from user {user_id}: {current_state}")
        await callback.answer("Ошибка: неверное состояние. Начните заново с /buy_premium", show_alert=True)
        return
    
    subscription_type = callback.data.replace("buy_", "")
    
    # Валидация subscription_type
    valid_types = ["1_month", "3_months", "6_months", "12_months"]
    if subscription_type not in valid_types:
        logger.error(f"Invalid subscription type from user {user_id}: {subscription_type}")
        await callback.answer("Ошибка: неверный тип подписки", show_alert=True)
        return
    
    duration_days = {
        "1_month": 30,
        "3_months": 90,
        "6_months": 180,
        "12_months": 365
    }
    
    price = SUBSCRIPTION_PRICES[subscription_type]
    days = duration_days[subscription_type]
    
    # Записываем попытку платежа
    record_payment_attempt(user_id)
    
    # Переходим в состояние ожидания платежа
    await state.set_state(PaymentStates.pending_payment)
    await state.update_data(subscription_type=subscription_type, price=price, days=days)
    
    # Формируем описание
    description = f"Премиум подписка EvolveAI на {days} дней"
    
    # Создаем инвойс
    try:
        await callback.bot.send_invoice(
            chat_id=callback.message.chat.id,
            title="💎 Премиум подписка EvolveAI",
            description=description,
            payload=f"premium_{subscription_type}_{user_id}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=f"Премиум подписка ({days} дней)", amount=price)],
            start_parameter="premium_subscription",
            photo_url="https://via.placeholder.com/400x200/6C5CE7/FFFFFF?text=Premium+EvolveAI",
            photo_width=400,
            photo_height=200
        )
        
        logger.info(f"Invoice created for user {user_id}: {subscription_type}, {price} RUB")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error creating invoice for user {user_id}: {e}", exc_info=True)
        await callback.answer("Ошибка создания инвойса. Попробуйте позже.", show_alert=True)
        await state.clear()

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    """Отмена покупки"""
    await state.clear()
    await callback.message.edit_text("❌ Покупка отменена")
    await callback.answer()
    logger.info(f"Payment cancelled by user {callback.from_user.id}")

@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    """
    Подтверждение платежа с валидацией payload.
    Это последний шанс отклонить платеж до его проведения.
    """
    user_id = pre_checkout_query.from_user.id
    payload = pre_checkout_query.invoice_payload
    
    logger.info(f"Pre-checkout query from user {user_id}: {payload}")
    
    # Валидация формата payload
    try:
        parts = payload.split("_")
        if len(parts) != 3:
            raise ValueError(f"Invalid payload format: expected 3 parts, got {len(parts)}")
        
        prefix, subscription_type, user_id_from_payload = parts
        
        # Проверка префикса
        if prefix != "premium":
            raise ValueError(f"Invalid payload prefix: {prefix}")
        
        # Проверка subscription type
        valid_types = ["1month", "3months", "6months", "12months"]
        if subscription_type not in valid_types:
            raise ValueError(f"Invalid subscription type: {subscription_type}")
        
        # Проверка user_id
        user_id_from_payload = int(user_id_from_payload)
        if user_id_from_payload != user_id:
            logger.warning(
                f"SECURITY: Payload user_id mismatch! "
                f"Authenticated: {user_id}, Payload: {user_id_from_payload}"
            )
            await pre_checkout_query.answer(
                ok=False,
                error_message="Ошибка безопасности: несоответствие пользователя"
            )
            return
        
        # Проверка цены (защита от манипуляций)
        expected_price = SUBSCRIPTION_PRICES.get(subscription_type.replace("month", "_month"))
        if expected_price and pre_checkout_query.total_amount != expected_price:
            logger.error(
                f"SECURITY: Price mismatch for user {user_id}! "
                f"Expected: {expected_price}, Got: {pre_checkout_query.total_amount}"
            )
            await pre_checkout_query.answer(
                ok=False,
                error_message="Ошибка: несоответствие цены"
            )
            return
        
        # Все проверки пройдены
        logger.info(f"Pre-checkout validation passed for user {user_id}")
        await pre_checkout_query.answer(ok=True)
        
    except (ValueError, IndexError) as e:
        logger.error(f"Invalid payment payload from user {user_id}: {payload}, error: {e}")
        await pre_checkout_query.answer(
            ok=False,
            error_message="Ошибка валидации платежа. Попробуйте создать новый инвойс."
        )
    except Exception as e:
        logger.error(f"Unexpected error in pre_checkout for user {user_id}: {e}", exc_info=True)
        await pre_checkout_query.answer(
            ok=False,
            error_message="Внутренняя ошибка. Обратитесь в поддержку."
        )

@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message, client: httpx.AsyncClient, state: FSMContext):
    """Обработка успешного платежа с детальным логированием"""
    payment = message.successful_payment
    user_id = message.from_user.id
    
    # AUDIT LOG: Детальное логирование успешной транзакции
    logger.info(
        f"PAYMENT_SUCCESS: user_id={user_id}, "
        f"amount={payment.total_amount}, "
        f"currency={payment.currency}, "
        f"charge_id={payment.telegram_payment_charge_id}, "
        f"payload={payment.invoice_payload}, "
        f"provider_charge_id={payment.provider_payment_charge_id}"
    )
    
    # Извлекаем тип подписки из payload
    try:
        payload_parts = payment.invoice_payload.split("_", 2)
        subscription_type = payload_parts[1]  # "1_month", "3_months", etc.
    except Exception as e:
        logger.error(f"Failed to parse payload for user {user_id}: {payment.invoice_payload}, error: {e}")
        await message.answer(
            "❌ Ошибка обработки платежа. "
            f"Обратитесь в поддержку с номером транзакции: {payment.telegram_payment_charge_id}"
        )
        await state.clear()
        return
    
    duration_days = {
        "1_month": 30,
        "3_months": 90,
        "6_months": 180,
        "12_months": 365
    }
    
    days = duration_days.get(subscription_type)
    if not days:
        logger.error(f"Invalid subscription type in successful payment: {subscription_type}")
        await message.answer(
            "❌ Ошибка: неверный тип подписки. "
            f"Обратитесь в поддержку с номером транзакции: {payment.telegram_payment_charge_id}"
        )
        await state.clear()
        return
    
    try:
        # Получаем JWT токен для безопасного вызова API
        from ..services.api_client import get_token
        token = await get_token(client, user_id)
        
        # Активируем подписку через API с JWT авторизацией
        response = await make_api_request(
            client,
            "post",
            "/activate_premium",
            user_id=user_id,
            token=token,
            json={
                "user_id": user_id,
                "duration_days": days,
                "charge_id": payment.telegram_payment_charge_id
            }
        )
        
        if response.status_code == 200:
            success_message = (
                f"🎉 *Поздравляем!*\n\n"
                f"✨ Премиум подписка активирована на {days} дней!\n\n"
                f"💎 Теперь у вас есть:\n"
                f"• Unlimited сообщения\n"
                f"• Продвинутая память\n"
                f"• Голосовые сообщения\n"
                f"• Доступ к платным уровням отношений\n\n"
                f"Спасибо за поддержку! ❤️"
            )
            
            await message.answer(success_message, parse_mode='MarkdownV2')
            
            # AUDIT LOG: Успешная активация
            logger.info(f"Premium activated successfully for user {user_id}, duration: {days} days")
            
            # Очищаем FSM состояние
            await state.clear()
            
        else:
            # AUDIT LOG: Ошибка активации
            logger.error(
                f"Premium activation failed for user {user_id}: "
                f"status={response.status_code}, response={response.text}"
            )
            await message.answer(
                "❌ Произошла ошибка при активации подписки. "
                f"Обратитесь в поддержку с номером транзакции: {payment.telegram_payment_charge_id}"
            )
            
    except Exception as e:
        # AUDIT LOG: Критическая ошибка
        logger.error(
            f"Critical error processing payment for user {user_id}: {e}, "
            f"charge_id={payment.telegram_payment_charge_id}",
            exc_info=True
        )
        await message.answer(
            "❌ Критическая ошибка обработки платежа. "
            f"Обратитесь в поддержку с номером транзакции: {payment.telegram_payment_charge_id}"
        )
    finally:
        # Всегда очищаем состояние после обработки платежа
        await state.clear()
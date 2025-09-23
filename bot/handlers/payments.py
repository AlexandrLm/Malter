import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from config import PAYMENT_PROVIDER_TOKEN
from ..services.api_client import make_api_request, handle_api_errors

router = Router()
logger = logging.getLogger(__name__)

# Цены для разных типов подписок (в копейках)
SUBSCRIPTION_PRICES = {
    "1_month": 99000,    # 990 рублей
    "3_months": 249000,  # 2490 рублей (скидка ~16%)
    "6_months": 399000,  # 3990 рублей (скидка ~33%)
    "12_months": 699000  # 6990 рублей (скидка ~41%)
}

@router.message(Command("buy_premium"))
@handle_api_errors
async def buy_premium_command(message: types.Message):
    """Показывает варианты премиум подписки"""
    if not PAYMENT_PROVIDER_TOKEN:
        await message.answer("💳 Платежи временно недоступны. Попробуйте позже.")
        return
    
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
    
    await message.answer(premium_info, reply_markup=keyboard, parse_mode='Markdown')

@router.callback_query(F.data.startswith("buy_"))
async def handle_subscription_choice(callback: types.CallbackQuery):
    """Обработка выбора тарифа подписки"""
    if not PAYMENT_PROVIDER_TOKEN:
        await callback.answer("Платежи временно недоступны", show_alert=True)
        return
    
    subscription_type = callback.data.replace("buy_", "")
    duration_days = {
        "1_month": 30,
        "3_months": 90,
        "6_months": 180,
        "12_months": 365
    }
    
    price = SUBSCRIPTION_PRICES[subscription_type]
    days = duration_days[subscription_type]
    
    # Формируем описание
    description = f"Премиум подписка EvolveAI на {days} дней"
    
    # Создаем инвойс
    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="💎 Премиум подписка EvolveAI",
        description=description,
        payload=f"premium_{subscription_type}_{callback.from_user.id}",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=f"Премиум подписка ({days} дней)", amount=price)],
        start_parameter="premium_subscription",
        photo_url="https://via.placeholder.com/400x200/6C5CE7/FFFFFF?text=Premium+EvolveAI",
        photo_width=400,
        photo_height=200
    )
    
    await callback.answer()

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery):
    """Отмена покупки"""
    await callback.message.edit_text("❌ Покупка отменена")
    await callback.answer()

@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение платежа"""
    # Здесь можно добавить дополнительную валидацию
    logger.info(f"Pre-checkout query from user {pre_checkout_query.from_user.id}: {pre_checkout_query.invoice_payload}")
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    """Обработка успешного платежа"""
    payment = message.successful_payment
    user_id = message.from_user.id
    
    try:
        # Извлекаем тип подписки из payload
        payload_parts = payment.invoice_payload.split("_")
        subscription_type = payload_parts[1] + "_" + payload_parts[2]  # "1_month", "3_months", etc.
        
        duration_days = {
            "1_month": 30,
            "3_months": 90,
            "6_months": 180,
            "12_months": 365
        }
        
        days = duration_days[subscription_type]
        
        # Активируем подписку через API
        response = await make_api_request(
            message.bot.get("httpx_client"),
            "post",
            "/activate_premium",
            json={"user_id": user_id, "duration_days": days}
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
            
            await message.answer(success_message, parse_mode='Markdown')
            
            # Логируем успешную покупку
            logger.info(f"Успешная покупка премиум подписки пользователем {user_id} на {days} дней")
            
        else:
            await message.answer(
                "❌ Произошла ошибка при активации подписки. "
                "Обратитесь в поддержку с номером транзакции: " + payment.telegram_payment_charge_id
            )
            
    except Exception as e:
        logger.error(f"Ошибка обработки платежа для пользователя {user_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке платежа. "
            "Обратитесь в поддержку с номером транзакции: " + payment.telegram_payment_charge_id
        )
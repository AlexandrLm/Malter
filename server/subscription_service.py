"""
Сервис для управления подписками и проверки лимитов.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from server.database import get_profile, create_or_update_profile, check_subscription_expiry

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Сервис для работы с подписками"""
    
    @staticmethod
    async def get_subscription_info(user_id: int) -> Dict[str, Any]:
        """
        Получает полную информацию о подписке пользователя.
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            Dict[str, Any]: Информация о подписке
        """
        profile = await get_profile(user_id)
        if not profile:
            return {
                "plan": "none",
                "expires": None,
                "is_active": False,
                "days_left": 0,
                "daily_count": 0,
                "daily_limit": 50
            }
        
        # Проверяем истечение подписки
        await check_subscription_expiry(user_id)
        profile = await get_profile(user_id)  # Обновляем профиль
        
        is_premium = (profile.subscription_plan == 'premium' and 
                     profile.subscription_expires and 
                     profile.subscription_expires > datetime.now(timezone.utc))
        
        days_left = 0
        if is_premium and profile.subscription_expires:
            days_left = max(0, (profile.subscription_expires - datetime.now(timezone.utc)).days)
        
        return {
            "plan": profile.subscription_plan,
            "expires": profile.subscription_expires.isoformat() if profile.subscription_expires else None,
            "is_active": is_premium,
            "days_left": days_left,
            "daily_count": profile.daily_message_count,
            "daily_limit": 50 if not is_premium else 0
        }
    
    @staticmethod
    async def can_send_message(user_id: int) -> Dict[str, Any]:
        """
        Проверяет, может ли пользователь отправить сообщение.
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            Dict[str, Any]: Результат проверки
        """
        from config import DAILY_MESSAGE_LIMIT
        
        profile = await get_profile(user_id)
        if not profile:
            return {
                "allowed": False,
                "reason": "profile_not_found",
                "message": "Профиль не найден. Используйте /start для создания профиля."
            }
        
        # Проверяем истечение подписки
        await check_subscription_expiry(user_id)
        profile = await get_profile(user_id)
        
        # Премиум пользователи не имеют ограничений
        if (profile.subscription_plan == 'premium' and 
            profile.subscription_expires and 
            profile.subscription_expires > datetime.now(timezone.utc)):
            return {
                "allowed": True,
                "reason": "premium_active",
                "message": "premium",
                "subscription_info": await SubscriptionService.get_subscription_info(user_id)
            }
        
        # Проверяем лимит для бесплатных пользователей
        if profile.daily_message_count >= DAILY_MESSAGE_LIMIT:
            return {
                "allowed": False,
                "reason": "daily_limit_exceeded",
                "message": f"Достигнут дневной лимит сообщений ({DAILY_MESSAGE_LIMIT}). Купите премиум для безлимитного общения!",
                "count": profile.daily_message_count,
                "limit": DAILY_MESSAGE_LIMIT
            }
        
        return {
            "allowed": True,
            "reason": "within_limit",
            "message": "ok",
            "count": profile.daily_message_count,
            "limit": DAILY_MESSAGE_LIMIT
        }
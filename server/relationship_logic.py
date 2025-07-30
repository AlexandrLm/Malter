# -*- coding: utf-8 -*-
from datetime import datetime
from server.database import get_profile, create_or_update_profile
from server.relationship_config import RELATIONSHIP_LEVELS_CONFIG

async def check_for_level_up(user_id: int) -> str | None:
    """
    Проверяет, достиг ли пользователь нового уровня отношений.
    Если да, обновляет профиль и возвращает имя нового уровня.
    """
    profile = await get_profile(user_id)
    if not profile:
        return None

    current_level = profile.relationship_level
    if current_level >= max(RELATIONSHIP_LEVELS_CONFIG.keys()):
        return None  # Пользователь уже на максимальном уровне

    next_level = current_level + 1
    next_level_config = RELATIONSHIP_LEVELS_CONFIG[next_level]
    current_level_config = RELATIONSHIP_LEVELS_CONFIG[current_level]

    # Проверка критериев для повышения уровня
    if next_level_config['is_paid'] and not profile.has_subscription:
        return "offer_subscription" # Предложить подписку

    if profile.relationship_score < next_level_config['min_score']:
        return None

    if (datetime.now() - profile.level_unlocked_at).days < current_level_config['min_days']:
        return None

    # Повышение уровня
    await create_or_update_profile(user_id, {
        "relationship_level": next_level,
        "level_unlocked_at": datetime.now()
    })

    return next_level_config['name']
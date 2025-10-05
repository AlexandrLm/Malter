"""
Модуль для аналитики и статистики использования бота.

Предоставляет функции для сбора и анализа данных о пользователях,
сообщениях, подписках и использовании функций.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import async_session_factory
from server.models import UserProfile, ChatHistory, LongTermMemory, ChatSummary
from utils.cache import cached

logger = logging.getLogger(__name__)


@cached(prefix="analytics_overview", ttl=300)  # Кэш на 5 минут
async def get_overview_stats() -> dict[str, Any]:
    """
    Получает общую статистику использования бота.
    
    Returns:
        dict: Общая статистика (пользователи, сообщения, подписки)
    """
    try:
        async with async_session_factory() as session:
            # Общее количество пользователей
            total_users_query = select(func.count(UserProfile.user_id))
            total_users = await session.scalar(total_users_query)
            
            # Активные пользователи (писали за последние 7 дней)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            active_users_query = select(func.count(func.distinct(ChatHistory.user_id))).where(
                ChatHistory.timestamp >= week_ago
            )
            active_users_7d = await session.scalar(active_users_query)
            
            # Активные пользователи за последние 24 часа (DAU)
            day_ago = datetime.now(timezone.utc) - timedelta(days=1)
            dau_query = select(func.count(func.distinct(ChatHistory.user_id))).where(
                ChatHistory.timestamp >= day_ago
            )
            dau = await session.scalar(dau_query)
            
            # Premium пользователи
            premium_query = select(func.count(UserProfile.user_id)).where(
                UserProfile.subscription_plan == 'premium',
                or_(
                    UserProfile.subscription_expires == None,
                    UserProfile.subscription_expires > datetime.now(timezone.utc)
                )
            )
            premium_users = await session.scalar(premium_query)
            
            # Общее количество сообщений
            total_messages_query = select(func.count(ChatHistory.id))
            total_messages = await session.scalar(total_messages_query)
            
            # Сообщения за последние 24 часа
            messages_24h_query = select(func.count(ChatHistory.id)).where(
                ChatHistory.timestamp >= day_ago
            )
            messages_24h = await session.scalar(messages_24h_query)
            
            # Средний уровень отношений
            avg_level_query = select(func.avg(UserProfile.relationship_level))
            avg_level = await session.scalar(avg_level_query) or 1
            
            # Конверсия в premium (%)
            conversion_rate = (premium_users / total_users * 100) if total_users > 0 else 0
            
            return {
                "users": {
                    "total": total_users or 0,
                    "active_7d": active_users_7d or 0,
                    "dau": dau or 0,
                    "premium": premium_users or 0,
                    "conversion_rate": round(conversion_rate, 2)
                },
                "messages": {
                    "total": total_messages or 0,
                    "last_24h": messages_24h or 0,
                    "avg_per_user": round(total_messages / total_users, 2) if total_users > 0 else 0
                },
                "engagement": {
                    "avg_relationship_level": round(float(avg_level), 2),
                    "retention_7d": round(active_users_7d / total_users * 100, 2) if total_users > 0 else 0
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Ошибка при получении общей статистики: {e}", exc_info=True)
        return {"error": str(e)}


@cached(prefix="analytics_users", ttl=300)
async def get_users_stats() -> dict[str, Any]:
    """
    Получает детальную статистику о пользователях.
    
    Returns:
        dict: Статистика пользователей (по уровням, активности, регионам)
    """
    try:
        async with async_session_factory() as session:
            # Распределение по уровням отношений
            levels_query = select(
                UserProfile.relationship_level,
                func.count(UserProfile.user_id).label('count')
            ).group_by(UserProfile.relationship_level).order_by(UserProfile.relationship_level)
            
            levels_result = await session.execute(levels_query)
            levels_distribution = {
                f"level_{row.relationship_level}": row.count 
                for row in levels_result
            }
            
            # Распределение по подпискам
            subscription_query = select(
                UserProfile.subscription_plan,
                func.count(UserProfile.user_id).label('count')
            ).group_by(UserProfile.subscription_plan)
            
            subscription_result = await session.execute(subscription_query)
            subscription_distribution = {
                row.subscription_plan: row.count 
                for row in subscription_result
            }
            
            # Топ пользователей по количеству сообщений
            top_users_query = select(
                ChatHistory.user_id,
                func.count(ChatHistory.id).label('message_count')
            ).group_by(ChatHistory.user_id).order_by(
                func.count(ChatHistory.id).desc()
            ).limit(10)
            
            top_users_result = await session.execute(top_users_query)
            top_users = [
                {"user_id": row.user_id, "messages": row.message_count}
                for row in top_users_result
            ]
            
            # Новые пользователи за последние 7 дней
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            new_users_query = select(func.count(UserProfile.user_id)).where(
                UserProfile.created_at >= week_ago
            )
            new_users_7d = await session.scalar(new_users_query) or 0
            
            # Пользователи с долговременной памятью
            users_with_memory_query = select(
                func.count(func.distinct(LongTermMemory.user_id))
            )
            users_with_memory = await session.scalar(users_with_memory_query) or 0
            
            return {
                "levels_distribution": levels_distribution,
                "subscription_distribution": subscription_distribution,
                "top_users": top_users,
                "new_users_7d": new_users_7d,
                "users_with_memory": users_with_memory,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Ошибка при получении статистики пользователей: {e}", exc_info=True)
        return {"error": str(e)}


@cached(prefix="analytics_messages", ttl=300)
async def get_messages_stats(days: int = 7) -> dict[str, Any]:
    """
    Получает статистику сообщений.
    
    Args:
        days: Количество дней для анализа
        
    Returns:
        dict: Статистика сообщений (по времени, типам, длине)
    """
    try:
        async with async_session_factory() as session:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Сообщения по дням
            messages_by_day_query = select(
                func.date(ChatHistory.timestamp).label('date'),
                func.count(ChatHistory.id).label('count')
            ).where(
                ChatHistory.timestamp >= start_date
            ).group_by(func.date(ChatHistory.timestamp)).order_by(func.date(ChatHistory.timestamp))
            
            messages_by_day_result = await session.execute(messages_by_day_query)
            messages_by_day = {
                str(row.date): row.count
                for row in messages_by_day_result
            }
            
            # Сообщения по часам (для понимания пиковой нагрузки)
            messages_by_hour_query = select(
                func.extract('hour', ChatHistory.timestamp).label('hour'),
                func.count(ChatHistory.id).label('count')
            ).where(
                ChatHistory.timestamp >= start_date
            ).group_by(func.extract('hour', ChatHistory.timestamp)).order_by(func.extract('hour', ChatHistory.timestamp))
            
            messages_by_hour_result = await session.execute(messages_by_hour_query)
            messages_by_hour = {
                int(row.hour): row.count
                for row in messages_by_hour_result
            }
            
            # Соотношение user/model сообщений
            role_distribution_query = select(
                ChatHistory.role,
                func.count(ChatHistory.id).label('count')
            ).where(
                ChatHistory.timestamp >= start_date
            ).group_by(ChatHistory.role)
            
            role_distribution_result = await session.execute(role_distribution_query)
            role_distribution = {
                row.role: row.count
                for row in role_distribution_result
            }
            
            # Средняя длина сообщений
            avg_length_query = select(
                func.avg(func.length(ChatHistory.content)).label('avg_length')
            ).where(
                ChatHistory.timestamp >= start_date,
                ChatHistory.role == 'user'
            )
            avg_user_message_length = await session.scalar(avg_length_query) or 0
            
            # Общее количество за период
            total_messages_query = select(func.count(ChatHistory.id)).where(
                ChatHistory.timestamp >= start_date
            )
            total_messages = await session.scalar(total_messages_query) or 0
            
            return {
                "period_days": days,
                "total_messages": total_messages,
                "messages_by_day": messages_by_day,
                "messages_by_hour": messages_by_hour,
                "role_distribution": role_distribution,
                "avg_user_message_length": round(float(avg_user_message_length), 2),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Ошибка при получении статистики сообщений: {e}", exc_info=True)
        return {"error": str(e)}


@cached(prefix="analytics_revenue", ttl=600)  # Кэш на 10 минут
async def get_revenue_stats() -> dict[str, Any]:
    """
    Получает статистику по подпискам и доходам.
    
    Returns:
        dict: Статистика подписок (активные, истекшие, прогноз)
    """
    try:
        async with async_session_factory() as session:
            now = datetime.now(timezone.utc)
            
            # Активные premium подписки
            active_premium_query = select(func.count(UserProfile.user_id)).where(
                UserProfile.subscription_plan == 'premium',
                or_(
                    UserProfile.subscription_expires == None,
                    UserProfile.subscription_expires > now
                )
            )
            active_premium = await session.scalar(active_premium_query) or 0
            
            # Подписки, истекающие в течение 7 дней
            week_later = now + timedelta(days=7)
            expiring_soon_query = select(func.count(UserProfile.user_id)).where(
                UserProfile.subscription_plan == 'premium',
                UserProfile.subscription_expires != None,
                UserProfile.subscription_expires > now,
                UserProfile.subscription_expires <= week_later
            )
            expiring_soon = await session.scalar(expiring_soon_query) or 0
            
            # Истекшие подписки за последний месяц (потенциально можно вернуть)
            month_ago = now - timedelta(days=30)
            expired_month_query = select(func.count(UserProfile.user_id)).where(
                UserProfile.subscription_plan == 'free',
                UserProfile.subscription_expires != None,
                UserProfile.subscription_expires < now,
                UserProfile.subscription_expires > month_ago
            )
            expired_last_month = await session.scalar(expired_month_query) or 0
            
            # Новые подписки за последние 7 дней
            # (пользователи с premium подпиской, созданной недавно)
            week_ago = now - timedelta(days=7)
            new_subscriptions_query = select(func.count(UserProfile.user_id)).where(
                UserProfile.subscription_plan == 'premium',
                UserProfile.created_at >= week_ago
            )
            new_subscriptions_7d = await session.scalar(new_subscriptions_query) or 0
            
            # Средняя продолжительность подписки (для активных)
            avg_subscription_days_query = select(
                func.avg(
                    func.extract('epoch', UserProfile.subscription_expires - UserProfile.created_at) / 86400
                )
            ).where(
                UserProfile.subscription_plan == 'premium',
                UserProfile.subscription_expires != None,
                UserProfile.subscription_expires > now
            )
            avg_subscription_days = await session.scalar(avg_subscription_days_query) or 0
            
            # MRR (Monthly Recurring Revenue) - примерный расчет
            # Предполагаем среднюю цену подписки (можно вынести в конфиг)
            avg_subscription_price = 299  # рублей/месяц
            mrr = active_premium * avg_subscription_price
            
            # Churn rate (процент отказов)
            total_had_premium = active_premium + expired_last_month
            churn_rate = (expired_last_month / total_had_premium * 100) if total_had_premium > 0 else 0
            
            return {
                "active_subscriptions": active_premium,
                "new_subscriptions_7d": new_subscriptions_7d,
                "expiring_soon_7d": expiring_soon,
                "expired_last_month": expired_last_month,
                "avg_subscription_days": round(float(avg_subscription_days), 2),
                "revenue": {
                    "mrr": mrr,
                    "currency": "RUB",
                    "projected_arr": mrr * 12
                },
                "metrics": {
                    "churn_rate": round(churn_rate, 2),
                    "retention_rate": round(100 - churn_rate, 2)
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Ошибка при получении статистики подписок: {e}", exc_info=True)
        return {"error": str(e)}


async def get_feature_usage_stats() -> dict[str, Any]:
    """
    Получает статистику использования функций бота.
    
    Returns:
        dict: Статистика использования функций (memory, images, voice)
    """
    try:
        async with async_session_factory() as session:
            # Использование долговременной памяти
            total_memories_query = select(func.count(LongTermMemory.id))
            total_memories = await session.scalar(total_memories_query) or 0
            
            users_using_memory_query = select(
                func.count(func.distinct(LongTermMemory.user_id))
            )
            users_using_memory = await session.scalar(users_using_memory_query) or 0
            
            # Память по категориям
            memory_by_category_query = select(
                LongTermMemory.category,
                func.count(LongTermMemory.id).label('count')
            ).group_by(LongTermMemory.category)
            
            memory_by_category_result = await session.execute(memory_by_category_query)
            memory_by_category = {
                row.category: row.count
                for row in memory_by_category_result
            }
            
            # Количество сводок (показатель длинных диалогов)
            total_summaries_query = select(func.count(ChatSummary.user_id))
            total_summaries = await session.scalar(total_summaries_query) or 0
            
            return {
                "memory": {
                    "total_facts": total_memories,
                    "users_using": users_using_memory,
                    "by_category": memory_by_category
                },
                "summaries": {
                    "total": total_summaries
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Ошибка при получении статистики функций: {e}", exc_info=True)
        return {"error": str(e)}


@cached(prefix="analytics_cohort", ttl=600)
async def get_cohort_analysis(days: int = 30) -> dict[str, Any]:
    """
    Когортный анализ - retention пользователей по датам регистрации.
    
    Args:
        days: Количество дней для анализа
        
    Returns:
        dict: Retention по когортам (день регистрации → активность)
    """
    try:
        async with async_session_factory() as session:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Получаем пользователей по датам регистрации
            cohorts_query = select(
                func.date(UserProfile.created_at).label('cohort_date'),
                func.count(UserProfile.user_id).label('users_count')
            ).where(
                UserProfile.created_at >= start_date
            ).group_by(func.date(UserProfile.created_at)).order_by(func.date(UserProfile.created_at))
            
            cohorts_result = await session.execute(cohorts_query)
            cohorts = {str(row.cohort_date): row.users_count for row in cohorts_result}
            
            # Для каждой когорты считаем retention (активность через N дней)
            cohort_retention = {}
            
            for cohort_date_str, cohort_size in cohorts.items():
                cohort_date = datetime.fromisoformat(cohort_date_str).replace(tzinfo=timezone.utc)
                
                # День 1 retention (активны на следующий день)
                day1_end = cohort_date + timedelta(days=2)
                day1_query = select(func.count(func.distinct(ChatHistory.user_id))).select_from(
                    UserProfile
                ).join(
                    ChatHistory, UserProfile.user_id == ChatHistory.user_id
                ).where(
                    func.date(UserProfile.created_at) == cohort_date.date(),
                    ChatHistory.timestamp >= cohort_date + timedelta(days=1),
                    ChatHistory.timestamp < day1_end
                )
                day1_active = await session.scalar(day1_query) or 0
                
                # День 7 retention
                day7_start = cohort_date + timedelta(days=7)
                day7_end = cohort_date + timedelta(days=8)
                day7_query = select(func.count(func.distinct(ChatHistory.user_id))).select_from(
                    UserProfile
                ).join(
                    ChatHistory, UserProfile.user_id == ChatHistory.user_id
                ).where(
                    func.date(UserProfile.created_at) == cohort_date.date(),
                    ChatHistory.timestamp >= day7_start,
                    ChatHistory.timestamp < day7_end
                )
                day7_active = await session.scalar(day7_query) or 0
                
                cohort_retention[cohort_date_str] = {
                    "cohort_size": cohort_size,
                    "day_1_active": day1_active,
                    "day_1_retention": round(day1_active / cohort_size * 100, 2) if cohort_size > 0 else 0,
                    "day_7_active": day7_active,
                    "day_7_retention": round(day7_active / cohort_size * 100, 2) if cohort_size > 0 else 0
                }
            
            # Средний retention
            avg_day1 = sum(c["day_1_retention"] for c in cohort_retention.values()) / len(cohort_retention) if cohort_retention else 0
            avg_day7 = sum(c["day_7_retention"] for c in cohort_retention.values()) / len(cohort_retention) if cohort_retention else 0
            
            return {
                "period_days": days,
                "cohorts": cohort_retention,
                "average_retention": {
                    "day_1": round(avg_day1, 2),
                    "day_7": round(avg_day7, 2)
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Ошибка при когортном анализе: {e}", exc_info=True)
        return {"error": str(e)}


@cached(prefix="analytics_funnel", ttl=300)
async def get_funnel_analysis() -> dict[str, Any]:
    """
    Funnel analysis - как пользователи проходят через уровни отношений.
    
    Returns:
        dict: Количество пользователей на каждом уровне и conversion rates
    """
    try:
        async with async_session_factory() as session:
            # Количество пользователей на каждом уровне
            levels_query = select(
                UserProfile.relationship_level,
                func.count(UserProfile.user_id).label('count')
            ).group_by(UserProfile.relationship_level).order_by(UserProfile.relationship_level)
            
            levels_result = await session.execute(levels_query)
            levels_data = {row.relationship_level: row.count for row in levels_result}
            
            # Рассчитываем conversion rates (% от предыдущего уровня)
            funnel = {}
            prev_count = None
            
            for level in range(1, 15):  # 14 уровней
                count = levels_data.get(level, 0)
                
                funnel[f"level_{level}"] = {
                    "users": count,
                    "conversion_from_previous": round(count / prev_count * 100, 2) if prev_count else 100,
                    "conversion_from_start": round(count / levels_data.get(1, 1) * 100, 2)
                }
                
                prev_count = count if count > 0 else prev_count
            
            # Находим bottleneck (самый большой drop-off)
            max_dropoff_level = None
            max_dropoff_rate = 0
            
            for level in range(2, 15):
                dropoff = 100 - funnel[f"level_{level}"]["conversion_from_previous"]
                if dropoff > max_dropoff_rate:
                    max_dropoff_rate = dropoff
                    max_dropoff_level = level
            
            # Средний уровень, до которого доходят
            total_users = sum(levels_data.values())
            weighted_avg = sum(level * count for level, count in levels_data.items()) / total_users if total_users > 0 else 0
            
            return {
                "funnel": funnel,
                "insights": {
                    "total_users": total_users,
                    "avg_level_reached": round(weighted_avg, 2),
                    "bottleneck_level": max_dropoff_level,
                    "bottleneck_dropoff": round(max_dropoff_rate, 2),
                    "level_14_conversion": funnel["level_14"]["conversion_from_start"]
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Ошибка при funnel analysis: {e}", exc_info=True)
        return {"error": str(e)}


@cached(prefix="analytics_activity", ttl=300)
async def get_activity_patterns() -> dict[str, Any]:
    """
    Паттерны активности - по дням недели, времени суток.
    
    Returns:
        dict: Активность по дням недели, часам, средняя длина сессии
    """
    try:
        async with async_session_factory() as session:
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            
            # Активность по дням недели (0=Monday, 6=Sunday)
            by_weekday_query = select(
                func.extract('dow', ChatHistory.timestamp).label('weekday'),
                func.count(ChatHistory.id).label('messages'),
                func.count(func.distinct(ChatHistory.user_id)).label('users')
            ).where(
                ChatHistory.timestamp >= week_ago
            ).group_by(func.extract('dow', ChatHistory.timestamp)).order_by(func.extract('dow', ChatHistory.timestamp))
            
            by_weekday_result = await session.execute(by_weekday_query)
            
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            by_weekday = {}
            
            for row in by_weekday_result:
                weekday_idx = int(row.weekday)
                by_weekday[weekday_names[weekday_idx]] = {
                    "messages": row.messages,
                    "active_users": row.users,
                    "avg_messages_per_user": round(row.messages / row.users, 2) if row.users > 0 else 0
                }
            
            # Пиковые и медленные часы
            by_hour_query = select(
                func.extract('hour', ChatHistory.timestamp).label('hour'),
                func.count(ChatHistory.id).label('count')
            ).where(
                ChatHistory.timestamp >= week_ago
            ).group_by(func.extract('hour', ChatHistory.timestamp)).order_by(func.count(ChatHistory.id).desc())
            
            by_hour_result = await session.execute(by_hour_query)
            hour_data = [(int(row.hour), row.count) for row in by_hour_result]
            
            peak_hour = hour_data[0][0] if hour_data else 0
            slowest_hour = hour_data[-1][0] if hour_data else 0
            
            # Средняя длина сессии (время между первым и последним сообщением в день)
            # Упрощенный подсчет через подзапросы
            avg_session_query = select(
                func.avg(
                    func.extract('epoch',
                        func.max(ChatHistory.timestamp) - func.min(ChatHistory.timestamp)
                    ) / 60  # в минутах
                ).label('avg_session_minutes')
            ).select_from(ChatHistory).where(
                ChatHistory.timestamp >= week_ago
            ).group_by(
                ChatHistory.user_id,
                func.date(ChatHistory.timestamp)
            )
            
            # Это подзапрос, нужно обернуть
            subquery = avg_session_query.subquery()
            final_avg = await session.scalar(select(func.avg(subquery.c.avg_session_minutes)))
            avg_session_minutes = float(final_avg) if final_avg else 0
            
            return {
                "by_weekday": by_weekday,
                "peak_hour": peak_hour,
                "slowest_hour": slowest_hour,
                "avg_session_minutes": round(avg_session_minutes, 2),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Ошибка при анализе активности: {e}", exc_info=True)
        return {"error": str(e)}


async def get_tools_usage_stats(days: int = 7) -> dict[str, Any]:
    """
    Детальная статистика использования AI Tools (memory, images).
    
    Args:
        days: Количество дней для анализа
        
    Returns:
        dict: Использование функций save_memory, get_memories, generate_image
    """
    try:
        async with async_session_factory() as session:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Новые факты за период (по датам)
            new_memories_query = select(
                func.date(LongTermMemory.created_at).label('date'),
                func.count(LongTermMemory.id).label('count')
            ).where(
                LongTermMemory.created_at >= start_date
            ).group_by(func.date(LongTermMemory.created_at)).order_by(func.date(LongTermMemory.created_at))
            
            new_memories_result = await session.execute(new_memories_query)
            memory_by_day = {str(row.date): row.count for row in new_memories_result}
            
            # Топ категорий
            top_categories_query = select(
                LongTermMemory.category,
                func.count(LongTermMemory.id).label('count')
            ).where(
                LongTermMemory.created_at >= start_date
            ).group_by(LongTermMemory.category).order_by(func.count(LongTermMemory.id).desc()).limit(5)
            
            top_categories_result = await session.execute(top_categories_query)
            top_categories = {row.category: row.count for row in top_categories_result}
            
            # Пользователи, активно использующие память (>5 фактов)
            power_users_query = select(
                func.count(func.distinct(LongTermMemory.user_id))
            ).where(
                LongTermMemory.user_id.in_(
                    select(LongTermMemory.user_id).group_by(LongTermMemory.user_id).having(
                        func.count(LongTermMemory.id) > 5
                    )
                )
            )
            power_users = await session.scalar(power_users_query) or 0
            
            return {
                "period_days": days,
                "memory": {
                    "new_facts_by_day": memory_by_day,
                    "top_categories": top_categories,
                    "power_users": power_users
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Ошибка при статистике использования tools: {e}", exc_info=True)
        return {"error": str(e)}

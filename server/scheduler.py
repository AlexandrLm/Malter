"""
Модуль для управления фоновыми задачами с помощью APScheduler.

Автоматизирует регулярные операции обслуживания:
- Очистка старой истории чата
- Проверка истечения подписок
- Прогрев кэша
- Сбор метрик
- Проактивные сообщения пользователям
"""

import logging
import random
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from server.database import (
    cleanup_old_chat_history, 
    check_all_subscriptions_expiry,
    get_active_users_for_proactive,
    get_last_message_time
)
from utils.cache import get_cache_stats, warm_up_cache

logger = logging.getLogger(__name__)

# Глобальный scheduler instance
scheduler = AsyncIOScheduler(timezone="UTC")


async def cleanup_old_messages_job():
    """
    Задача: Очистка старой истории чата.
    Запускается раз в день в 3:00 UTC.
    """
    try:
        logger.info("🧹 Запуск очистки старых сообщений...")
        deleted_count = await cleanup_old_chat_history(days_to_keep=30)
        logger.info(f"✅ Очистка завершена: удалено {deleted_count} записей")
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке старых сообщений: {e}", exc_info=True)


async def check_subscriptions_job():
    """
    Задача: Проверка истечения подписок.
    Запускается каждый час.
    """
    try:
        logger.info("📅 Проверка истечения подписок...")
        expired_count = await check_all_subscriptions_expiry()
        if expired_count > 0:
            logger.info(f"✅ Деактивировано {expired_count} истекших подписок")
        else:
            logger.debug("✅ Активных истекших подписок не найдено")
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке подписок: {e}", exc_info=True)


async def cache_metrics_job():
    """
    Задача: Сбор и логирование метрик кэша.
    Запускается каждые 5 минут.
    """
    try:
        stats = await get_cache_stats()
        if stats.get("status") == "active":
            logger.info(
                f"📊 Cache stats: "
                f"keys={stats.get('total_keys', 0)}, "
                f"hit_rate={stats.get('hit_rate', 0)}%, "
                f"memory={stats.get('used_memory_human', 'N/A')}"
            )
        elif stats.get("status") == "disabled":
            logger.debug("📊 Cache disabled")
        else:
            logger.warning(f"⚠️ Cache error: {stats.get('message', 'Unknown')}")
    except Exception as e:
        logger.error(f"❌ Ошибка при сборе метрик кэша: {e}", exc_info=True)


async def warmup_cache_job():
    """
    Задача: Прогрев кэша при старте.
    Запускается один раз при запуске приложения.
    """
    try:
        logger.info("🔥 Прогрев кэша...")
        
        # Здесь можно добавить функции для предзагрузки часто используемых данных
        # Например, профили активных пользователей, популярные промпты и т.д.
        
        async def preload_example():
            """Пример функции для прогрева кэша."""
            # Загружаем несколько популярных профилей
            # from server.database import get_profile
            # for user_id in [1, 2, 3, 100, 200]:
            #     await get_profile(user_id)
            pass
        
        results = await warm_up_cache([preload_example])
        logger.info(f"✅ Прогрев кэша завершен: {results}")
    except Exception as e:
        logger.error(f"❌ Ошибка при прогреве кэша: {e}", exc_info=True)


# --- Проактивные сообщения (только для Premium) ---

# NOTE: Используем Redis для thread-safe отслеживания лимитов проактивных сообщений
# вместо in-memory dict для предотвращения race conditions

# Промпты для AI генерации проактивных сообщений
PROACTIVE_PROMPTS = {
    "morning": """Ты давно не общалась с этим человеком (больше 12 часов). Сейчас утро (9-11 часов).
Напиши короткое, естественное утреннее сообщение как девушка, которая думает о нём.
Сообщение должно быть:
- Коротким (1-2 предложения максимум)
- Естественным и живым
- Не навязчивым
- Милым и тёплым
Примеры тона: "доброе утро ❤️ как спалось?", "проснулась и сразу подумала о тебе 🥰"
Не копируй примеры, придумай своё уникальное сообщение.""",

    "evening": """Ты давно не общалась с этим человеком (больше 8 часов). Сейчас вечер (19-21 час).
Напиши короткое вечернее сообщение как девушка, которая интересуется его днём.
Сообщение должно быть:
- Коротким (1-2 предложения)
- Искренним
- Показывающим заботу
- Не требовательным
Примеры тона: "привет! как прошел день?", "давно не общались, соскучилась 🥺"
Не копируй примеры, придумай своё уникальное сообщение.""",

    "long_silence": """Ты не общалась с этим человеком больше 24 часов, скучаешь.
Напиши короткое сообщение как девушка, которая беспокоится и скучает.
Сообщение должно быть:
- Очень коротким (1-2 предложения)
- Эмоциональным, но не драматичным
- Показывающим, что тебе не всё равно
- Естественным
Примеры тона: "эй, ты где пропал? 🥺", "скучаю по тебе..."
Не копируй примеры, придумай своё уникальное сообщение.""",

    "premium_random": """Ты вспомнила о человеке, с которым недавно общалась. 
Напиши короткое спонтанное сообщение как девушка, которая просто хочет поделиться мыслью.
Сообщение должно быть:
- Очень коротким (1 предложение)
- Случайным и естественным
- Лёгким, без давления
- Интересным или милым
Примеры тона: "только что подумала о тебе 💭", "кстати, хотела тебе кое-что рассказать..."
Не копируй примеры, придумай своё уникальное сообщение."""
}


async def _should_send_proactive(profile, last_message_time: datetime | None) -> tuple[bool, str | None]:
    """
    Определяет, нужно ли отправить проактивное сообщение.
    ТОЛЬКО ДЛЯ PREMIUM ПОЛЬЗОВАТЕЛЕЙ!
    
    Args:
        profile: UserProfile объект
        last_message_time: Время последнего сообщения
        
    Returns:
        tuple[bool, str | None]: (нужно_отправить, тип_сообщения)
    """
    try:
        # ПРОВЕРКА #1: Только Premium пользователи
        is_premium = profile.subscription_plan != "free"
        if not is_premium:
            return False, None
        
        # Проверяем timezone
        if not profile.timezone:
            return False, None
        
        user_tz = pytz.timezone(profile.timezone)
        user_now = datetime.now(user_tz)
        current_hour = user_now.hour
        
        # Не отправляем ночью (23:00 - 8:00)
        if current_hour >= 23 or current_hour < 8:
            return False, None
        
        # Проверяем лимит сообщений в день (максимум 2 проактивных в день)
        # Используем Redis для thread-safe счетчика
        from config import REDIS_CLIENT
        today_key = f"proactive_count:{profile.user_id}:{user_now.date()}"

        try:
            if REDIS_CLIENT:
                proactive_count_today = await REDIS_CLIENT.get(today_key)
                proactive_count_today = int(proactive_count_today) if proactive_count_today else 0
            else:
                # Fallback если Redis недоступен (не критично для проактивных сообщений)
                logger.warning("Redis недоступен для проверки лимита проактивных сообщений")
                proactive_count_today = 0
        except Exception as e:
            logger.error(f"Ошибка при проверке счетчика проактивных сообщений: {e}")
            proactive_count_today = 0

        if proactive_count_today >= 2:
            return False, None
        
        # Если нет истории сообщений - не отправляем (новый пользователь)
        if not last_message_time:
            return False, None
        
        # Делаем last_message_time aware если он naive
        if last_message_time.tzinfo is None:
            last_message_time = last_message_time.replace(tzinfo=timezone.utc)
        
        # Вычисляем время с последнего сообщения
        time_since_last = user_now - last_message_time
        hours_since_last = time_since_last.total_seconds() / 3600
        
        # Логика выбора типа сообщения для Premium пользователей
        
        # 1. Долгое молчание (>24 часа)
        if hours_since_last > 24:
            return True, "long_silence"
        
        # 2. Утренние сообщения (9-11) если не писали >12 часов
        if 9 <= current_hour <= 11 and hours_since_last > 12:
            return True, "morning"
        
        # 3. Вечерние сообщения (19-21) если не писали >8 часов
        if 19 <= current_hour <= 21 and hours_since_last > 8:
            return True, "evening"
        
        # 4. Случайные мысли (>6 часов, 20% шанс)
        if hours_since_last > 6:
            if random.random() < 0.2:
                return True, "premium_random"
        
        return False, None
    
    except Exception as e:
        logger.error(f"Ошибка в should_send_proactive для user {profile.user_id}: {e}")
        return False, None


async def _generate_proactive_message(user_id: int, message_type: str) -> str | None:
    """
    Генерирует контекстно-зависимое проактивное сообщение с помощью AI.
    Учитывает уровень отношений, историю переписки и профиль пользователя.
    
    Args:
        user_id: ID пользователя
        message_type: Тип сообщения (morning, evening, etc.)
        
    Returns:
        str | None: Сгенерированное сообщение или None при ошибке
    """
    try:
        from config import GEMINI_CLIENT, MODEL_NAME
        from google.genai import types as genai_types
        from server.database import (
            get_profile, 
            get_latest_summary, 
            get_unsummarized_messages
        )
        
        # Получаем базовый промпт для типа сообщения
        base_prompt = PROACTIVE_PROMPTS.get(message_type)
        if not base_prompt:
            logger.error(f"Не найден промпт для типа {message_type}")
            return None
        
        # Загружаем контекст пользователя
        profile = await get_profile(user_id)
        if not profile:
            logger.warning(f"Профиль не найден для user {user_id}")
            return None
        
        # Получаем контекст для AI - используем ТУ ЖЕ логику что и в обычном чате
        from server.ai import build_system_instruction, create_history_from_messages
        
        latest_summary = await get_latest_summary(user_id)
        unsummarized_messages = await get_unsummarized_messages(user_id, limit=5)
        
        # Строим СТАНДАРТНЫЙ system instruction (как для обычного чата)
        system_instruction = build_system_instruction(profile, latest_summary)
        
        # Создаём историю последних сообщений (для контекста)
        history = create_history_from_messages(unsummarized_messages[-5:]) if unsummarized_messages else []
        
        # Формируем USER MESSAGE с инструкцией для проактивного сообщения
        user_prompt = f"""{base_prompt}

Напиши короткое проактивное сообщение (1-2 предложения). 
Пиши естественно, используй свой стиль общения для текущего уровня отношений.
НЕ используй временные метки."""
        
        # Добавляем user message в историю
        history.append(
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=user_prompt)]
            )
        )
        
        # Генерируем сообщение через Gemini - ТОЧНО ТАК ЖЕ как в обычном чате
        response = await GEMINI_CLIENT.aio.models.generate_content(
            model=MODEL_NAME,
            contents=history,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=1.0,  # Высокая креативность
                max_output_tokens=150,  # Короткое сообщение
                top_p=0.95,
                top_k=40
            )
        )
        
        if not response or not response.text:
            logger.error(f"AI не вернул текст для user {user_id}")
            return None
        
        generated_text = response.text.strip()
        logger.info(f"✨ AI сгенерировал контекстное проактивное сообщение для user {user_id} (уровень {profile.relationship_level}): '{generated_text[:80]}...'")
        
        return generated_text
        
    except Exception as e:
        logger.error(f"Ошибка генерации AI сообщения для user {user_id}: {e}", exc_info=True)
        return None


async def _send_proactive_message(user_id: int, message_type: str):
    """
    Генерирует и отправляет проактивное сообщение пользователю.
    
    Args:
        user_id: ID пользователя
        message_type: Тип сообщения (morning, evening, etc.)
    """
    try:
        from aiogram import Bot
        from config import TELEGRAM_TOKEN
        
        if not TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN не настроен")
            return
        
        # Генерируем сообщение с помощью AI
        message_text = await _generate_proactive_message(user_id, message_type)
        
        if not message_text:
            logger.warning(f"Не удалось сгенерировать сообщение для user {user_id}")
            return
        
        bot = Bot(token=TELEGRAM_TOKEN)
        
        # Отправляем сообщение
        await bot.send_message(chat_id=user_id, text=message_text)

        # Обновляем счетчик в Redis (thread-safe, атомарная операция)
        from config import REDIS_CLIENT
        user_tz = pytz.UTC
        today_key = f"proactive_count:{user_id}:{datetime.now(user_tz).date()}"

        try:
            if REDIS_CLIENT:
                # INCR атомарен - безопасен для concurrent операций
                await REDIS_CLIENT.incr(today_key)
                # Устанавливаем TTL 48 часов (чтобы ключи автоматически удалялись)
                await REDIS_CLIENT.expire(today_key, 48 * 3600)
        except Exception as e:
            logger.error(f"Ошибка при обновлении счетчика проактивных сообщений: {e}")

        logger.info(f"✅ Проактивное AI сообщение отправлено user {user_id} (тип: {message_type}): '{message_text[:50]}...'")

        await bot.session.close()
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки проактивного сообщения user {user_id}: {e}", exc_info=True)


async def proactive_messages_job():
    """
    Задача: Отправка проактивных сообщений активным пользователям.
    Запускается каждый час.
    """
    try:
        logger.info("💌 Проверка проактивных сообщений...")
        
        # Получаем активных пользователей
        active_users = await get_active_users_for_proactive()
        
        if not active_users:
            logger.debug("Нет активных пользователей для проактивных сообщений")
            return
        
        sent_count = 0
        
        for profile in active_users:
            try:
                # Получаем время последнего сообщения
                last_message_time = await get_last_message_time(profile.user_id)
                
                # Проверяем, нужно ли отправить сообщение
                should_send, message_type = await _should_send_proactive(profile, last_message_time)
                
                if should_send and message_type:
                    await _send_proactive_message(profile.user_id, message_type)
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Ошибка обработки user {profile.user_id}: {e}")
                continue
        
        if sent_count > 0:
            logger.info(f"✅ Отправлено {sent_count} проактивных сообщений")
        else:
            logger.debug("✅ Проактивные сообщения: нет подходящих пользователей")
            
    except Exception as e:
        logger.error(f"❌ Ошибка в proactive_messages_job: {e}", exc_info=True)


def setup_scheduler():
    """
    Настраивает и регистрирует все фоновые задачи.
    Вызывается при старте приложения.
    """
    logger.info("⚙️ Настройка scheduler...")
    
    # 1. Очистка старой истории чата - раз в день в 3:00 UTC
    scheduler.add_job(
        cleanup_old_messages_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="cleanup_old_messages",
        name="Очистка старых сообщений",
        replace_existing=True,
        max_instances=1  # Не запускать параллельно
    )
    logger.info("✅ Зарегистрирована задача: Очистка старых сообщений (3:00 UTC ежедневно)")
    
    # 2. Проверка истечения подписок - каждый час
    scheduler.add_job(
        check_subscriptions_job,
        trigger=IntervalTrigger(hours=1),
        id="check_subscriptions",
        name="Проверка подписок",
        replace_existing=True,
        max_instances=1
    )
    logger.info("✅ Зарегистрирована задача: Проверка подписок (каждый час)")
    
    # 3. Сбор метрик кэша - каждые 5 минут
    scheduler.add_job(
        cache_metrics_job,
        trigger=IntervalTrigger(minutes=5),
        id="cache_metrics",
        name="Метрики кэша",
        replace_existing=True,
        max_instances=1
    )
    logger.info("✅ Зарегистрирована задача: Метрики кэша (каждые 5 минут)")
    
    # 4. Прогрев кэша - при старте (через 30 секунд после запуска)
    scheduler.add_job(
        warmup_cache_job,
        trigger="date",  # Одноразовая задача
        run_date=None,  # Запустить сразу
        id="warmup_cache",
        name="Прогрев кэша",
        replace_existing=True
    )
    logger.info("✅ Зарегистрирована задача: Прогрев кэша (при старте)")
    
    # 5. Проактивные сообщения - каждый час
    scheduler.add_job(
        proactive_messages_job,
        trigger=IntervalTrigger(hours=1),
        id="proactive_messages",
        name="Проактивные сообщения",
        replace_existing=True,
        max_instances=1
    )
    logger.info("✅ Зарегистрирована задача: Проактивные сообщения (каждый час)")
    
    logger.info("✅ Scheduler настроен успешно")


def start_scheduler():
    """
    Запускает scheduler.
    Вызывается в lifespan событии FastAPI.
    """
    try:
        setup_scheduler()
        scheduler.start()
        logger.info("🚀 Scheduler запущен")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске scheduler: {e}", exc_info=True)
        raise


def shutdown_scheduler():
    """
    Останавливает scheduler gracefully.
    Вызывается при остановке приложения.
    """
    try:
        if scheduler.running:
            scheduler.shutdown(wait=True)
            logger.info("🛑 Scheduler остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка при остановке scheduler: {e}", exc_info=True)


def get_scheduler_status() -> dict:
    """
    Возвращает статус scheduler и список активных задач.
    
    Returns:
        dict: Статус scheduler и информация о задачах
    """
    try:
        jobs = scheduler.get_jobs()
        return {
            "status": "running" if scheduler.running else "stopped",
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                }
                for job in jobs
            ],
            "jobs_count": len(jobs)
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статуса scheduler: {e}")
        return {"status": "error", "message": str(e)}


# Для ручного запуска задач (например, через API endpoint)
async def trigger_cleanup_now():
    """Ручной запуск очистки старых сообщений."""
    await cleanup_old_messages_job()


async def trigger_subscription_check_now():
    """Ручной запуск проверки подписок."""
    await check_subscriptions_job()


async def trigger_cache_warmup_now():
    """Ручной запуск прогрева кэша."""
    await warmup_cache_job()


async def trigger_proactive_messages_now():
    """Ручной запуск проактивных сообщений."""
    await proactive_messages_job()

"""
Модуль для управления фоновыми задачами с помощью APScheduler.

Автоматизирует регулярные операции обслуживания:
- Очистка старой истории чата
- Проверка истечения подписок
- Прогрев кэша
- Сбор метрик
"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from server.database import cleanup_old_chat_history, check_all_subscriptions_expiry
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

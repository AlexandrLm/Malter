"""
Мониторинг производительности базы данных.

Этот модуль содержит middleware и утилиты для отслеживания:
- Медленных запросов (slow queries)
- Количества запросов к БД
- Метрики производительности

Использование:
    В database.py добавить event listener для мониторинга всех запросов.
"""

import logging
import time
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

# Порог для slow queries (секунды)
SLOW_QUERY_THRESHOLD = 1.0

# Счетчики для метрик
query_metrics = {
    "total_queries": 0,
    "slow_queries": 0,
    "total_time": 0.0
}

def log_slow_query(duration: float, statement: str, parameters: dict):
    """
    Логирует медленный запрос с деталями.
    
    Args:
        duration: Время выполнения в секундах
        statement: SQL запрос
        parameters: Параметры запроса
    """
    logger.warning(
        f"SLOW QUERY detected ({duration:.2f}s):\n"
        f"SQL: {statement}\n"
        f"Parameters: {parameters}"
    )
    query_metrics["slow_queries"] += 1


def setup_query_monitoring(engine: AsyncEngine, threshold: float = SLOW_QUERY_THRESHOLD):
    """
    Настраивает мониторинг запросов для async engine.
    
    Args:
        engine: SQLAlchemy AsyncEngine
        threshold: Порог для slow queries в секундах
    """
    
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Сохраняет время начала запроса."""
        conn.info.setdefault('query_start_time', []).append(time.perf_counter())
        logger.debug(f"Query started: {statement[:100]}...")
    
    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Вычисляет время выполнения и логирует slow queries."""
        if 'query_start_time' in conn.info:
            start_times = conn.info['query_start_time']
            if start_times:
                start_time = start_times.pop()
                duration = time.perf_counter() - start_time
                
                # Обновляем метрики
                query_metrics["total_queries"] += 1
                query_metrics["total_time"] += duration
                
                # Логируем slow query
                if duration > threshold:
                    log_slow_query(duration, statement, parameters)
                else:
                    logger.debug(f"Query completed in {duration:.3f}s: {statement[:100]}...")


def get_query_metrics() -> dict:
    """
    Возвращает текущие метрики запросов.
    
    Returns:
        dict: Словарь с метриками:
            - total_queries: Общее количество запросов
            - slow_queries: Количество медленных запросов
            - total_time: Общее время выполнения (секунды)
            - avg_time: Среднее время выполнения (секунды)
            - slow_query_percentage: Процент медленных запросов
    """
    total = query_metrics["total_queries"]
    slow = query_metrics["slow_queries"]
    total_time = query_metrics["total_time"]
    
    return {
        "total_queries": total,
        "slow_queries": slow,
        "total_time": round(total_time, 2),
        "avg_time": round(total_time / total, 3) if total > 0 else 0,
        "slow_query_percentage": round((slow / total * 100), 2) if total > 0 else 0
    }


def reset_query_metrics():
    """Сбрасывает счетчики метрик (для тестирования или периодического сброса)."""
    query_metrics["total_queries"] = 0
    query_metrics["slow_queries"] = 0
    query_metrics["total_time"] = 0.0
    logger.info("Query metrics reset")

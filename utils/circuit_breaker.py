"""
Модуль для реализации Circuit Breaker паттерна.

Circuit Breaker защищает систему от каскадных сбоев при проблемах с внешними сервисами.
Три состояния: CLOSED (норма), OPEN (сбой, запросы блокируются), HALF_OPEN (тестирование восстановления).
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Any, TypeVar, Generic
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Состояния Circuit Breaker."""
    CLOSED = "CLOSED"        # Нормальная работа
    OPEN = "OPEN"            # Сервис недоступен, запросы блокируются
    HALF_OPEN = "HALF_OPEN"  # Тестирование восстановления


class CircuitBreakerError(Exception):
    """Исключение, вызываемое когда circuit breaker открыт."""
    pass


class CircuitBreaker(Generic[T]):
    """
    Circuit Breaker для защиты от каскадных сбоев.
    
    Использование:
        cb = CircuitBreaker(
            name="gemini_api",
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=APIError
        )
        
        @cb.call
        async def risky_operation():
            ...
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] = Exception,
        success_threshold: int = 2,
    ):
        """
        Инициализация Circuit Breaker.
        
        Args:
            name: Имя circuit breaker для логирования
            failure_threshold: Количество сбоев для открытия circuit
            recovery_timeout: Время (сек) до попытки восстановления
            expected_exception: Тип исключения, который считается сбоем
            success_threshold: Количество успехов в HALF_OPEN для закрытия circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        
        # Состояние
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.last_attempt_time: datetime | None = None
        
        # Статистика
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.total_blocked = 0
    
    def _should_attempt_reset(self) -> bool:
        """Проверяет, пора ли попытаться восстановить соединение."""
        if self.state != CircuitState.OPEN:
            return False
        
        if not self.last_failure_time:
            return True
        
        time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.recovery_timeout
    
    def _on_success(self):
        """Обрабатывает успешный вызов."""
        self.total_successes += 1
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.info(
                f"🟡 {self.name} Circuit Breaker: HALF_OPEN успех "
                f"{self.success_count}/{self.success_threshold}"
            )
            
            if self.success_count >= self.success_threshold:
                self._close_circuit()
        elif self.state == CircuitState.CLOSED:
            # Уже закрыт, все хорошо
            pass
    
    def _on_failure(self, exception: Exception):
        """Обрабатывает неудачный вызов."""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            # В HALF_OPEN даже одна ошибка возвращает в OPEN
            self._open_circuit()
            logger.warning(
                f"🔴 {self.name} Circuit Breaker: HALF_OPEN → OPEN (тест провален)"
            )
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._open_circuit()
                logger.error(
                    f"🔴 {self.name} Circuit Breaker: CLOSED → OPEN "
                    f"(превышен порог: {self.failure_count} сбоев)"
                )
            else:
                logger.warning(
                    f"⚠️ {self.name} Circuit Breaker: сбой "
                    f"{self.failure_count}/{self.failure_threshold} - {exception}"
                )
    
    def _open_circuit(self):
        """Открывает circuit (блокирует запросы)."""
        self.state = CircuitState.OPEN
        self.success_count = 0
    
    def _close_circuit(self):
        """Закрывает circuit (восстанавливает работу)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"✅ {self.name} Circuit Breaker: восстановлен (CLOSED)")
    
    def _half_open_circuit(self):
        """Переводит в режим тестирования."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        logger.info(f"🟡 {self.name} Circuit Breaker: тестирование восстановления (HALF_OPEN)")
    
    def call(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Декоратор для оборачивания функции в circuit breaker.
        
        Args:
            func: Async функция для защиты
            
        Returns:
            Обернутая функция
        """
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            self.total_calls += 1
            self.last_attempt_time = datetime.now()
            
            # Проверяем состояние circuit
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._half_open_circuit()
                else:
                    self.total_blocked += 1
                    raise CircuitBreakerError(
                        f"{self.name} Circuit Breaker открыт. "
                        f"Повтор через {self.recovery_timeout}s"
                    )
            
            # Пытаемся выполнить функцию
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure(e)
                raise
            except Exception as e:
                # Неожиданное исключение - не считаем сбоем circuit breaker
                logger.error(f"Неожиданная ошибка в {self.name}: {e}")
                raise
        
        return wrapper
    
    def get_state(self) -> str:
        """Возвращает текущее состояние."""
        return self.state.value
    
    def get_stats(self) -> dict[str, Any]:
        """
        Возвращает статистику работы circuit breaker.
        
        Returns:
            dict: Статистика (state, failure_count, total_calls, etc.)
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "total_blocked": self.total_blocked,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_attempt_time": self.last_attempt_time.isoformat() if self.last_attempt_time else None,
            "time_until_retry": self._time_until_retry() if self.state == CircuitState.OPEN else None
        }
    
    def _time_until_retry(self) -> int:
        """Возвращает время до следующей попытки (секунды)."""
        if not self.last_failure_time:
            return 0
        
        time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
        remaining = max(0, self.recovery_timeout - time_since_failure)
        return int(remaining)
    
    def reset(self):
        """Принудительный сброс circuit breaker (для тестирования/админки)."""
        logger.info(f"🔄 {self.name} Circuit Breaker: принудительный сброс")
        self._close_circuit()
        self.last_failure_time = None
        self.last_attempt_time = None


# Готовые экземпляры для разных сервисов
gemini_circuit_breaker = CircuitBreaker(
    name="Gemini API",
    failure_threshold=5,      # 5 сбоев подряд
    recovery_timeout=60,      # Ждем 60 секунд перед повтором
    expected_exception=Exception,  # Ловим все ошибки API
    success_threshold=2       # 2 успеха в HALF_OPEN для восстановления
)


def get_all_circuit_breakers() -> list[CircuitBreaker]:
    """Возвращает список всех circuit breakers для мониторинга."""
    return [
        gemini_circuit_breaker,
        # Добавляйте новые circuit breakers здесь
    ]

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

from geopy.geocoders import Nominatim
from geopy.location import Location
from timezonefinder import TimezoneFinder

logger = logging.getLogger(__name__)


class GeolocationService:
    """Сервис для получения геолокации и часового пояса города с кэшированием."""
    
    def __init__(self, max_workers: int = 4) -> None:
        """
        Инициализация сервиса геолокации.
        
        Args:
            max_workers: Максимальное количество потоков в ThreadPoolExecutor
        """
        self.tf = TimezoneFinder()
        self.geolocator = Nominatim(user_agent="EvolveAI", timeout=10)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cache: dict[str, Tuple[Optional[Location], str]] = {}
        logger.debug(f"GeolocationService initialized with {max_workers} workers")
    
    async def get_location_and_timezone(self, city: str) -> Tuple[Optional[Location], str]:
        """
        Получает локацию и часовой пояс для города асинхронно с кэшированием.
        
        Args:
            city: Название города
            
        Returns:
            tuple: (location, timezone) - локация и часовой пояс (или None и "UTC" при ошибке)
        """
        city_normalized = city.strip().lower()
        
        # Проверяем кэш
        if city_normalized in self._cache:
            logger.debug(f"Cache hit for city: {city}")
            return self._cache[city_normalized]
        
        try:
            loop = asyncio.get_event_loop()
            
            # Получаем локацию
            location = await loop.run_in_executor(
                self.executor, self.geolocator.geocode, city
            )
            
            if location:
                # Получаем часовой пояс
                timezone = await loop.run_in_executor(
                    self.executor,
                    lambda: self.tf.timezone_at(lng=location.longitude, lat=location.latitude)
                )
                result = (location, timezone or "UTC")
                logger.info(f"Location found for '{city}': {location.address}, timezone: {timezone}")
            else:
                result = (None, "UTC")
                logger.warning(f"Location not found for city: {city}")
            
            # Сохраняем в кэш
            self._cache[city_normalized] = result
            return result
            
        except Exception as e:
            logger.error(f"Error getting location for '{city}': {e}", exc_info=True)
            # Кэшируем неудачный результат чтобы не повторять запросы
            result = (None, "UTC")
            self._cache[city_normalized] = result
            return result
    
    def clear_cache(self) -> None:
        """Очищает кэш геолокации."""
        self._cache.clear()
        logger.debug("Geolocation cache cleared")
    
    async def close(self) -> None:
        """Закрывает ThreadPoolExecutor и освобождает ресурсы."""
        try:
            self.executor.shutdown(wait=True)
            logger.debug("GeolocationService closed")
        except Exception as e:
            logger.error(f"Error closing GeolocationService: {e}")
    
    def __del__(self) -> None:
        """Деструктор для автоматического закрытия ресурсов."""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)
        except Exception:
            pass
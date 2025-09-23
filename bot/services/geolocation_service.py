import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

logger = logging.getLogger(__name__)

class GeolocationService:
    def __init__(self):
        self.tf = TimezoneFinder()
        self.geolocator = Nominatim(user_agent="EvolveAI")
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def get_location_and_timezone(self, city: str):
        """
        Получает локацию и часовой пояс для города асинхронно.
        """
        try:
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(
                self.executor, self.geolocator.geocode, city
            )
            if location:
                timezone = await loop.run_in_executor(
                    self.executor,
                    self.tf.timezone_at,
                    lng=location.longitude,
                    lat=location.latitude
                )
                return location, timezone
            return None, "UTC"
        except Exception as e:
            logger.error(f"Error getting location for {city}: {e}")
            return None, "UTC"
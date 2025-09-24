import base64
import logging
from aiogram.types import Message
from io import BytesIO

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

async def process_image(message: Message) -> str | None:
    """
    Обрабатывает изображение из сообщения и возвращает его в формате base64.
    
    Args:
        message (Message): Сообщение с изображением.
        
    Returns:
        str | None: Изображение в формате base64 или None, если изображение не найдено или слишком большое.
    """
    if not message.photo:
        return None
        
    try:
        # Выбираем лучшее качество (последнее в списке)
        photo = message.photo[-1]
        # Скачиваем фото в память
        photo_bytes = BytesIO()
        await message.bot.download(photo, destination=photo_bytes)
        photo_bytes.seek(0)
        
        # Проверяем размер
        file_size = len(photo_bytes.getvalue())
        
        if file_size > MAX_IMAGE_SIZE:
            logger.warning(f"Image too large for user {message.from_user.id}: {file_size} bytes")
            return None
        return base64.b64encode(photo_bytes.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error processing image for user {message.from_user.id}: {e}")
        return None
        
    return None
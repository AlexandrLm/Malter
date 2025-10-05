import base64
import logging
from io import BytesIO
from typing import Optional

from aiogram.types import Message
from PIL import Image

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_DIMENSIONS = (1024, 1024)  # Max resolution
JPEG_QUALITY = 85  # Качество JPEG сжатия


class ImageProcessingError(Exception):
    """Исключение для ошибок обработки изображений."""
    pass


async def process_image(message: Message) -> Optional[str]:
    """
    Обрабатывает изображение из сообщения и возвращает его в формате base64.
    Включает валидацию, сжатие и уведомления пользователя об ошибках.
    
    Args:
        message: Сообщение с изображением
        
    Returns:
        Изображение в формате base64 или None при ошибке
        
    Raises:
        ImageProcessingError: При критических ошибках обработки
    """
    if not message.photo:
        return None
    
    user_id = message.from_user.id
    
    try:
        # Выбираем лучшее качество (последнее в списке)
        photo = message.photo[-1]
        
        # Скачиваем фото в память
        photo_bytes = BytesIO()
        await message.bot.download(photo, destination=photo_bytes)
        photo_bytes.seek(0)
        
        # Проверяем размер сырых данных
        raw_data = photo_bytes.getvalue()
        raw_size = len(raw_data)
        if raw_size > MAX_IMAGE_SIZE:
            logger.warning(f"Raw image too large for user {user_id}: {raw_size} bytes")
            await message.answer(
                "⚠️ Изображение слишком большое (более 10MB). "
                "Пожалуйста, отправьте изображение меньшего размера."
            )
            return None
        
        # Валидация и обработка изображения с Pillow
        image_stream = BytesIO(raw_data)
        
        try:
            image = Image.open(image_stream)
            # Проверяем, что это валидное изображение
            image.verify()
            
            # Переоткрываем после verify
            image_stream = BytesIO(raw_data)
            image = Image.open(image_stream)
            
            # Конвертируем в RGB если RGBA/LA/P (для JPEG)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            
            # Изменяем размер если слишком большой
            image.thumbnail(MAX_IMAGE_DIMENSIONS, Image.Resampling.LANCZOS)
            
            # Сохраняем как JPEG с оптимизацией
            output_bytes = BytesIO()
            image.save(output_bytes, format='JPEG', quality=JPEG_QUALITY, optimize=True)
            processed_bytes = output_bytes.getvalue()
            
            # Финальная проверка размера после обработки
            if len(processed_bytes) > MAX_IMAGE_SIZE:
                logger.warning(
                    f"Processed image still too large for user {user_id}: "
                    f"{len(processed_bytes)} bytes"
                )
                await message.answer(
                    "⚠️ Не удалось сжать изображение до допустимого размера. "
                    "Попробуйте другое изображение."
                )
                return None
            
            logger.info(
                f"Image processed successfully for user {user_id}: "
                f"{len(processed_bytes)} bytes, {image.size} dimensions"
            )
            return base64.b64encode(processed_bytes).decode('utf-8')
            
        except Exception as pil_error:
            logger.error(f"Pillow validation error for user {user_id}: {pil_error}")
            await message.answer(
                "⚠️ Не удалось обработать изображение. "
                "Убедитесь, что это корректный файл изображения."
            )
            return None
            
    except Exception as e:
        logger.error(f"Error processing image for user {user_id}: {e}", exc_info=True)
        await message.answer(
            "⚠️ Произошла ошибка при обработке изображения. Попробуйте еще раз."
        )
        return None
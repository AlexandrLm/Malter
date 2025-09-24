import base64
import logging
from aiogram.types import Message
from io import BytesIO
from PIL import Image
import io

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_DIMENSIONS = (1024, 1024)  # Max resolution to prevent large images

async def process_image(message: Message) -> str | None:
    """
    Обрабатывает изображение из сообщения и возвращает его в формате base64.
    Добавлена валидация и сжатие с помощью Pillow для безопасности и оптимизации.
    
    Args:
        message (Message): Сообщение с изображением.
        
    Returns:
        str | None: Изображение в формате base64 или None, если изображение не найдено, слишком большое или невалидное.
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
        
        # Проверяем размер сырых данных
        raw_size = len(photo_bytes.getvalue())
        if raw_size > MAX_IMAGE_SIZE:
            logger.warning(f"Raw image too large for user {message.from_user.id}: {raw_size} bytes")
            return None
        
        # Валидация и обработка изображения с Pillow
        image_stream = io.BytesIO(photo_bytes.getvalue())
        try:
            image = Image.open(image_stream)
            # Проверить, что это валидное изображение
            image.verify()
            # Переоткрыть после verify (PIL требует этого)
            image_stream.seek(0)
            image = Image.open(image_stream)
            
            # Конвертировать в RGB если RGBA (для JPEG)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Изменить размер если слишком большой
            image.thumbnail(MAX_IMAGE_DIMENSIONS, Image.Resampling.LANCZOS)
            
            # Сохранить как JPEG с качеством 85% для оптимизации
            output_bytes = BytesIO()
            image.save(output_bytes, format='JPEG', quality=85, optimize=True)
            processed_bytes = output_bytes.getvalue()
            
            # Финальная проверка размера после обработки
            if len(processed_bytes) > MAX_IMAGE_SIZE:
                logger.warning(f"Processed image still too large for user {message.from_user.id}: {len(processed_bytes)} bytes")
                return None
            
            logger.info(f"Image processed successfully for user {message.from_user.id}: {len(processed_bytes)} bytes, {image.size} dimensions")
            return base64.b64encode(processed_bytes).decode('utf-8')
            
        except Exception as pil_error:
            logger.error(f"Pillow validation error for user {message.from_user.id}: {pil_error}")
            return None
            
    except Exception as e:
        logger.error(f"Error processing image for user {message.from_user.id}: {e}")
        return None
        
    return None
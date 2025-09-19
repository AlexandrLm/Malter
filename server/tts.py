import os
import asyncio
from google.genai import types as genai_types
from google.genai.errors import APIError
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from config import TTS_CLIENT

async def create_telegram_voice_message(text_to_speak: str, output_file_object: object) -> bool:
    """
    Асинхронно генерирует аудио из текста и сохраняет его в файловый объект
    в формате OGG/OPUS, подходящем для голосовых сообщений Telegram.
    """
    if not TTS_CLIENT:
        logging.error("Клиент TTS не инициализирован.")
        return False
        
    try:
        logging.info(f"Генерация аудио для текста: '{text_to_speak}'...")
        
        response = await call_tts_api_with_retry(text_to_speak)
        
        # Получаем аудиоданные напрямую из ответа
        if not response.candidates or not response.candidates[0].content.parts:
            logging.error("Ответ от TTS API не содержит аудиоданных.")
            return False
        
        pcm_data = response.candidates[0].content.parts[0].inline_data.data
        logging.info("Аудиоданные (PCM) получены.")
        
        # Если получили WAV, конвертируем через pydub
        if isinstance(pcm_data, bytes) and pcm_data.startswith(b'RIFF'):
            # Это WAV файл, загружаем его
            import io
            audio_segment = AudioSegment.from_wav(io.BytesIO(pcm_data))
        else:
            # Это сырые PCM данные
            audio_segment = AudioSegment(
                data=pcm_data,
                sample_width=2,      # 16-bit PCM
                frame_rate=24000,    # 24kHz частота дискретизации
                channels=1           # Моно
            )

        logging.info("Конвертация в OGG/OPUS...")
        # Оборачиваем блокирующий вызов экспорта в to_thread, так как он работает с файловым объектом
        await asyncio.to_thread(
            audio_segment.export, out_f=output_file_object, format="ogg", codec="libopus"
        )

        logging.info(f"Аудио успешно сконвертировано. Размер PCM данных: {len(pcm_data)} байт")
        return True

    except APIError as e:
        logging.error(f"Ошибка TTS API: {e}")
        return False
    except Exception as e:
        logging.error(f"Ошибка при создании голосового сообщения: {e}", exc_info=True)
        return False

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(APIError), # Используем актуальный класс ошибок
    reraise=True
)
async def call_tts_api_with_retry(text_to_speak: str):
    """
    Выполняет асинхронный вызов к TTS API Gemini с логикой повторных попыток.
    """
    logging.info("Попытка вызова TTS API...")
    try:
        # Используем актуальную структуру API согласно документации
        response = await TTS_CLIENT.aio.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text_to_speak,
            config=genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=genai_types.SpeechConfig(
                    voice_config=genai_types.VoiceConfig(
                        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                            voice_name='zephyr',
                        )
                    )
                ),
            )
        )
        return response
    except APIError as e:
        logging.warning(f"Ошибка TTS API: {e}. Повторная попытка...")
        raise
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при вызове TTS API: {e}", exc_info=True)
        raise

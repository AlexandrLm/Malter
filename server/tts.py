import os
import asyncio
from google import genai
from google.genai import types as genai_types
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

async def create_telegram_voice_message(text_to_speak, output_filename):
    """
    Асинхронно генерирует аудио из текста и сохраняет его в формате OGG/OPUS,
    подходящем для голосовых сообщений Telegram.
    """
    try:
        logging.info(f"Генерация аудио для текста: '{text_to_speak}'...")
        
        response = await call_tts_api_with_retry(text_to_speak)

        pcm_data = response.candidates[0].content.parts[0].inline_data.data
        logging.info("Аудиоданные получены.")
        audio_segment = AudioSegment(
            data=pcm_data,
            sample_width=2,
            frame_rate=24000,
            channels=1
        )

        logging.info(f"Конвертация в OGG/OPUS и сохранение в '{output_filename}'...")
        # Оборачиваем блокирующий вызов экспорта файла в to_thread
        await asyncio.to_thread(
            audio_segment.export, out_f=output_filename, format="ogg", codec="libopus"
        )

        logging.info(f"Аудио успешно сохранено в '{output_filename}'.")
        return True

    except Exception as e:
        logging.error(f"Ошибка при создании голосового сообщения: {e}", exc_info=True)
        return False

# --- Пример использования ---
async def main():
    text_ru = "Зевая: Я совершенно не хочу вылезать из-под одеяла. Может, закажем еду?"
    filename_ru = "voice_ru.ogg"
    await create_telegram_voice_message(text_ru, filename_ru)

if __name__ == "__main__":
    asyncio.run(main())

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    # retry=retry_if_exception_type(genai_types.generation_types.InternalServerError),
    reraise=True
)
async def call_tts_api_with_retry(text_to_speak: str):
    """
    Выполняет вызов к TTS API Gemini с логикой повторных попыток.
    """
    logging.info("Попытка вызова TTS API...")
    try:
        client = genai.Client()
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash-preview-tts",
            contents=text_to_speak,
            config=genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=genai_types.SpeechConfig(
                    voice_config=genai_types.VoiceConfig(
                        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                            voice_name='Leda',
                        )
                    )
                ),
            )
        )
        return response
    except genai_types.generation_types.InternalServerError as e:
        logging.warning(f"Внутренняя ошибка TTS API: {e}. Повторная попытка...")
        raise
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при вызове TTS API: {e}", exc_info=True)
        raise
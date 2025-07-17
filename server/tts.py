import os
from google import genai
from google.genai import types
from pydub import AudioSegment

def create_telegram_voice_message(text_to_speak, output_filename):
    """
    Генерирует аудио из текста и сохраняет его в формате OGG/OPUS,
    подходящем для голосовых сообщений Telegram.
    """
    try:
        print(f"Генерация аудио для текста: '{text_to_speak}'...")
        client = genai.Client()

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text_to_speak,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            # Вы можете менять голоса, например: 'Kore', 'Larc', 'Pace'
                            voice_name='Leda', 
                        )
                    )
                ),
            )
        )

        # Получаем сырые аудиоданные (PCM)
        pcm_data = response.candidates[0].content.parts[0].inline_data.data
        print("Аудиоданные получены.")
        audio_segment = AudioSegment(
            data=pcm_data,
            sample_width=2,
            frame_rate=24000,
            channels=1
        )

        print(f"Конвертация в OGG/OPUS и сохранение в файл '{output_filename}'...")
        audio_segment.export(output_filename, format="ogg", codec="libopus")

        print(f"Файл '{output_filename}' успешно создан и готов к отправке в Telegram.")
        return True

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return False

# --- Пример использования ---
if __name__ == "__main__":
    text_ru = "Зевая: Я совершенно не хочу вылезать из-под одеяла. Может, закажем еду?"
    filename_ru = "voice_ru.ogg"
    create_telegram_voice_message(text_ru, filename_ru)
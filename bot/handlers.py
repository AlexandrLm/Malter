import httpx
import asyncio
import logging
import base64
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# Импортируем URL из конфига, а не хардкодим
from config import API_BASE_URL, DAILY_MESSAGE_LIMIT

router = Router()
tf = TimezoneFinder()
geolocator = Nominatim(user_agent="EvolveAI")

# ### Константы для управления "печатью" ###
TYPING_SPEED_CPS = 15  # Символов в секунду
MIN_TYPING_DELAY = 0.5 # Минимальная задержка в секундах
MAX_TYPING_DELAY = 4.0 # Максимальная задержка в секундах

# --- FSM для анкеты ---

class ProfileStates(StatesGroup):
    name = State()
    gender = State()
    city = State()

# --- Клавиатуры ---
gender_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# --- Функции-валидаторы ---
def is_valid_name(name: str) -> bool:
    """Проверяет, что имя состоит только из букв и имеет длину от 2 до 30 символов."""
    return name.isalpha() and 2 <= len(name) <= 30

def is_valid_city(city: str) -> bool:
    """Проверяет, что название города имеет длину от 2 до 50 символов."""
    return 2 <= len(city) <= 50


async def simulate_typing_and_send(message: types.Message, text: str):
    """
    Имитирует набор текста с реалистичной скоростью и отправляет сообщение.
    """
    # 1. Рассчитываем задержку на основе длины текста
    delay = len(text) / TYPING_SPEED_CPS
    
    # 2. Ограничиваем задержку минимальным и максимальным значениями
    clamped_delay = max(MIN_TYPING_DELAY, min(delay, MAX_TYPING_DELAY))

    # 3. Отправляем экшен "печатает", ждем и отправляем сообщение
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(clamped_delay)
    await message.answer(text)


async def send_typing_response(message: types.Message, text: str):
    """
    Отправляет ответ, разделяя его по '||' и имитируя набор для каждой части.
    """
    parts = text.split('||')
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        # Отправляем первую часть с имитацией набора
        await simulate_typing_and_send(message, part)

        # Если есть следующая часть, делаем небольшую паузу "на подумать"
        if i < len(parts) - 1:
            await asyncio.sleep(1.2)


# --- API-клиент с Retry ---

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True
)
async def make_api_request(client: httpx.AsyncClient, method: str, endpoint: str, **kwargs):
    """Централизованная функция для выполнения запросов к API."""
    url = f"{API_BASE_URL}{endpoint}"
    logging.info(f"Вызов API: {method.upper()} {url}")
    response = await client.request(method, url, **kwargs)
    response.raise_for_status()
    return response

# --- Обработчики команд ---

@router.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    user_id = message.from_user.id
    try:
        response = await make_api_request(client, "get", f"/profile/{user_id}")
        if response.status_code == 200 and response.json() is not None:
            await message.answer("Привет, милый. Я так рада, что ты написал. Уже успела соскучиться.")
            await state.clear()
        else:
            # Начинаем анкетирование
            await message.answer("Привет, как тебя зовут?")
            await state.set_state(ProfileStates.name)
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f"API connection error in /start for user {user_id} after retries: {e}")
        await message.answer("Ой, у меня что-то с интернетом... Не могу проверить, знакомы ли мы. Попробуй чуть позже.")
    except Exception as e:
        logging.error(f"Unexpected error in /start for user {user_id}: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка. Попробуйте еще раз позже.")


@router.message(Command("reset"))
async def command_reset(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    user_id = message.from_user.id
    try:
        await make_api_request(client, "delete", f"/profile/{user_id}")
        await message.answer("Хм, хочешь начать все с чистого листа? Хорошо...")
        await asyncio.sleep(1)
        
        await message.answer("Давай начнем сначала. Как тебя зовут?")
        await state.set_state(ProfileStates.name)
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f"API connection error in /reset for user {user_id} after retries: {e}")
        await message.answer("Телефон глючит, не могу ничего удалить... Попробуй позже, пожалуйста.")
    except Exception as e:
        logging.error(f"Unexpected error in /reset for user {user_id}: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка. Попробуйте еще раз позже.")

@router.message(Command("status"))
async def command_status(message: types.Message, client: httpx.AsyncClient):
    """Показывает пользователю его текущий статус подписки."""
    user_id = message.from_user.id
    try:
        response = await make_api_request(client, "get", f"/profile/status/{user_id}")
        if response.status_code == 200:
            data = response.json()
            if data:
                plan = data['subscription_plan']
                expires = data['subscription_expires']
                count = data['daily_message_count']
                limit = DAILY_MESSAGE_LIMIT
                
                status_text = f"Твой тариф: *{plan.capitalize()}\n"
                if plan == 'premium' and expires:
                    status_text += f"Подписка действует до: {expires.split('T')[0]}\n"
                elif plan == 'free':
                    status_text += f"Сообщений сегодня: {count}/{limit}\n"
                    status_text += "Премиум-пользователи не имеют ограничений по сообщениям и получают доступ к продвинутым функциям!"
                
                await message.answer(status_text, parse_mode='Markdown')
            else:
                await message.answer("Профиль не найден. Пожалуйста, используй /start.")
        else:
            await message.answer("Не удалось получить статус. Попробуй позже.")
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f"API connection error in /status for user {user_id} after retries: {e}")
        await message.answer("Ой, у меня что-то с интернетом... Попробуй чуть позже.")
    except Exception as e:
        logging.error(f"Unexpected error in /status for user {user_id}: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка. Попробуйте еще раз позже.")

@router.message(Command("premium"))
async def command_premium(message: types.Message):
    """Показывает информацию о премиум-подписке."""
    premium_info = (
        "✨ *Премиум-подписка EvolveAI* ✨\n\n"
        "Разблокируй все возможности общения!\n\n"
        f" Unlimited общение без дневных лимитов (бесплатные пользователи могут отправлять до {DAILY_MESSAGE_LIMIT} сообщений в день).\n"
        " 🧠 Продвинутую память (суммаризация диалогов).\n"
        " 📷 Возможность отправлять фото и получать комментарии.\n"
        " 🎙️ Голосовые сообщения от ИИ-компаньона.\n"
        " 💬 Приоритет в обработке запросов.\n\n"
        "Сейчас эта функция в разработке. Следи за обновлениями!"
    )
    await message.answer(premium_info, parse_mode='Markdown')

# --- Обработчики анкеты с валидацией ---

@router.message(ProfileStates.name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    if is_valid_name(message.text):
        await state.update_data(name=message.text)
        await message.answer(
            f"Хорошо, {message.text}. А ты мужчина или женщина? Мне это нужно, чтобы правильно к тебе обращаться.",
            reply_markup=gender_keyboard
        )
        await state.set_state(ProfileStates.gender)
    else:
        await message.answer("Хм, что-то не похоже на имя. Попробуй еще раз. Используй только буквы, пожалуйста.")

@router.message(ProfileStates.name)
async def process_name_invalid(message: types.Message):
    await message.answer("Пожалуйста, отправь свое имя в виде текста.")


@router.message(ProfileStates.gender, F.text.in_(["Мужчина", "Женщина"]))
async def process_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text.lower())
    await message.answer(
        "И последний вопрос, чтобы я не путалась во времени... В каком городе ты живешь?",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(ProfileStates.city)

@router.message(ProfileStates.gender)
async def process_gender_invalid(message: types.Message):
    await message.answer("Пожалуйста, выбери один из вариантов на клавиатуре.")


@router.message(ProfileStates.city, F.text)
async def process_city(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    if not is_valid_city(message.text):
        await message.answer("Название города кажется слишком коротким. Попробуй еще раз.")
        return

    try:
        location = await asyncio.to_thread(geolocator.geocode, message.text)
        if not location:
            await message.answer("Не могу найти такой город... Попробуй, пожалуйста, ввести его еще раз, возможно, с уточнением (например, 'Москва, Россия').")
            return
        timezone = await asyncio.to_thread(tf.timezone_at, lng=location.longitude, lat=location.latitude)
    except Exception as e:
        logging.error(f"Could not determine timezone for {message.text}: {e}")
        timezone = "UTC" # Фоллбэк

    await state.update_data(city=message.text, timezone=timezone)
    user_data = await state.get_data()

    profile_data = {
        "name": user_data.get("name"),
        "gender": user_data.get("gender"),
        "city": user_data.get("city"),
        "timezone": user_data.get("timezone")
    }

    try:
        await make_api_request(
            client,
            "post",
            "/profile",
            json={"user_id": message.from_user.id, "data": profile_data}
        )
        await state.clear()
        await message.answer("Привет!")
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f"API connection error saving profile for user {message.from_user.id} after retries: {e}")
        await message.answer("Ой, не могу сохранить... что-то с телефоном. Давай попробуем позже, нажми /reset.")
    except Exception as e:
        logging.error(f"Unexpected error saving profile for user {message.from_user.id}: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка при сохранении профиля. Попробуйте еще раз позже.")

@router.message(ProfileStates.city)
async def process_city_invalid(message: types.Message):
    await message.answer("Пожалуйста, отправь название города в виде текста.")


# --- Основной хендлер для текстовых и фото-сообщений ---
async def process_image(message: types.Message) -> str | None:
    """
    Обрабатывает изображение из сообщения и возвращает его в формате base64.
    
    Args:
        message (types.Message): Сообщение с изображением.
        
    Returns:
        str | None: Изображение в формате base64 или None, если изображение не найдено.
    """
    if not message.photo:
        return None
        
    try:
        # Выбираем лучшее качество (последнее в списке)
        photo = message.photo[-1]
        # Скачиваем фото в память
        photo_bytes = await message.bot.download(photo.file_id)
        if photo_bytes:
            return base64.b64encode(photo_bytes.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error processing image for user {message.from_user.id}: {e}")
        return None
        
    return None


async def send_response(message: types.Message, response_data: dict):
    """
    Отправляет ответ пользователю, включая обработку голосовых сообщений.
    
    Args:
        message (types.Message): Исходное сообщение пользователя.
        response_data (dict): Данные ответа от API.
    """
    voice_bytes_b64 = response_data.get("voice_message")
    if voice_bytes_b64:
        try:
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)
            voice_bytes = base64.b64decode(voice_bytes_b64)
            await message.answer_voice(types.BufferedInputFile(voice_bytes, "voice.ogg"))
        except Exception as e:
            logging.error(f"Error sending voice message to user {message.from_user.id}: {e}")
            await message.answer("Хо хотела записать голосовое, но что-то с телефоном... короче, я так по тебе соскучилась!")
    else:
        await send_typing_response(message, response_data["response_text"])


@router.message(F.text | F.photo)
async def handle_message(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    if await state.get_state() is not None:
        await message.answer("Подожди, давай сначала я все вспомню...")
        return

    user_id = message.from_user.id
    image_data_b64 = None

    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        # Обработка изображения, если оно есть
        image_data_b64 = await process_image(message)

        # Текст сообщения (или подпись к фото)
        text = message.text or message.caption or ""

        payload = {
            "user_id": user_id,
            "message": text,
            "timestamp": message.date.isoformat(),
            "image_data": image_data_b64 # Добавляем base64 картинки
        }

        response = await make_api_request(
            client,
            "post",
            "/chat",
            json=payload,
            timeout=180.0 # Увеличиваем таймаут для обработки изображений
        )

        data = response.json()
        await send_response(message, data)

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f"API connection error in handle_message for user {user_id} after retries: {e}")
        await message.answer("Милый, у меня связь пропала... Не вижу твое сообщение. Напиши, как только интернет появится.")
    except ValueError as e:
        logging.error(f"ValueError in handle_message for user {user_id}: {e}")
        await message.answer("Произошла ошибка обработки данных. Попробуйте еще раз.")
    except Exception as e:
        logging.error(f"An unexpected error occurred in handle_message for user {user_id}: {e}", exc_info=True)
        await message.answer("Ой, что-то пошло не так... Попробуй еще раз.")
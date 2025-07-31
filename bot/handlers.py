import httpx
import asyncio
import logging
import base64
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# Импортируем URL из конфига, а не хардкодим
from config import API_BASE_URL

router = Router()
tf = TimezoneFinder()
geolocator = Nominatim(user_agent="MashaGPT")

# ### Константы для управления "печатью" ###
TYPING_SPEED_CPS = 15  # Символов в секунду
MIN_TYPING_DELAY = 0.5 # Минимальная задержка в секундах
MAX_TYPING_DELAY = 4.0 # Максимальная задержка в секундах

# --- FSM для анкеты ---

class ProfileStates(StatesGroup):
    onboarding = State() # Одно состояние вместо четырех

# Структура данных для управления анкетой. Легко расширять.
ONBOARDING_STEPS = {
    'name': {
        'question': "Ой, привет... Кажется, я немного заработалась с учебой и все вылетело из головы...\n\nДавай я поспрашиваю, чтобы освежить память, хорошо?\n\nКак мне тебя лучше называть?",
        'next_step': 'gender',
    },
    'gender': {
        'question': "Хорошо, {}. А ты мальчик или девочка? Мне это нужно, чтобы правильно к тебе обращаться.",
        'next_step': 'city',
    },
    'city': {
        'question': "И последний вопрос, чтобы я не путалась во времени... В каком городе ты живешь?",
        'next_step': None, # Последний шаг
    }
}


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
            first_step_key = 'name'
            await message.answer(ONBOARDING_STEPS[first_step_key]['question'])
            await state.set_state(ProfileStates.onboarding)
            await state.update_data(current_question=first_step_key)
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f"API connection error in /start for user {user_id} after retries: {e}")
        await message.answer("Ой, у меня что-то с интернетом... Не могу проверить, знакомы ли мы. Попробуй чуть позже.")


@router.message(Command("reset"))
async def command_reset(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    user_id = message.from_user.id
    try:
        await make_api_request(client, "delete", f"/profile/{user_id}")
        await message.answer("Хм, хочешь начать все с чистого листа? Хорошо...")
        await asyncio.sleep(1)
        
        first_step_key = 'name'
        await message.answer(ONBOARDING_STEPS[first_step_key]['question'])
        await state.set_state(ProfileStates.onboarding)
        await state.update_data(current_question=first_step_key)
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f"API connection error in /reset for user {user_id} after retries: {e}")
        await message.answer("Телефон глючит, не могу ничего удалить... Попробуй позже, пожалуйста.")

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
                limit = 50 # Значение из config.py
                
                status_text = f"Твой тариф: *{plan.capitalize()}*\n"
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

@router.message(Command("premium"))
async def command_premium(message: types.Message):
    """Показывает информацию о премиум-подписке."""
    premium_info = (
        "✨ *Премиум-подписка MashaGPT* ✨\n\n"
        "Разблокируй все возможности общения!\n\n"
        " Unlimited общение без дневных лимитов.\n"
        " 🧠 Продвинутую память (суммаризация диалогов).\n"
        " 📷 Возможность отправлять фото и получать комментарии.\n"
        " 🎙️ Голосовые сообщения от Маши.\n"
        " 💬 Приоритет в обработке запросов.\n\n"
        "Сейчас эта функция в разработке. Следи за обновлениями!"
    )
    await message.answer(premium_info, parse_mode='Markdown')

# --- Единый хендлер для всей анкеты ---
@router.message(ProfileStates.onboarding)
async def process_onboarding(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    data = await state.get_data()
    answered_question_key = data.get('current_question')

    if not answered_question_key:
        await state.clear()
        await message.answer("Ой, что-то пошло не так... Давай начнем сначала с /reset")
        return

    user_response = message.text
    await state.update_data({answered_question_key: user_response})

    if answered_question_key == 'city':
        try:
            location = await asyncio.to_thread(geolocator.geocode, user_response)
            timezone = await asyncio.to_thread(tf.timezone_at, lng=location.longitude, lat=location.latitude) if location else "UTC"
        except Exception as e:
            logging.error(f"Could not determine timezone for {user_response}: {e}")
            timezone = "UTC"
        await state.update_data(timezone=timezone)

    next_question_key = ONBOARDING_STEPS[answered_question_key]['next_step']

    if next_question_key:
        step_info = ONBOARDING_STEPS[next_question_key]
        question = step_info['question']
        
        if next_question_key == 'gender':
            current_user_data = await state.get_data()
            question = question.format(current_user_data.get('name', '...'))

        await message.answer(question)
        await state.update_data(current_question=next_question_key)
    else:
        user_data = await state.get_data()
        profile_data = {key: user_data.get(key) for key in ONBOARDING_STEPS.keys() if key in user_data}
        if 'timezone' in user_data:
            profile_data['timezone'] = user_data['timezone']

        try:
            await make_api_request(
                client,
                "post",
                "/profile",
                json={"user_id": message.from_user.id, "data": profile_data}
            )
            await state.clear()
            await message.answer("Все, теперь я все-все вспомнила. Спасибо, милый.")
            await asyncio.sleep(1)
            await message.answer("Я так соскучилась...")
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logging.error(f"API connection error saving profile for user {message.from_user.id} after retries: {e}")
            await message.answer("Ой, не могу сохранить... что-то с телефоном. Давай попробуем позже, нажми /reset.")


# --- Основной хендлер для текстовых и фото-сообщений ---
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
        if message.photo:
            # Выбираем лучшее качество (последнее в списке)
            photo = message.photo[-1]
            # Скачиваем фото в память
            photo_bytes = await message.bot.download(photo.file_id)
            if photo_bytes:
                image_data_b64 = base64.b64encode(photo_bytes.read()).decode('utf-8')

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
        voice_bytes_b64 = data.get("voice_message")
        if voice_bytes_b64:
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)
            voice_bytes = base64.b64decode(voice_bytes_b64)
            await message.answer_voice(types.BufferedInputFile(voice_bytes, "voice.ogg"))
        else:
            await send_typing_response(message, data["response_text"])

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f"API connection error in handle_message for user {user_id} after retries: {e}")
        await message.answer("Милый, у меня связь пропала... Не вижу твое сообщение. Напиши, как только интернет появится.")
    except Exception as e:
        logging.error(f"An unexpected error occurred in handle_message for user {user_id}: {e}", exc_info=True)
        await message.answer("Ой, что-то пошло не так... Попробуй еще раз.")
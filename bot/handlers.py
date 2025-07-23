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
        'next_step': 'occupation',
    },
    'occupation': {
        'question': "Точно, {}... Вспомнила) А напомни, чем ты сейчас занимаешься, родной?",
        'next_step': 'hobby',
    },
    'hobby': {
        'question': "Поняла... А что мы с тобой больше всего любили делать вместе?",
        'next_step': 'place',
    },
    'place': {
        'question': "Дааа... точно. А было у нас какое-то особенное место в городе?",
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


@router.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    user_id = message.from_user.id
    try:
        response = await client.get(f"{API_BASE_URL}/profile/{user_id}")
        if response.status_code == 200 and response.json() is not None:
            await message.answer("Привет, милый. Я так рада, что ты написал. Уже успела соскучиться.")
            await state.clear()
        else:
            # Начинаем анкетирование
            first_step_key = 'name'
            await message.answer(ONBOARDING_STEPS[first_step_key]['question'])
            await state.set_state(ProfileStates.onboarding)
            await state.update_data(current_question=first_step_key) # Сохраняем текущий шаг
    except httpx.RequestError as e:
        logging.error(f"API connection error in /start for user {user_id}: {e}")
        await message.answer("Ой, у меня что-то с интернетом... Не могу проверить, знакомы ли мы. Попробуй чуть позже.")


@router.message(Command("reset"))
async def command_reset(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    user_id = message.from_user.id
    try:
        await client.delete(f"{API_BASE_URL}/profile/{user_id}")
        await message.answer("Хм, хочешь начать все с чистого листа? Хорошо...")
        await asyncio.sleep(1)
        
        # Начинаем анкетирование заново
        first_step_key = 'name'
        await message.answer(ONBOARDING_STEPS[first_step_key]['question'])
        await state.set_state(ProfileStates.onboarding)
        await state.update_data(current_question=first_step_key) # Сохраняем текущий шаг
    except httpx.RequestError as e:
        logging.error(f"API connection error in /reset for user {user_id}: {e}")
        await message.answer("Телефон глючит, не могу ничего удалить... Попробуй позже, пожалуйста.")


# --- Единый хендлер для всей анкеты ---
@router.message(ProfileStates.onboarding)
async def process_onboarding(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    data = await state.get_data()
    answered_question_key = data.get('current_question')

    if not answered_question_key:
        await state.clear()
        await message.answer("Ой, что-то пошло не так... Давай начнем сначала с /reset")
        return

    # Сохраняем ответ
    user_response = message.text
    await state.update_data({answered_question_key: user_response})

    # Если ответили на вопрос о городе, определяем таймзону
    if answered_question_key == 'city':
        try:
            location = await asyncio.to_thread(geolocator.geocode, user_response)
            timezone = await asyncio.to_thread(tf.timezone_at, lng=location.longitude, lat=location.latitude) if location else "UTC"
        except Exception as e:
            logging.error(f"Could not determine timezone for {user_response}: {e}")
            timezone = "UTC"
        await state.update_data(timezone=timezone)

    # Определяем следующий шаг
    next_question_key = ONBOARDING_STEPS[answered_question_key]['next_step']

    if next_question_key:
        # Задаем следующий вопрос
        step_info = ONBOARDING_STEPS[next_question_key]
        question = step_info['question']
        
        if next_question_key == 'occupation':
            current_user_data = await state.get_data()
            question = question.format(current_user_data.get('name', '...'))

        await message.answer(question)
        await state.update_data(current_question=next_question_key)
    else:
        # Это был последний вопрос, сохраняем профиль
        user_data = await state.get_data()
        profile_data = {key: user_data.get(key) for key in ONBOARDING_STEPS.keys() if key in user_data}
        if 'timezone' in user_data:
            profile_data['timezone'] = user_data['timezone']

        try:
            await client.post(f"{API_BASE_URL}/profile", json={"user_id": message.from_user.id, "data": profile_data})
            await state.clear()
            await message.answer("Все, теперь я все-все вспомнила. Спасибо, милый.")
            await asyncio.sleep(1)
            await message.answer("Я так соскучилась...")
        except httpx.RequestError as e:
            logging.error(f"API connection error saving profile for user {message.from_user.id}: {e}")
            await message.answer("Ой, не могу сохранить... что-то с телефоном. Давай попробуем позже, нажми /reset.")


# --- Основной хендлер для текстовых сообщений ---
@router.message(F.text)
async def handle_message(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    if await state.get_state() is not None:
        await message.answer("Подожди, давай сначала я все вспомню...")
        return
        
    user_id = message.from_user.id
    
    try:
        # Устанавливаем статус "печатает" заранее
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

        payload = {
            "user_id": message.from_user.id,
            "message": message.text,
            "timestamp": message.date.isoformat()
        }
        # Увеличиваем таймаут для долгих ответов от AI
        response = await client.post(
            f"{API_BASE_URL}/chat",
            json=payload,
            timeout=90.0
        )
        
        if response.status_code == 200:
            data = response.json()
            voice_bytes_b64 = data.get("voice_message")
            if voice_bytes_b64:
                await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)
                # API возвращает байты в виде строки base64, декодируем их
                voice_bytes = base64.b64decode(voice_bytes_b64)
                await message.answer_voice(types.BufferedInputFile(voice_bytes, "voice.ogg"))
            else:
                await send_typing_response(message, data["response_text"])
        else:
            logging.warning(f"API returned status {response.status_code} for user {user_id}")
            await message.answer("Что-то телефон глючит, не могу нормально напечатать. Попробуй еще раз, пожалуйста.")

    except httpx.RequestError as e:
        logging.error(f"API connection error in handle_message for user {user_id}: {e}")
        await message.answer("Милый, у меня связь пропала... Не вижу твое сообщение. Напиши, как только интернет появится.")
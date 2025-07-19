import httpx
import asyncio
import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction

# Импортируем URL из конфига, а не хардкодим
from config import API_BASE_URL

router = Router()

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
        'next_step': None, # Последний шаг
    }
}


async def send_typing_response(message: types.Message, text: str):
    """
    Вспомогательная функция для отправки сообщений с имитацией набора текста
    и обработкой разделителя '||'.
    """
    parts = text.split('||')
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        if i > 0:
            delay = max(1.0, min(len(part) / 15, 4.0)) # Упрощенная и более предсказуемая задержка
            await asyncio.sleep(delay)

        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        await asyncio.sleep(0.3) # Короткая пауза для реалистичности
        await message.answer(part)


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
            await state.update_data(step='occupation') # Сохраняем следующий шаг
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
        await state.update_data(step='occupation') # Сохраняем следующий шаг
    except httpx.RequestError as e:
        logging.error(f"API connection error in /reset for user {user_id}: {e}")
        await message.answer("Телефон глючит, не могу ничего удалить... Попробуй позже, пожалуйста.")


# --- Единый хендлер для всей анкеты ---
@router.message(ProfileStates.onboarding)
async def process_onboarding(message: types.Message, state: FSMContext, client: httpx.AsyncClient):
    current_data = await state.get_data()
    # Определяем, какой ключ мы сохраняли на предыдущем шаге
    previous_step_key = list(ONBOARDING_STEPS.keys())[list(ONBOARDING_STEPS.values()).index(next(v for v in ONBOARDING_STEPS.values() if v['next_step'] == current_data.get('step')))]
    
    # Сохраняем ответ пользователя
    await state.update_data({previous_step_key: message.text})
    
    current_step_key = current_data.get('step')
    step_info = ONBOARDING_STEPS[current_step_key]
    
    # Задаем следующий вопрос
    question = step_info['question']
    if '{}' in question: # Форматируем вопрос, если нужно (для имени)
        question = question.format(message.text)
    await message.answer(question)
    
    next_step_key = step_info['next_step']
    if next_step_key:
        # Переходим к следующему шагу
        await state.update_data(step=next_step_key)
    else:
        # Это был последний шаг, сохраняем профиль
        user_data = await state.get_data()
        profile_data = {key: user_data[key] for key in ONBOARDING_STEPS.keys()}
        
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
            "message": message.text
        }
        # Увеличиваем таймаут для долгих ответов от AI
        response = await client.post(
            f"{API_BASE_URL}/chat",
            json=payload,
            timeout=90.0
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("voice_message"):
                await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)
                # Вместо еще одного запроса, предполагаем, что бэкенд вернет base64 или байты
                # Но если бэкенд отдает URL, то ваш код с httpx.get() корректен.
                voice_bytes = httpx.get(data["voice_message"]).content # Оставляем как есть
                await message.answer_voice(types.BufferedInputFile(voice_bytes, "voice.ogg"))
            else:
                await send_typing_response(message, data["response_text"])
        else:
            logging.warning(f"API returned status {response.status_code} for user {user_id}")
            await message.answer("Что-то телефон глючит, не могу нормально напечатать. Попробуй еще раз, пожалуйста.")

    except httpx.RequestError as e:
        logging.error(f"API connection error in handle_message for user {user_id}: {e}")
        await message.answer("Милый, у меня связь пропала... Не вижу твое сообщение. Напиши, как только интернет появится.")
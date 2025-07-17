import httpx
import asyncio
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction

API_BASE_URL = "http://127.0.0.1:8000"

router = Router()

class ProfileStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_occupation = State()
    waiting_for_hobby = State()
    waiting_for_place = State()

async def get_profile(user_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/profile/{user_id}")
        if response.status_code == 200 and response.json() is not None:
            return response.json()
        return None

@router.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext):
    profile = await get_profile(message.from_user.id)
    if profile:
        await message.answer("Привет, милый. Я так рада, что ты написал. Уже успела соскучиться.")
    else:
        await message.answer("Ой, привет... Кажется, я немного заработалась с учебой и все вылетело из головы...")
        await asyncio.sleep(1)
        await message.answer("Давай я поспрашиваю, чтобы освежить память, хорошо?")
        await asyncio.sleep(1)
        await message.answer("Как мне тебя лучше называть?")
        await state.set_state(ProfileStates.waiting_for_name)

@router.message(Command("reset"))
async def command_reset(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    async with httpx.AsyncClient() as client:
        await client.delete(f"{API_BASE_URL}/profile/{user_id}")
    
    await message.answer("Хм, хочешь начать все с чистого листа? Хорошо...")
    await asyncio.sleep(1)
    await message.answer("Тогда напомни, как мне тебя называть?")
    await state.set_state(ProfileStates.waiting_for_name)

async def process_profile_field(message: types.Message, state: FSMContext, field_name: str, next_question: str, next_state: State):
    await state.update_data({field_name: message.text})
    await message.answer(next_question)
    await state.set_state(next_state)

@router.message(ProfileStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await process_profile_field(message, state, "name", f"Точно, {message.text}... Вспомнила) А напомни, чем ты сейчас занимаешься, родной?", ProfileStates.waiting_for_occupation)

@router.message(ProfileStates.waiting_for_occupation)
async def process_occupation(message: types.Message, state: FSMContext):
    await process_profile_field(message, state, "occupation", "Поняла... А что мы с тобой больше всего любили делать вместе?", ProfileStates.waiting_for_hobby)

@router.message(ProfileStates.waiting_for_hobby)
async def process_hobby(message: types.Message, state: FSMContext):
    await process_profile_field(message, state, "hobby", "Дааа... точно. А было у нас какое-то особенное место в городе?", ProfileStates.waiting_for_place)

@router.message(ProfileStates.waiting_for_place)
async def process_place(message: types.Message, state: FSMContext):
    await state.update_data(place=message.text)
    user_data = await state.get_data()
    
    async with httpx.AsyncClient() as client:
        await client.post(f"{API_BASE_URL}/profile", json={"user_id": message.from_user.id, "data": user_data})
    
    await state.clear()
    
    await message.answer("Все, теперь я все-все вспомнила. Спасибо, милый.")
    await asyncio.sleep(1)
    await message.answer("Я так соскучилась...")

@router.message(F.text)
async def handle_message(message: types.Message, state: FSMContext):
    if await state.get_state() is not None:
        await message.answer("Подожди, давай сначала я все вспомню...")
        return
        
    profile = await get_profile(message.from_user.id)
    if not profile:
        await message.answer("Ой, привет... Кажется, я тебя не помню. Нажми /start, чтобы мы познакомились.")
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(f"{API_BASE_URL}/chat", json={"user_id": message.from_user.id, "message": message.text})
    
    if response.status_code == 200:
        data = response.json()
        if data.get("voice_message"):
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)
            voice_bytes = httpx.get(data["voice_message"]).content
            await message.answer_voice(types.BufferedInputFile(voice_bytes, "voice.ogg"))
        else:
            parts = data["response_text"].split('||')
            for i, part in enumerate(parts):
                part = part.strip()
                if not part: continue
                
                # Перед отправкой имитируем набор текста
                if i > 0: # Не делаем задержку перед самым первым сообщением
                    # Динамическая задержка: ~20 символов в секунду + небольшая случайность
                    delay = len(part) / 20 + (0.5 * (i % 2)) # Добавляем 0.5с к каждой второй паузе для ритма
                    delay = max(1.0, min(delay, 4.0)) # Ограничиваем задержку от 1 до 4 секунд
                    await asyncio.sleep(delay)

                await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                await asyncio.sleep(0.5) # Короткая пауза после "печатает..."
                await message.answer(part)
    else:
        await message.answer("Что-то телефон глючит, не могу нормально напечатать. Попробуй еще раз, пожалуйста.")
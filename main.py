import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile
import yt_dlp

# Токен вашего бота (получите у @BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Определение состояний диалога
class VideoDownloadStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_start = State()
    waiting_for_end = State()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Привет! Отправь мне ссылку на видео (YouTube и др.).")
    await state.set_state(VideoDownloadStates.waiting_for_url)

# 1. Получаем ссылку
@dp.message(VideoDownloadStates.waiting_for_url, F.text)
async def process_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith("http"):
        await message.answer("❌ Это не похоже на ссылку. Попробуйте еще раз.")
        return
        
    await state.update_data(url=url)
    await message.answer("⏱ Теперь введите **время начала** отрезка (например, 00:15 или 01:23:45, или просто в секундах):")
    await state.set_state(VideoDownloadStates.waiting_for_start)

# 2. Получаем время начала
@dp.message(VideoDownloadStates.waiting_for_start, F.text)
async def process_start_time(message: types.Message, state: FSMContext):
    start_time = message.text.strip()
    await state.update_data(start_time=start_time)
    await message.answer("⏱ Отлично! Теперь введвремя окончанияия** отрезка:")
    await state.set_state(VideoDownloadStates.waiting_for_end)

# 3. Получаем время конца, скачиваем отрезок и отправляем
@dp.message(VideoDownloadStates.waiting_for_end, F.text)
async def process_end_time(message: types.Message, state: FSMContext):
    end_time = message.text.strip()
    user_data = await state.get_data()
    
    url = user_data['url']
    start_time = user_data['start_time']
    
    status_message = await message.answer("⏳ Обрабатываю ваш запрос... Это может занять пару минут.")
    await state.clear()  # Сбрасываем состояние, чтобы пользователь мог делать новые запросы

    # Имя выходного файла (уникальное для каждого запроса)
    output_filename = f"clip_{message.from_user.id}_{int(asyncio.get_event_loop().time())}.mp4"

    # Настройки yt-dlp для загрузки конкретного фрагмента
    ydl_opts = {
        'format': 'mp4[height<=720]/best[ext=mp4]',  # Ограничиваем 720p, чтобы файл не весил слишком много для Telegram
        'outtmpl': output_filename,
        # Аргументы для умной нарезки ffmpeg прямо во время стриминга потока
        'download_ranges': lambda info, ctx: [{
            'start_time': parse_time_to_seconds(start_time),
            'end_time': parse_time_to_seconds(end_time),
        }],
        'force_keyframes_at_cuts': True,
        'quiet': True,
    }

    try:
        # Запуск скачивания в отдельном потоке, чтобы не блокировать бота
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, download_video, url, ydl_opts)

        if os.path.exists(output_filename):
            await status_message.edit_text("🚀 Файл готов! Отправляю в чат...")
            
            # Отправка видеофайла
            video_file = FSInputFile(output_filename)
            await message.reply_video(video=video_file, caption=f"🎬 Ваш отрезок с {start_time} по {end_time}")
            
            # Удаляем локальный файл после отправки
            os.remove(output_filename)
        else:
            await status_message.edit_text("❌ Ошибка: не удалось создать файл отрезка.")

    except Exception as e:
        await status_message.edit_text(f"❌ Произошла ошибка при обработке видео: \n{str(e)}", parse_mode="Markdown")
        if os.path.exists(output_filename):
            os.remove(output_filename)
            def download_video(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

def parse_time_to_seconds(time_str: str) -> float:
    
    try:
        if ':' not in time_str:
            return float(time_str)
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 2:  # ММ:СС
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:  # ЧЧ:ММ:СС
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception:
        return 0.0  # Возвращаем 0 в случае некорректного формата

async def main():
    print("Бот запущен и готов к работе...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

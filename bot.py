"""
Telegram Reminder Bot with AI - Fast & Beautiful
Optimized for Render.com deployment
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

import pytz
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
import httpx

# ============================================================================
# CONFIGURATION
# ============================================================================

BOT_TOKEN = "8926447955:AAEKjSAYuaAFg-8VdS5YBVYNavMwt10QrNM"
MISTRAL_API_KEY = "7eMrGygzAbBjIhIuFXDEYqrMaxpyuHh5"
DEFAULT_TIMEZONE = "Europe/Chisinau"

# Premium Emoji IDs
EMOJI = {
    "settings": "5870982283724328568",
    "profile": "5870994129244131212",
    "check": "5870633910337015697",
    "cross": "5870657884844462243",
    "edit": "5870676941614354370",
    "trash": "5870875489362513438",
    "calendar": "5890937706803894250",
    "clock": "5983150113483134607",
    "bell": "6039486778597970865",
    "gift": "6032644646587338669",
    "celebrate": "6041731551845159060",
    "back": "5893192487324880883",
    "list": "5870528606328852614",
    "smile": "5870764288364252592",
    "info": "6028435952299413210",
}

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# IN-MEMORY STORAGE
# ============================================================================

users_db: Dict[int, Dict] = {}
reminders_db: Dict[int, Dict] = {}
reminder_counter = 0

def ensure_user(user_id: int):
    """Ensure user exists"""
    if user_id not in users_db:
        users_db[user_id] = {
            "timezone": DEFAULT_TIMEZONE,
            "created_at": datetime.now().isoformat()
        }

def add_reminder(user_id: int, data: Dict[str, Any]) -> int:
    """Add reminder"""
    global reminder_counter
    reminder_counter += 1

    reminders_db[reminder_counter] = {
        "id": reminder_counter,
        "user_id": user_id,
        "title": data["title"],
        "date": data["date"],
        "time": data["time"],
        "category": data.get("category", "другое"),
        "priority": data.get("priority", "обычное"),
        "completed": False,
        "created_at": datetime.now().isoformat()
    }

    return reminder_counter

def get_user_reminders(user_id: int) -> List[Dict]:
    """Get user reminders"""
    return [r for r in reminders_db.values()
            if r["user_id"] == user_id and not r["completed"]]

def get_today_reminders(user_id: int) -> List[Dict]:
    """Get today's reminders"""
    tz = pytz.timezone(users_db.get(user_id, {}).get("timezone", DEFAULT_TIMEZONE))
    today = datetime.now(tz).strftime('%Y-%m-%d')

    return [r for r in reminders_db.values()
            if r["user_id"] == user_id and r["date"] == today and not r["completed"]]

def mark_completed(reminder_id: int):
    """Mark reminder as completed"""
    if reminder_id in reminders_db:
        reminders_db[reminder_id]["completed"] = True

def delete_reminder(reminder_id: int):
    """Delete reminder"""
    if reminder_id in reminders_db:
        del reminders_db[reminder_id]

# ============================================================================
# FSM STATES
# ============================================================================

class ReminderStates(StatesGroup):
    waiting_for_time = State()

# ============================================================================
# AI INTEGRATION
# ============================================================================

async def parse_with_ai(text: str) -> Dict[str, Any]:
    """Parse reminder with Mistral AI"""

    tz = pytz.timezone(DEFAULT_TIMEZONE)
    now = datetime.now(tz)

    system_prompt = f"""Parse reminder from user message. Current date: {now.strftime('%Y-%m-%d')}, time: {now.strftime('%H:%M')}.

Return JSON:
- title: event name
- date: YYYY-MM-DD
- time: HH:MM (24h)
- category: личное/работа/учёба/здоровье/финансы/важное/другое
- priority: обычное/важное/срочное
- needs_clarification: true if missing time
- clarification_question: question if needed

Examples:
"стрижка завтра в 15:00" -> {{"title": "стрижка", "date": "2026-06-01", "time": "15:00", "category": "личное", "priority": "обычное", "needs_clarification": false}}
"встреча 3 июня" -> {{"title": "встреча", "date": "2026-06-03", "needs_clarification": true, "clarification_question": "Во сколько напомнить?"}}"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {MISTRAL_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "mistral-small-latest",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                }
            )

            if response.status_code == 200:
                result = response.json()
                return json.loads(result["choices"][0]["message"]["content"])
    except Exception as e:
        logger.error(f"AI error: {e}")

    return {
        "needs_clarification": True,
        "clarification_question": "Не удалось распознать. Попробуйте: 'название дата время'"
    }

# ============================================================================
# KEYBOARDS
# ============================================================================

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main keyboard"""
    keyboard = {
        "keyboard": [
            [
                {"text": "Добавить напоминание", "icon_custom_emoji_id": EMOJI["calendar"]},
                {"text": "Мои напоминания", "icon_custom_emoji_id": EMOJI["list"]}
            ],
            [
                {"text": "Сегодня", "icon_custom_emoji_id": EMOJI["clock"]},
                {"text": "Настройки", "icon_custom_emoji_id": EMOJI["settings"]}
            ]
        ],
        "resize_keyboard": True
    }
    return ReplyKeyboardMarkup(**keyboard)

def get_main_menu() -> InlineKeyboardMarkup:
    """Main menu inline"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Мои напоминания", callback_data="list", icon_custom_emoji_id=EMOJI["list"]),
            InlineKeyboardButton(text="Добавить", callback_data="add", icon_custom_emoji_id=EMOJI["calendar"])
        ],
        [
            InlineKeyboardButton(text="Сегодня", callback_data="today", icon_custom_emoji_id=EMOJI["clock"]),
            InlineKeyboardButton(text="Настройки", callback_data="settings", icon_custom_emoji_id=EMOJI["settings"])
        ]
    ])

def get_reminder_actions(reminder_id: int) -> InlineKeyboardMarkup:
    """Reminder actions"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Выполнено", callback_data=f"done_{reminder_id}", icon_custom_emoji_id=EMOJI["check"]),
            InlineKeyboardButton(text="Удалить", callback_data=f"del_{reminder_id}", icon_custom_emoji_id=EMOJI["trash"])
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="list", icon_custom_emoji_id=EMOJI["back"])
        ]
    ])

# ============================================================================
# BOT SETUP
# ============================================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ============================================================================
# HANDLERS
# ============================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Start command"""
    ensure_user(message.from_user.id)

    text = f'''<b><tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> Привет! Я бот-напоминалка с ИИ.</b>

Просто напишите мне обычным текстом:
• "стрижка завтра в 15:00"
• "встреча 3 июня в 10:00"
• "купить молоко сегодня в 18:00"

<b><tg-emoji emoji-id="{EMOJI["smile"]}">🙂</tg-emoji> Я пойму и создам напоминание!</b>'''

    await message.answer(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Help command"""
    text = f'''<b><tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Как пользоваться:</b>

<b>1️⃣</b> Напишите напоминание обычным текстом
<b>2️⃣</b> Я распознаю дату, время и событие
<b>3️⃣</b> Если чего-то не хватает, я уточню

<b>Примеры:</b>
• стрижка завтра в 15:00
• встреча 3 июня
• купить молоко сегодня'''

    await message.answer(text, parse_mode=ParseMode.HTML)

@dp.message(F.text == "Мои напоминания")
@dp.callback_query(F.data == "list")
async def show_reminders(event: Message | CallbackQuery):
    """Show reminders"""
    user_id = event.from_user.id
    reminders = get_user_reminders(user_id)

    if not reminders:
        text = f'<b><tg-emoji emoji-id="{EMOJI["list"]}">📁</tg-emoji> У вас пока нет напоминаний</b>'
    else:
        text = f'<b><tg-emoji emoji-id="{EMOJI["list"]}">📁</tg-emoji> Ваши напоминания:</b>\n\n'
        for r in reminders[:10]:  # Limit to 10
            text += f'<b><tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> {r["title"]}</b>\n'
            text += f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> {r["date"]} в {r["time"]}\n\n'

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_menu())
        await event.answer()
    else:
        await event.answer(text, parse_mode=ParseMode.HTML)

@dp.message(F.text == "Сегодня")
@dp.callback_query(F.data == "today")
async def show_today(event: Message | CallbackQuery):
    """Show today's reminders"""
    user_id = event.from_user.id
    reminders = get_today_reminders(user_id)

    if not reminders:
        text = f'<b><tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> На сегодня напоминаний нет</b>'
    else:
        text = f'<b><tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> Задачи на сегодня:</b>\n\n'
        for r in reminders:
            text += f'<b>{r["title"]}</b> в {r["time"]}\n'

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_menu())
        await event.answer()
    else:
        await event.answer(text, parse_mode=ParseMode.HTML)

@dp.message(F.text == "Настройки")
@dp.callback_query(F.data == "settings")
async def show_settings(event: Message | CallbackQuery):
    """Show settings"""
    text = f'<b><tg-emoji emoji-id="{EMOJI["settings"]}">⚙</tg-emoji> Настройки</b>\n\nЧасовой пояс: {DEFAULT_TIMEZONE}'

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_menu())
        await event.answer()
    else:
        await event.answer(text, parse_mode=ParseMode.HTML)

@dp.message(F.text == "Добавить напоминание")
@dp.callback_query(F.data == "add")
async def add_reminder_prompt(event: Message | CallbackQuery):
    """Prompt to add reminder"""
    text = f'''<b><tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> Напишите напоминание</b>

Например:
• стрижка завтра в 15:00
• встреча 3 июня в 10:00'''

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_menu())
        await event.answer()
    else:
        await event.answer(text, parse_mode=ParseMode.HTML)

@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    """Handle text messages"""
    ensure_user(message.from_user.id)

    current_state = await state.get_state()

    if current_state == ReminderStates.waiting_for_time:
        data = await state.get_data()
        data["time"] = message.text

        add_reminder(message.from_user.id, data)

        await state.clear()
        await message.answer(
            f'<b><tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Напоминание создано!</b>\n\n'
            f'<b>{data["title"]}</b>\n'
            f'{data["date"]} в {data["time"]}',
            parse_mode=ParseMode.HTML
        )
        return

    # Parse with AI
    parsed = await parse_with_ai(message.text)

    if parsed.get("needs_clarification"):
        await message.answer(parsed["clarification_question"])

        if not parsed.get("time"):
            await state.set_state(ReminderStates.waiting_for_time)
            await state.update_data(
                title=parsed.get("title", ""),
                date=parsed.get("date", ""),
                category=parsed.get("category", "другое"),
                priority=parsed.get("priority", "обычное")
            )
        return

    add_reminder(message.from_user.id, parsed)

    await message.answer(
        f'<b><tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Напоминание создано!</b>\n\n'
        f'<b>{parsed["title"]}</b>\n'
        f'{parsed["date"]} в {parsed["time"]}',
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("done_"))
async def mark_done(callback: CallbackQuery):
    """Mark reminder as done"""
    reminder_id = int(callback.data.split("_")[1])
    mark_completed(reminder_id)

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Напоминание выполнено!</b>',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def delete_rem(callback: CallbackQuery):
    """Delete reminder"""
    reminder_id = int(callback.data.split("_")[1])
    delete_reminder(reminder_id)

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["trash"]}">🗑</tg-emoji> Напоминание удалено</b>',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )
    await callback.answer()

# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main function"""
    logger.info("Starting bot...")

    # Delete webhook
    await bot.delete_webhook(drop_pending_updates=True)

    # Start polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())

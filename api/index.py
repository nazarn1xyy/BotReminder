"""
Telegram Reminder Bot with AI - Serverless Function for Vercel
"""

import json
import logging
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from http.server import BaseHTTPRequestHandler

import pytz
from aiogram import Bot, Dispatcher, F
from aiogram.types import Update, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ============================================================================
# CONFIGURATION
# ============================================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8926447955:AAEKjSAYuaAFg-8VdS5YBVYNavMwt10QrNM")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "7eMrGygzAbBjIhIuFXDEYqrMaxpyuHh5")
DEFAULT_TIMEZONE = "Europe/Chisinau"

PREMIUM_EMOJI = {
    "reminder": "⏰",
    "time": "🕐",
    "success": "✅",
    "error": "❌",
    "settings": "⚙️",
    "category": "📁",
    "priority": "⭐",
    "list": "📋",
}

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# IN-MEMORY STORAGE
# ============================================================================

USERS_DB = {}
REMINDERS_DB = {}
NOTIFICATIONS_SENT = {}

def ensure_user_exists(user_id: int):
    """Ensure user exists in storage"""
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {
            "user_id": user_id,
            "timezone": DEFAULT_TIMEZONE,
            "morning_summary_time": "08:00",
            "created_at": datetime.now().isoformat()
        }

def add_reminder(user_id: int, reminder_data: Dict[str, Any]) -> int:
    """Add reminder to storage"""
    reminder_id = len(REMINDERS_DB) + 1

    REMINDERS_DB[reminder_id] = {
        "id": reminder_id,
        "user_id": user_id,
        "title": reminder_data["title"],
        "date": reminder_data["date"],
        "time": reminder_data["time"],
        "category": reminder_data.get("category", "другое"),
        "priority": reminder_data.get("priority", "обычное"),
        "repeat": reminder_data.get("repeat", "none"),
        "remind_before_minutes": reminder_data.get("remind_before_minutes", [120, 30, 0]),
        "completed": False,
        "created_at": datetime.now().isoformat()
    }

    return reminder_id

def get_user_reminders(user_id: int, completed: bool = False) -> List[Dict]:
    """Get user reminders"""
    reminders = []
    for reminder in REMINDERS_DB.values():
        if reminder["user_id"] == user_id and reminder["completed"] == completed:
            reminders.append(reminder)

    reminders.sort(key=lambda x: (x["date"], x["time"]))
    return reminders

def get_today_reminders(user_id: int, user_timezone: str = DEFAULT_TIMEZONE) -> List[Dict]:
    """Get today's reminders"""
    tz = pytz.timezone(user_timezone)
    today = datetime.now(tz).strftime('%Y-%m-%d')

    reminders = []
    for reminder in REMINDERS_DB.values():
        if reminder["user_id"] == user_id and reminder["date"] == today and not reminder["completed"]:
            reminders.append(reminder)

    reminders.sort(key=lambda x: x["time"])
    return reminders

def mark_reminder_completed(reminder_id: int):
    """Mark reminder as completed"""
    if reminder_id in REMINDERS_DB:
        REMINDERS_DB[reminder_id]["completed"] = True

def delete_reminder(reminder_id: int):
    """Delete reminder"""
    if reminder_id in REMINDERS_DB:
        del REMINDERS_DB[reminder_id]

    to_delete = [k for k, v in NOTIFICATIONS_SENT.items() if v["reminder_id"] == reminder_id]
    for k in to_delete:
        del NOTIFICATIONS_SENT[k]

# ============================================================================
# FSM STATES
# ============================================================================

class ReminderStates(StatesGroup):
    waiting_for_time = State()
    waiting_for_date = State()
    waiting_for_title = State()

# ============================================================================
# AI INTEGRATION (MISTRAL)
# ============================================================================

async def parse_reminder_with_ai(text: str, user_timezone: str = DEFAULT_TIMEZONE) -> Dict[str, Any]:
    """Parse reminder text using Mistral AI"""
    import httpx

    system_prompt = f"""You are a reminder parsing assistant. Parse the user's message and extract reminder information.
Current timezone: {user_timezone}
Current date: {datetime.now(pytz.timezone(user_timezone)).strftime('%Y-%m-%d')}
Current time: {datetime.now(pytz.timezone(user_timezone)).strftime('%H:%M')}

Return JSON with these fields:
- title: event name
- date: YYYY-MM-DD format
- time: HH:MM format (24-hour)
- category: личное/работа/учёба/здоровье/финансы/важное/другое
- priority: обычное/важное/срочное
- repeat: none/daily/weekly/monthly/yearly
- remind_before_minutes: array like [120, 30, 0]
- needs_clarification: true if missing critical info
- clarification_question: question to ask user if needs_clarification is true

Examples:
"стрижка завтра в 15:00" -> {{"title": "стрижка", "date": "2026-05-31", "time": "15:00", "category": "личное", "priority": "обычное", "repeat": "none", "remind_before_minutes": [120, 30, 0], "needs_clarification": false}}
"встреча 3 июня" -> {{"title": "встреча", "date": "2026-06-03", "time": null, "needs_clarification": true, "clarification_question": "Во сколько напомнить?"}}
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                content = result["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return parsed
            else:
                logger.error(f"Mistral API error: {response.status_code}")
                return {
                    "needs_clarification": True,
                    "clarification_question": "Не удалось распознать напоминание. Попробуйте написать в формате: 'название дата время'"
                }
    except Exception as e:
        logger.error(f"Error parsing with AI: {e}")
        return {
            "needs_clarification": True,
            "clarification_question": "Произошла ошибка. Попробуйте написать в формате: 'название дата время'"
        }

# ============================================================================
# KEYBOARD BUILDERS
# ============================================================================

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(text=f"{PREMIUM_EMOJI['list']} Мои напоминания", callback_data="list_reminders"),
            InlineKeyboardButton(text=f"{PREMIUM_EMOJI['reminder']} Добавить", callback_data="add_reminder")
        ],
        [
            InlineKeyboardButton(text=f"{PREMIUM_EMOJI['time']} Сегодня", callback_data="today_reminders"),
            InlineKeyboardButton(text=f"{PREMIUM_EMOJI['settings']} Настройки", callback_data="settings")
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ============================================================================
# BOT SETUP
# ============================================================================

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============================================================================
# BOT HANDLERS
# ============================================================================

async def cmd_start(message: Message):
    """Handle /start command"""
    ensure_user_exists(message.from_user.id)

    welcome_text = f"""
{PREMIUM_EMOJI['reminder']} Привет! Я бот-напоминалка с ИИ.

Просто напишите мне обычным текстом, что и когда вам напомнить:
• "стрижка завтра в 15:00"
• "встреча 3 июня в 10:00"
• "купить молоко сегодня в 18:00"

Я пойму и создам напоминание!
"""

    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard())

async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = """
📖 Как пользоваться ботом:

1️⃣ Просто напишите напоминание обычным текстом
2️⃣ Я распознаю дату, время и событие
3️⃣ Если чего-то не хватает, я уточню

Команды:
/start - главное меню
/list - мои напоминания
/today - задачи на сегодня
/settings - настройки
/help - эта справка
"""
    await message.answer(help_text, reply_markup=get_main_menu_keyboard())

async def cmd_list(message: Message):
    """Handle /list command"""
    reminders = get_user_reminders(message.from_user.id)

    if not reminders:
        await message.answer("У вас пока нет напоминаний", reply_markup=get_main_menu_keyboard())
        return

    text = f"{PREMIUM_EMOJI['list']} Ваши напоминания:\n\n"
    for r in reminders:
        text += f"📌 {r['title']}\n"
        text += f"📅 {r['date']} в {r['time']}\n\n"

    await message.answer(text, reply_markup=get_main_menu_keyboard())

async def cmd_today(message: Message):
    """Handle /today command"""
    reminders = get_today_reminders(message.from_user.id)

    if not reminders:
        await message.answer("На сегодня напоминаний нет", reply_markup=get_main_menu_keyboard())
        return

    text = f"{PREMIUM_EMOJI['time']} Задачи на сегодня:\n\n"
    for r in reminders:
        text += f"📌 {r['title']} в {r['time']}\n"

    await message.answer(text, reply_markup=get_main_menu_keyboard())

async def handle_text_message(message: Message, state: FSMContext):
    """Handle text messages"""
    ensure_user_exists(message.from_user.id)

    current_state = await state.get_state()

    if current_state == ReminderStates.waiting_for_time:
        data = await state.get_data()
        data["time"] = message.text

        reminder_id = add_reminder(message.from_user.id, data)

        await state.clear()
        await message.answer(
            f"{PREMIUM_EMOJI['success']} Напоминание создано!\n\n"
            f"📌 {data['title']}\n"
            f"📅 {data['date']} в {data['time']}",
            reply_markup=get_main_menu_keyboard()
        )
        return

    parsed = await parse_reminder_with_ai(message.text)

    if parsed.get("needs_clarification"):
        await message.answer(parsed["clarification_question"])

        if not parsed.get("time"):
            await state.set_state(ReminderStates.waiting_for_time)
            await state.update_data(
                title=parsed.get("title", ""),
                date=parsed.get("date", ""),
                category=parsed.get("category", "другое"),
                priority=parsed.get("priority", "обычное"),
                repeat=parsed.get("repeat", "none"),
                remind_before_minutes=parsed.get("remind_before_minutes", [120, 30, 0])
            )
        return

    reminder_id = add_reminder(message.from_user.id, parsed)

    await message.answer(
        f"{PREMIUM_EMOJI['success']} Напоминание создано!\n\n"
        f"📌 {parsed['title']}\n"
        f"📅 {parsed['date']} в {parsed['time']}",
        reply_markup=get_main_menu_keyboard()
    )

async def callback_list_reminders(callback: CallbackQuery):
    """Handle list reminders callback"""
    reminders = get_user_reminders(callback.from_user.id)

    if not reminders:
        await callback.message.edit_text("У вас пока нет напоминаний", reply_markup=get_main_menu_keyboard())
        return

    text = f"{PREMIUM_EMOJI['list']} Ваши напоминания:\n\n"
    for r in reminders:
        text += f"📌 {r['title']}\n"
        text += f"📅 {r['date']} в {r['time']}\n\n"

    await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    await callback.answer()

async def callback_add_reminder(callback: CallbackQuery):
    """Handle add reminder callback"""
    await callback.message.edit_text(
        "Напишите напоминание обычным текстом, например:\n\n"
        "• стрижка завтра в 15:00\n"
        "• встреча 3 июня в 10:00",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()

async def callback_today_reminders(callback: CallbackQuery):
    """Handle today reminders callback"""
    reminders = get_today_reminders(callback.from_user.id)

    if not reminders:
        await callback.message.edit_text("На сегодня напоминаний нет", reply_markup=get_main_menu_keyboard())
        return

    text = f"{PREMIUM_EMOJI['time']} Задачи на сегодня:\n\n"
    for r in reminders:
        text += f"📌 {r['title']} в {r['time']}\n"

    await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    await callback.answer()

async def callback_settings(callback: CallbackQuery):
    """Handle settings callback"""
    text = f"{PREMIUM_EMOJI['settings']} Настройки:\n\nЧасовой пояс: {DEFAULT_TIMEZONE}"
    await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    await callback.answer()

async def callback_help(callback: CallbackQuery):
    """Handle help callback"""
    help_text = """
📖 Как пользоваться ботом:

1️⃣ Просто напишите напоминание обычным текстом
2️⃣ Я распознаю дату, время и событие
3️⃣ Если чего-то не хватает, я уточню
"""
    await callback.message.edit_text(help_text, reply_markup=get_main_menu_keyboard())
    await callback.answer()

async def callback_complete_reminder(callback: CallbackQuery):
    """Handle complete reminder callback"""
    reminder_id = int(callback.data.split("_")[1])
    mark_reminder_completed(reminder_id)

    await callback.message.edit_text(
        f"{PREMIUM_EMOJI['success']} Напоминание отмечено как выполненное!",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()

async def callback_delete_reminder(callback: CallbackQuery):
    """Handle delete reminder callback"""
    reminder_id = int(callback.data.split("_")[1])
    delete_reminder(reminder_id)

    await callback.message.edit_text(
        "🗑 Напоминание удалено",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()

# ============================================================================
# REGISTER HANDLERS (at module level)
# ============================================================================

# Register message handlers
dp.message.register(cmd_start, Command("start"))
dp.message.register(cmd_help, Command("help"))
dp.message.register(cmd_list, Command("list"))
dp.message.register(cmd_today, Command("today"))
dp.message.register(handle_text_message, F.text)

# Register callback handlers
dp.callback_query.register(callback_list_reminders, F.data == "list_reminders")
dp.callback_query.register(callback_add_reminder, F.data == "add_reminder")
dp.callback_query.register(callback_today_reminders, F.data == "today_reminders")
dp.callback_query.register(callback_settings, F.data == "settings")
dp.callback_query.register(callback_help, F.data == "help")
dp.callback_query.register(callback_complete_reminder, F.data.startswith("complete_"))
dp.callback_query.register(callback_delete_reminder, F.data.startswith("delete_"))

# ============================================================================
# VERCEL SERVERLESS HANDLER
# ============================================================================

async def process_update(body: dict):
    """Process Telegram update"""
    try:
        logger.info(f"Processing update: {body}")
        update = Update.model_validate(body, context={"bot": bot})
        logger.info(f"Update validated: {update}")
        await dp.feed_update(bot, update)
        logger.info("Update processed successfully")
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)

class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler"""

    def do_GET(self):
        """Handle GET requests"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = json.dumps({'status': 'ok', 'message': 'Reminder Bot is running'})
        self.wfile.write(response.encode())

    def do_POST(self):
        """Handle POST requests (webhook)"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))

            # Process update asynchronously
            asyncio.run(process_update(body))

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({'ok': True})
            self.wfile.write(response.encode())
        except Exception as e:
            logger.error(f"Handler error: {e}")
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({'ok': True})
            self.wfile.write(response.encode())

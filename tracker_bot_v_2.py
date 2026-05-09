import telebot
from telebot import types
import sqlite3
from datetime import datetime
import threading
import time

# =========================
# CONFIG
# =========================

TOKEN = "8696665559:AAHoFXlywG_YNpDBE68ePeoiH-n8lsnBD_4"
ADMIN_IDS = [1427099343]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# =========================
# DATABASE
# =========================

conn = sqlite3.connect("calendar.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    event_time TEXT,
    notified INTEGER DEFAULT 0
)
""")

conn.commit()

# =========================
# HELPERS
# =========================

def add_user(user):
    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?)",
        (user.id, user.username)
    )
    conn.commit()

def is_admin(user_id):
    return user_id in ADMIN_IDS

# =========================
# MENUS
# =========================

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row("➕ Добавить", "📅 События")
    kb.row("🗑 Удалить", "ℹ️ Помощь")

    return kb

def admin_menu():
    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton(
            "📊 Статистика",
            callback_data="stats"
        )
    )

    return kb

# =========================
# START
# =========================

@bot.message_handler(commands=['start'])
def start(message):

    add_user(message.from_user)

    bot.send_message(
        message.chat.id,
        "📅 <b>Calendar Bot</b>\n\nВыбери действие 👇",
        reply_markup=main_menu()
    )

# =========================
# ADD EVENT
# =========================

@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def add_event(message):

    msg = bot.send_message(
        message.chat.id,
        "✍️ Введи событие:\n\n"
        "Пример:\n"
        "<code>Тренировка | 2026-05-10 18:00</code>"
    )

    bot.register_next_step_handler(msg, save_event)

def save_event(message):

    try:
        data = message.text.split("|")

        title = data[0].strip()
        event_time = data[1].strip()

        datetime.strptime(event_time, "%Y-%m-%d %H:%M")

        cursor.execute("""
            INSERT INTO events (
                user_id,
                title,
                event_time
            )
            VALUES (?, ?, ?)
        """, (
            message.from_user.id,
            title,
            event_time
        ))

        conn.commit()

        bot.send_message(
            message.chat.id,
            f"✅ Добавлено\n\n📌 {title}\n⏰ {event_time}"
        )

    except:
        bot.send_message(
            message.chat.id,
            "❌ Неверный формат"
        )

# =========================
# EVENTS
# =========================

@bot.message_handler(func=lambda m: m.text == "📅 События")
def events(message):

    cursor.execute("""
        SELECT id, title, event_time
        FROM events
        WHERE user_id=?
        ORDER BY event_time
    """, (message.from_user.id,))

    data = cursor.fetchall()

    if not data:
        return bot.send_message(
            message.chat.id,
            "📭 Событий нет"
        )

    text = "📅 <b>Твои события:</b>\n\n"

    for e in data:
        text += (
            f"🆔 {e[0]}\n"
            f"📌 {e[1]}\n"
            f"⏰ {e[2]}\n\n"
        )

    bot.send_message(message.chat.id, text)

# =========================
# DELETE
# =========================

@bot.message_handler(func=lambda m: m.text == "🗑 Удалить")
def delete_event(message):

    msg = bot.send_message(
        message.chat.id,
        "🗑 Введи ID события"
    )

    bot.register_next_step_handler(msg, process_delete)

def process_delete(message):

    try:
        event_id = int(message.text)

        cursor.execute("""
            DELETE FROM events
            WHERE id=? AND user_id=?
        """, (
            event_id,
            message.from_user.id
        ))

        conn.commit()

        bot.send_message(
            message.chat.id,
            "✅ Удалено"
        )

    except:
        bot.send_message(
            message.chat.id,
            "❌ Ошибка"
        )

# =========================
# HELP
# =========================

@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def help_cmd(message):

    bot.send_message(
        message.chat.id,
        "📖 Это бот-календарь с напоминаниями"
    )

# =========================
# ADMIN
# =========================

@bot.message_handler(commands=['admin'])
def admin(message):

    if not is_admin(message.from_user.id):
        return

    bot.send_message(
        message.chat.id,
        "🔧 Админ-панель",
        reply_markup=admin_menu()
    )

@bot.callback_query_handler(func=lambda c: c.data == "stats")
def stats(call):

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM events")
    events = cursor.fetchone()[0]

    bot.send_message(
        call.message.chat.id,
        f"📊 Статистика\n\n👥 Пользователей: {users}\n📅 Событий: {events}"
    )

# =========================
# REMINDERS
# =========================

def reminder_loop():

    while True:

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        cursor.execute("""
            SELECT id, user_id, title
            FROM events
            WHERE event_time=? AND notified=0
        """, (now,))

        events = cursor.fetchall()

        for e in events:

            try:
                bot.send_message(
                    e[1],
                    f"⏰ Напоминание\n\n📌 {e[2]}"
                )

                cursor.execute("""
                    UPDATE events
                    SET notified=1
                    WHERE id=?
                """, (e[0],))

                conn.commit()

            except:
                pass

        time.sleep(20)

threading.Thread(
    target=reminder_loop,
    daemon=True
).start()

# =========================
# RUN
# =========================

print("Calendar bot started")

while True:
    try:
        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=30
        )

    except Exception as e:
        print(e)
        time.sleep(5)

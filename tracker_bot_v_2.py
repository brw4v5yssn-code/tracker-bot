import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import threading
import time

# =========================================
# 🔐 CONFIG
# =========================================

TOKEN = "8696665559:AAHoFXlywG_YNpDBE68ePeoiH-n8lsnBD_4"
ADMIN_IDS = [987654321]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# =========================================
# 📦 DATABASE
# =========================================

conn = sqlite3.connect("calendar.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    joined TEXT
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

# =========================================
# 🧠 HELPERS
# =========================================

def add_user(user):
    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, ?)",
        (
            user.id,
            user.username,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        )
    )
    conn.commit()


def is_admin(user_id):
    return user_id in ADMIN_IDS


def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row("➕ Добавить", "📅 Мои события")
    kb.row("🗑 Удалить", "ℹ️ Помощь")

    return kb

# =========================================
# 🚀 START
# =========================================

@bot.message_handler(commands=['start'])
def start(message):
    add_user(message.from_user)

    text = (
        "📅 <b>Calendar PRO</b>\n\n"
        "Я помогу хранить события и напоминания.\n\n"
        "Выбери действие 👇"
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_menu()
    )

# =========================================
# ➕ ADD EVENT
# =========================================

@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def add_event(message):
    msg = bot.send_message(
        message.chat.id,
        "✍️ Введи событие:\n\n"
        "<code>Текст | YYYY-MM-DD HH:MM</code>\n\n"
        "Пример:\n"
        "<code>Встреча | 2026-05-10 18:00</code>"
    )

    bot.register_next_step_handler(msg, save_event)


def save_event(message):
    try:
        data = message.text.split("|")

        title = data[0].strip()
        event_time = data[1].strip()

        # проверка даты
        dt = datetime.strptime(event_time, "%Y-%m-%d %H:%M")

        cursor.execute("""
            INSERT INTO events (
                user_id,
                title,
                event_time
            ) VALUES (?, ?, ?)
        """, (
            message.from_user.id,
            title,
            event_time
        ))

        conn.commit()

        bot.send_message(
            message.chat.id,
            f"✅ Событие добавлено\n\n"
            f"📌 {title}\n"
            f"⏰ {event_time}"
        )

    except Exception as e:
        bot.send_message(
            message.chat.id,
            "❌ Ошибка формата\n\n"
            "Пример:\n"
            "<code>Тренировка | 2026-05-10 18:00</code>"
        )

# =========================================
# 📅 MY EVENTS
# =========================================

@bot.message_handler(func=lambda m: m.text == "📅 Мои события")
def my_events(message):

    cursor.execute("""
        SELECT id, title, event_time
        FROM events
        WHERE user_id=?
        ORDER BY event_time
    """, (message.from_user.id,))

    events = cursor.fetchall()

    if not events:
        return bot.send_message(
            message.chat.id,
            "📭 У тебя нет событий"
        )

    text = "📅 <b>Твои события:</b>\n\n"

    for event in events:
        text += (
            f"🆔 {event[0]}\n"
            f"📌 {event[1]}\n"
            f"⏰ {event[2]}\n\n"
        )

    bot.send_message(message.chat.id, text)

# =========================================
# 🗑 DELETE EVENT
# =========================================

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
            f"✅ Событие {event_id} удалено"
        )

    except:
        bot.send_message(
            message.chat.id,
            "❌ Ошибка"
        )

# =========================================
# ℹ️ HELP
# =========================================

@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def help_cmd(message):

    text = (
        "📖 <b>Помощь</b>\n\n"
        "➕ Добавить событие\n"
        "📅 Посмотреть список\n"
        "🗑 Удалить событие\n\n"
        "Бот автоматически пришлёт напоминание ⏰"
    )

    bot.send_message(message.chat.id, text)

# =========================================
# 🔧 ADMIN PANEL
# =========================================

@bot.message_handler(commands=['admin'])
def admin(message):

    if not is_admin(message.from_user.id):
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM events")
    events = cursor.fetchone()[0]

    text = (
        "🔧 <b>ADMIN PANEL</b>\n\n"
        f"👥 Пользователей: {users}\n"
        f"📅 Событий: {events}"
    )

    bot.send_message(message.chat.id, text)

# =========================================
# ⏰ REMINDER LOOP
# =========================================

def reminder_loop():

    while True:

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        cursor.execute("""
            SELECT id, user_id, title
            FROM events
            WHERE event_time=? AND notified=0
        """, (now,))

        events = cursor.fetchall()

        for event in events:

            try:
                bot.send_message(
                    event[1],
                    f"⏰ <b>НАПОМИНАНИЕ</b>\n\n📌 {event[2]}"
                )

                cursor.execute("""
                    UPDATE events
                    SET notified=1
                    WHERE id=?
                """, (event[0],))

                conn.commit()

            except Exception as e:
                print(e)

        time.sleep(20)

# =========================================
# 🚀 START THREAD
# =========================================

threading.Thread(
    target=reminder_loop,
    daemon=True
).start()

# =========================================
# ▶️ RUN
# =========================================

print("📅 Calendar PRO started...")

while True:
    try:
        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=30
        )

    except Exception as e:
        print("ERROR:", e)
        time.sleep(5)

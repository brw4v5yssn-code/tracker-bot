import telebot
from telebot import types
import sqlite3
from datetime import datetime
import os

# ======================
# 🔐 НАСТРОЙКИ
# ======================

TOKEN = "8696665559:AAFj5mQtQh2b3nAiaq5q3EUPDqqXNDaBXmY"
ADMIN_IDS = [1427099343]  # <-- свой Telegram ID

bot = telebot.TeleBot(TOKEN)

# ======================
# 📦 БАЗА ДАННЫХ
# ======================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_seen TEXT,
    messages_count INTEGER DEFAULT 0,
    banned INTEGER DEFAULT 0
)
""")

conn.commit()

# ======================
# 🧠 ЛОГИКА
# ======================

def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_banned(user_id):
    cursor.execute("SELECT banned FROM users WHERE id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1


def add_user(user_id, username):
    cursor.execute("SELECT id FROM users WHERE id=?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (id, username, first_seen) VALUES (?, ?, ?)",
            (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()


def increase_messages(user_id):
    cursor.execute(
        "UPDATE users SET messages_count = messages_count + 1 WHERE id=?",
        (user_id,)
    )
    conn.commit()

# ======================
# 🧩 АДМИН ПАНЕЛЬ
# ======================

def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        types.InlineKeyboardButton("👥 Пользователи", callback_data="users")
    )

    markup.add(
        types.InlineKeyboardButton("🚫 Бан", callback_data="ban"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")
    )

    return markup

# ======================
# 🚀 START
# ======================

@bot.message_handler(commands=['start'])
def start(message):
    if is_banned(message.from_user.id):
        return

    add_user(message.from_user.id, message.from_user.username)

    bot.send_message(message.chat.id, "👋 Бот работает!")

# ======================
# 📩 ВСЕ СООБЩЕНИЯ
# ======================

@bot.message_handler(func=lambda m: True)
def all_messages(message):
    if is_banned(message.from_user.id):
        return

    add_user(message.from_user.id, message.from_user.username)
    increase_messages(message.from_user.id)

# ======================
# 🔧 АДМИНКА
# ======================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        return bot.send_message(message.chat.id, "⛔ Нет доступа")

    bot.send_message(message.chat.id, "🔧 Админ-панель:", reply_markup=admin_menu())

# ======================
# 📊 СТАТИСТИКА
# ======================

def get_stats():
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(messages_count) FROM users")
    messages = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned = cursor.fetchone()[0]

    return users, messages, banned


@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats(call):
    users, messages, banned = get_stats()

    bot.send_message(call.message.chat.id,
        f"📊 СТАТИСТИКА\n\n👥 {users}\n💬 {messages}\n🚫 {banned}"
    )

# ======================
# 👥 ПОЛЬЗОВАТЕЛИ
# ======================

@bot.callback_query_handler(func=lambda call: call.data == "users")
def users(call):
    cursor.execute("""
        SELECT id, username, messages_count
        FROM users
        ORDER BY messages_count DESC
        LIMIT 10
    """)

    data = cursor.fetchall()

    text = "👥 ТОП:\n\n"

    for u in data:
        text += f"{u[0]} | @{u[1]} | 💬 {u[2]}\n"

    bot.send_message(call.message.chat.id, text)

# ======================
# 🚫 БАН
# ======================

@bot.callback_query_handler(func=lambda call: call.data == "ban")
def ban_menu(call):
    msg = bot.send_message(call.message.chat.id, "ID для бана:")
    bot.register_next_step_handler(msg, do_ban)


def do_ban(message):
    try:
        user_id = int(message.text)

        cursor.execute("UPDATE users SET banned=1 WHERE id=?", (user_id,))
        conn.commit()

        bot.send_message(message.chat.id, f"🚫 Забанен {user_id}")

    except:
        bot.send_message(message.chat.id, "❌ Ошибка")

# ======================
# 📢 РАССЫЛКА
# ======================

@bot.callback_query_handler(func=lambda call: call.data == "broadcast")
def broadcast(call):
    msg = bot.send_message(call.message.chat.id, "Текст рассылки:")
    bot.register_next_step_handler(msg, send_broadcast)


def send_broadcast(message):
    text = message.text

    cursor.execute("SELECT id FROM users WHERE banned=0")
    users = cursor.fetchall()

    sent = 0

    for u in users:
        try:
            bot.send_message(u[0], f"📢 {text}")
            sent += 1
        except:
            pass

    bot.send_message(message.chat.id, f"✅ Отправлено: {sent}")

# ======================
# ▶️ ЗАПУСК (ЧИСТЫЙ)
# ======================

print("Bot started...")

bot.infinity_polling()
import telebot
from telebot import types
import sqlite3
from datetime import datetime
import time

# ======================
# 🔐 CONFIG
# ======================

TOKEN = "8696665559:AAHoFXlywG_YNpDBE68ePeoiH-n8lsnBD_4"
ADMIN_IDS = [1427099343]

bot = telebot.TeleBot(TOKEN)

# ======================
# 📦 DB
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
# 🧠 HELPERS
# ======================

def add_user(uid, username):
    cursor.execute("SELECT id FROM users WHERE id=?", (uid,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (id, username, first_seen) VALUES (?, ?, ?)",
            (uid, username, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()

def inc(uid):
    cursor.execute(
        "UPDATE users SET messages_count = messages_count + 1 WHERE id=?",
        (uid,)
    )
    conn.commit()

def is_admin(uid):
    return uid in ADMIN_IDS

# ======================
# 🎮 MAIN MENU
# ======================

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row("📊 Статус", "👤 Профиль")
    kb.row("ℹ️ Помощь", "💬 Написать боту")

    return kb

# ======================
# 🚀 START
# ======================

@bot.message_handler(commands=['start'])
def start(m):
    add_user(m.from_user.id, m.from_user.username)
    inc(m.from_user.id)

    bot.send_message(
        m.chat.id,
        "👋 Привет! Я живой бот.\nВыбери действие ниже 👇",
        reply_markup=main_menu()
    )

# ======================
# 💬 PROFILE
# ======================

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(m):
    cursor.execute("SELECT messages_count, first_seen FROM users WHERE id=?",
                   (m.from_user.id,))
    data = cursor.fetchone()

    if not data:
        bot.send_message(m.chat.id, "Нет данных")
        return

    bot.send_message(
        m.chat.id,
        f"👤 Твой профиль\n\n💬 Сообщений: {data[0]}\n📅 С нами с: {data[1]}"
    )

# ======================
# 📊 STATUS
# ======================

@bot.message_handler(func=lambda m: m.text == "📊 Статус")
def status(m):
    bot.send_message(m.chat.id, "✅ Бот работает нормально и живой")

# ======================
# ℹ️ HELP
# ======================

@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def help(m):
    bot.send_message(
        m.chat.id,
        "🧠 Команды:\n\n"
        "📊 Статус — проверка работы\n"
        "👤 Профиль — твоя статистика\n"
        "💬 Написать боту — просто напиши сообщение"
    )

# ======================
# 💬 ECHO + AI STYLE
# ======================

@bot.message_handler(func=lambda m: True)
def all_messages(m):
    add_user(m.from_user.id, m.from_user.username)
    inc(m.from_user.id)

    text = m.text.lower()

    # простые реакции (делают бота "живым")
    if "привет" in text:
        bot.send_message(m.chat.id, "👋 Привет!")
        return

    if "как дела" in text:
        bot.send_message(m.chat.id, "🤖 Я работаю стабильно")
        return

    if "бот" in text:
        bot.send_message(m.chat.id, "🤖 Да, я здесь")
        return

    # fallback
    bot.send_message(m.chat.id, f"💬 Ты написал: {m.text}")

# ======================
# 🔧 ADMIN
# ======================

@bot.message_handler(commands=['admin'])
def admin(m):
    if not is_admin(m.from_user.id):
        return

    bot.send_message(m.chat.id, "🔧 Админ режим активен")

# ======================
# 🧠 SAFE LOOP
# ======================

print("🤖 Bot is alive...")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except Exception as e:
        print("ERROR:", e)
        time.sleep(3)

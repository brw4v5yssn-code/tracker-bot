import telebot
from telebot import types
import sqlite3
from datetime import datetime
import os
import time

# ======================
# 🔐 CONFIG
# ======================

TOKEN = "8696665559:AAFj5mQtQh2b3nAiaq5q3EUPDqqXNDaBXmY"
ADMIN_IDS = [1427099343]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ======================
# 📦 DB (STABLE MODE)
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
# 🧠 CACHE (ANTI SPAM)
# ======================

last_msg_time = {}

def anti_spam(user_id):
    now = time.time()
    if user_id in last_msg_time:
        if now - last_msg_time[user_id] < 0.3:
            return True
    last_msg_time[user_id] = now
    return False

# ======================
# 🔐 HELPERS
# ======================

def is_admin(uid):
    return uid in ADMIN_IDS

def is_banned(uid):
    cursor.execute("SELECT banned FROM users WHERE id=?", (uid,))
    r = cursor.fetchone()
    return r and r[0] == 1

def add_user(uid, username):
    cursor.execute("SELECT id FROM users WHERE id=?", (uid,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (id, username, first_seen) VALUES (?, ?, ?)",
            (uid, username, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()

def inc_msg(uid):
    cursor.execute(
        "UPDATE users SET messages_count = messages_count + 1 WHERE id=?",
        (uid,)
    )
    conn.commit()

# ======================
# 🔧 ADMIN PANEL
# ======================

def menu():
    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.add(
        types.InlineKeyboardButton("📊 Стата", callback_data="stats"),
        types.InlineKeyboardButton("👥 Юзеры", callback_data="users")
    )

    kb.add(
        types.InlineKeyboardButton("🚫 Бан", callback_data="ban"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")
    )

    return kb

# ======================
# 🚀 START
# ======================

@bot.message_handler(commands=['start'])
def start(m):
    if anti_spam(m.from_user.id):
        return

    if is_banned(m.from_user.id):
        return

    add_user(m.from_user.id, m.from_user.username)
    bot.send_message(m.chat.id, "👋 Бот работает")

# ======================
# 📩 ALL MSGS
# ======================

@bot.message_handler(func=lambda m: True)
def all(m):
    if anti_spam(m.from_user.id):
        return

    if is_banned(m.from_user.id):
        return

    add_user(m.from_user.id, m.from_user.username)
    inc_msg(m.from_user.id)

# ======================
# 🔧 ADMIN
# ======================

@bot.message_handler(commands=['admin'])
def admin(m):
    if not is_admin(m.from_user.id):
        return bot.send_message(m.chat.id, "⛔ Нет доступа")

    bot.send_message(m.chat.id, "🔧 Админка", reply_markup=menu())

# ======================
# 📊 STATS
# ======================

def stats():
    cursor.execute("SELECT COUNT(*) FROM users")
    u = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(messages_count) FROM users")
    msg = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    b = cursor.fetchone()[0]

    return u, msg, b


@bot.callback_query_handler(func=lambda c: c.data == "stats")
def st(c):
    u, m, b = stats()

    bot.send_message(c.message.chat.id,
        f"📊 СТАТИСТИКА\n\n👥 {u}\n💬 {m}\n🚫 {b}"
    )

# ======================
# 👥 USERS
# ======================

@bot.callback_query_handler(func=lambda c: c.data == "users")
def us(c):
    cursor.execute("""
        SELECT id, username, messages_count
        FROM users
        ORDER BY messages_count DESC
        LIMIT 10
    """)

    data = cursor.fetchall()

    text = "👥 TOP:\n\n"
    for u in data:
        text += f"{u[0]} | @{u[1]} | 💬 {u[2]}\n"

    bot.send_message(c.message.chat.id, text)

# ======================
# 🚫 BAN
# ======================

@bot.callback_query_handler(func=lambda c: c.data == "ban")
def ban(c):
    msg = bot.send_message(c.message.chat.id, "ID для бана:")
    bot.register_next_step_handler(msg, do_ban)


def do_ban(m):
    try:
        uid = int(m.text)

        cursor.execute("UPDATE users SET banned=1 WHERE id=?", (uid,))
        conn.commit()

        bot.send_message(m.chat.id, f"🚫 Забанен {uid}")

    except:
        bot.send_message(m.chat.id, "❌ Ошибка")

# ======================
# 📢 BROADCAST
# ======================

@bot.callback_query_handler(func=lambda c: c.data == "broadcast")
def bc(c):
    msg = bot.send_message(c.message.chat.id, "Текст:")
    bot.register_next_step_handler(msg, send_bc)


def send_bc(m):
    text = m.text

    cursor.execute("SELECT id FROM users WHERE banned=0")
    users = cursor.fetchall()

    sent = 0

    for u in users:
        try:
            bot.send_message(u[0], f"📢 {text}")
            sent += 1
        except:
            pass

    bot.send_message(m.chat.id, f"✅ Отправлено {sent}")

# ======================
# 🛡 SAFE START (RAILWAY FIX)
# ======================

print("Bot started...")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except Exception as e:
        print("ERROR:", e)
        time.sleep(3)

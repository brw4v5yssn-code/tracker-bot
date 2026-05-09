import telebot
from telebot import types
import sqlite3
from datetime import datetime

# ======================
# 🔐 НАСТРОЙКИ
# ======================

TOKEN = "8696665559:AAFj5mQtQh2b3nAiaq5q3EUPDqqXNDaBXmY"
ADMIN_IDS = [1427099343]  # <-- поставь свой Telegram ID

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
# 🧠 ФУНКЦИИ
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
# 🧩 АДМИН-ПАНЕЛЬ
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
# 🚀 СТАРТ
# ======================

@bot.message_handler(commands=['start'])
def start(message):
    if is_banned(message.from_user.id):
        return

    add_user(message.from_user.id, message.from_user.username)

    bot.send_message(
        message.chat.id,
        "👋 Привет! Бот работает."
    )

# ======================
# 📊 ЛЮБОЕ СООБЩЕНИЕ
# ======================

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if is_banned(message.from_user.id):
        return

    add_user(message.from_user.id, message.from_user.username)
    increase_messages(message.from_user.id)

# ======================
# 🔧 АДМИН ПАНЕЛЬ
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

    bot.send_message(
        call.message.chat.id,
        f"""📊 СТАТИСТИКА

👥 Пользователей: {users}
💬 Сообщений: {messages}
🚫 Забанено: {banned}
"""
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

    text = "👥 ТОП пользователей:\n\n"

    for u in data:
        text += f"ID: {u[0]} | @{u[1]} | 💬 {u[2]}\n"

    bot.send_message(call.message.chat.id, text)

# ======================
# 🚫 БАН
# ======================

@bot.callback_query_handler(func=lambda call: call.data == "ban")
def ban_menu(call):
    msg = bot.send_message(call.message.chat.id, "Введи ID пользователя:")
    bot.register_next_step_handler(msg, do_ban)


def do_ban(message):
    try:
        user_id = int(message.text)

        cursor.execute("UPDATE users SET banned=1 WHERE id=?", (user_id,))
        conn.commit()

        bot.send_message(message.chat.id, f"🚫 Забанен: {user_id}")

    except:
        bot.send_message(message.chat.id, "❌ Ошибка ID")

# ======================
# 📢 РАССЫЛКА
# ======================

@bot.callback_query_handler(func=lambda call: call.data == "broadcast")
def broadcast_start(call):
    msg = bot.send_message(call.message.chat.id, "📢 Введи текст:")
    bot.register_next_step_handler(msg, do_broadcast)


def do_broadcast(message):
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
# ▶️ ЗАПУСК
# ======================

print("Bot started...")
import os
bot.infinity_polling()
import sqlite3
from datetime import datetime, timedelta
from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    print('ERROR: BOT_TOKEN not found. Create .env file with BOT_TOKEN=your_token')
    raise SystemExit(1)
bot = TeleBot(TOKEN, parse_mode='HTML')
DB='tracker_v2.db'

# ---------- DB ----------
def conn():
    return sqlite3.connect(DB)

def init_db():
    with conn() as c:
        cur=c.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,name TEXT,goal REAL DEFAULT 8,last_project TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,date TEXT,project TEXT,hours REAL)')
init_db()

state={}
temp={}

def today(): return datetime.now().strftime('%Y-%m-%d')

def menu():
    m=types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row('➕ Добавить','📊 Сегодня')
    m.row('📆 Неделя','🎯 Цель')
    m.row('🔥 Streak','📁 Проекты')
    return m

def projects():
    m=types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row('🐍 Python','💼 Work','📚 Study')
    m.row('🧠 Gym','💰 Freelance')
    m.row('🔙 Назад')
    return m

def hours_kb():
    m=types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row('1','2','3','4')
    m.row('5','6','7','8')
    m.row('🔙 Назад')
    return m

@bot.message_handler(commands=['start'])
def start(msg):
    uid=msg.chat.id
    with conn() as c:
        c.execute('INSERT OR IGNORE INTO users(user_id,name) VALUES(?,?)',(uid,msg.from_user.first_name))
    bot.send_message(uid,'🚀 Tracker V2 запущен',reply_markup=menu())

@bot.message_handler(func=lambda m: True)
def handler(msg):
    uid=msg.chat.id
    text=msg.text.strip()

    if text.startswith('+'):
        quick_add(uid,text)
        return

    if uid in state:
        flow(uid,text)
        return

    if text=='➕ Добавить':
        state[uid]='project'
        bot.send_message(uid,'Выбери проект',reply_markup=projects())
    elif text=='📊 Сегодня':
        report_today(uid)
    elif text=='📆 Неделя':
        report_week(uid)
    elif text=='🔥 Streak':
        bot.send_message(uid,f'🔥 Серия: {streak(uid)} дней')
    elif text=='🎯 Цель':
        state[uid]='goal'
        bot.send_message(uid,'Введи дневную цель в часах (например 6)')
    elif text=='📁 Проекты':
        project_stats(uid)
    else:
        bot.send_message(uid,'Используй меню 👇',reply_markup=menu())

def flow(uid,text):
    step=state[uid]
    if step=='project':
        if text=='🔙 Назад':
            state.pop(uid,None); bot.send_message(uid,'Меню',reply_markup=menu()); return
        temp[uid]={'project':text}
        state[uid]='hours'
        bot.send_message(uid,'Сколько часов?',reply_markup=hours_kb())
    elif step=='hours':
        try:
            h=float(text.replace(',','.'))
            if h<=0 or h>24: raise ValueError()
            p=temp[uid]['project']
            save_log(uid,p,h)
            bot.send_message(uid,f'✅ {h}ч [{p}]',reply_markup=menu())
        except:
            bot.send_message(uid,'Введите число от 0 до 24')
        state.pop(uid,None); temp.pop(uid,None)
    elif step=='goal':
        try:
            g=float(text.replace(',','.'))
            with conn() as c:
                c.execute('UPDATE users SET goal=? WHERE user_id=?',(g,uid))
            bot.send_message(uid,f'🎯 Цель сохранена: {g}ч',reply_markup=menu())
        except:
            bot.send_message(uid,'Ошибка ввода',reply_markup=menu())
        state.pop(uid,None)

def save_log(uid,p,h):
    with conn() as c:
        c.execute('INSERT INTO logs(user_id,date,project,hours) VALUES(?,?,?,?)',(uid,today(),p,h))
        c.execute('UPDATE users SET last_project=? WHERE user_id=?',(p,uid))

def quick_add(uid,text):
    try:
        arr=text[1:].split()
        h=float(arr[0]); p=arr[1] if len(arr)>1 else 'Work'
        save_log(uid,p,h)
        bot.send_message(uid,f'⚡ Добавлено {h}ч [{p}]')
    except:
        bot.send_message(uid,'Формат: +2 Work')

def report_today(uid):
    with conn() as c:
        val=c.execute('SELECT COALESCE(SUM(hours),0) FROM logs WHERE user_id=? AND date=?',(uid,today())).fetchone()[0]
        goal=c.execute('SELECT goal FROM users WHERE user_id=?',(uid,)).fetchone()[0]
    pct=min(100,int(val/goal*100)) if goal else 0
    bot.send_message(uid,f'📊 Сегодня: {val:.1f}ч / {goal:.1f}ч ({pct}%)')

def report_week(uid):
    since=(datetime.now()-timedelta(days=7)).strftime('%Y-%m-%d')
    with conn() as c:
        rows=c.execute('SELECT COALESCE(SUM(hours),0) FROM logs WHERE user_id=? AND date>=?',(uid,since)).fetchone()[0]
    bot.send_message(uid,f'📆 За 7 дней: {rows:.1f}ч')

def streak(uid):
    with conn() as c:
        dates=[r[0] for r in c.execute('SELECT DISTINCT date FROM logs WHERE user_id=? ORDER BY date DESC',(uid,)).fetchall()]
    cur=datetime.now(); s=0
    for d in dates:
        if d==cur.strftime('%Y-%m-%d'):
            s+=1; cur-=timedelta(days=1)
        else:
            break
    return s

def project_stats(uid):
    with conn() as c:
        rows=c.execute('SELECT project,SUM(hours) FROM logs WHERE user_id=? GROUP BY project ORDER BY SUM(hours) DESC',(uid,)).fetchall()
    if not rows:
        bot.send_message(uid,'Нет данных'); return
    txt='📁 Проекты:\n'+'\n'.join([f'{p}: {h:.1f}ч' for p,h in rows])
    bot.send_message(uid,txt)

def daily_push():
    with conn() as c:
        users=c.execute('SELECT user_id FROM users').fetchall()
    for (uid,) in users:
        try:
            report_today(uid)
        except:
            pass

scheduler=BackgroundScheduler()
scheduler.add_job(daily_push,'cron',hour=23,minute=0)
scheduler.start()

print('Bot started successfully. Press Ctrl+C to stop.')
bot.infinity_polling()

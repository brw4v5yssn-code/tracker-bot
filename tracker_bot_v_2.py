import os
import sqlite3
import time
from datetime import datetime, timedelta

from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("ERROR: BOT_TOKEN not found in .env")
    raise SystemExit(1)

ADMIN_IDS = [1427099343]

DB = "tracker_v2.db"

bot = TeleBot(TOKEN, parse_mode="HTML")

# =========================
# DB
# =========================

def conn():
    return sqlite3.connect(DB, check_same_thread=False)


def init_db():
    with conn() as c:
        cur = c.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            goal REAL DEFAULT 8,
            last_project TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            project TEXT,
            hours REAL
        )
        """)

        # защита от спама
        cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders(
            user_id INTEGER,
            date TEXT,
            PRIMARY KEY(user_id, date)
        )
        """)

        c.commit()


init_db()

# =========================
# MEMORY
# =========================

state = {}
temp = {}

# =========================
# HELPERS
# =========================

def today():
    return datetime.now().strftime("%Y-%m-%d")


def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Добавить", "📊 Сегодня")
    kb.row("📆 Неделя", "🔥 Streak")
    kb.row("🎯 Цель", "📁 Проекты")
    return kb


def projects_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🐍 Python", "💼 Work")
    kb.row("📚 Study", "🧠 Gym")
    kb.row("💰 Freelance")
    kb.row("🔙 Назад")
    return kb


def hours_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("1", "2", "3", "4")
    kb.row("5", "6", "7", "8")
    kb.row("🔙 Назад")
    return kb


def save_log(uid, project, hours):
    with conn() as c:
        c.execute(
            "INSERT INTO logs(user_id,date,project,hours) VALUES(?,?,?,?)",
            (uid, today(), project, hours)
        )
        c.execute(
            "UPDATE users SET last_project=? WHERE user_id=?",
            (project, uid)
        )
        c.commit()

# =========================
# REPORTS
# =========================

def report_today(uid):
    with conn() as c:
        total = c.execute(
            "SELECT COALESCE(SUM(hours),0) FROM logs WHERE user_id=? AND date=?",
            (uid, today())
        ).fetchone()[0]

        goal = c.execute(
            "SELECT goal FROM users WHERE user_id=?",
            (uid,)
        ).fetchone()

    goal = goal[0] if goal else 8
    percent = min(100, int((total / goal) * 100)) if goal else 0

    bot.send_message(
        uid,
        f"📊 <b>Сегодня</b>\n\n⏱ {total:.1f}ч / {goal:.1f}ч\n📈 {percent}%",
        reply_markup=main_menu()
    )


def report_week(uid):
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    with conn() as c:
        total = c.execute(
            "SELECT COALESCE(SUM(hours),0) FROM logs WHERE user_id=? AND date>=?",
            (uid, since)
        ).fetchone()[0]

    bot.send_message(uid, f"📆 За 7 дней: <b>{total:.1f}ч</b>", reply_markup=main_menu())


def streak(uid):
    with conn() as c:
        rows = c.execute(
            "SELECT DISTINCT date FROM logs WHERE user_id=? ORDER BY date DESC",
            (uid,)
        ).fetchall()

    dates = [r[0] for r in rows]
    if not dates:
        return 0

    cur = datetime.now().date()
    s = 0

    for d in dates:
        dd = datetime.strptime(d, "%Y-%m-%d").date()
        if dd == cur:
            s += 1
            cur -= timedelta(days=1)
        else:
            break

    return s


def project_stats(uid):
    with conn() as c:
        rows = c.execute(
            "SELECT project, SUM(hours) FROM logs WHERE user_id=? GROUP BY project ORDER BY SUM(hours) DESC",
            (uid,)
        ).fetchall()

    if not rows:
        bot.send_message(uid, "Нет данных", reply_markup=main_menu())
        return

    txt = "📁 <b>Проекты</b>\n\n"
    for p, h in rows:
        txt += f"• {p}: {h:.1f}ч\n"

    bot.send_message(uid, txt, reply_markup=main_menu())

# =========================
# QUICK ADD
# =========================

def quick_add(uid, text):
    try:
        arr = text[1:].split()
        h = float(arr[0].replace(",", "."))
        if h <= 0 or h > 24:
            raise ValueError()

        p = arr[1] if len(arr) > 1 else "Work"
        save_log(uid, p, h)

        bot.send_message(uid, f"⚡ {h}ч [{p}]", reply_markup=main_menu())

    except:
        bot.send_message(uid, "Формат: +2 Work")

# =========================
# REMINDERS (NO SPAM)
# =========================

def send_reminders():
    with conn() as c:
        users = c.execute("SELECT user_id, COALESCE(goal,8) FROM users").fetchall()

    for uid, goal in users:

        today_str = today()

        with conn() as c:
            exists = c.execute(
                "SELECT 1 FROM reminders WHERE user_id=? AND date=?",
                (uid, today_str)
            ).fetchone()

            if exists:
                continue

            total = c.execute(
                "SELECT COALESCE(SUM(hours),0) FROM logs WHERE user_id=? AND date=?",
                (uid, today_str)
            ).fetchone()[0]

        goal = goal or 8

        if total >= goal:
            continue

        missing = goal - total

        try:
            bot.send_message(
                uid,
                f"⏰ <b>Напоминание</b>\n\n"
                f"Сегодня: <b>{total:.1f}ч</b>\n"
                f"Осталось: <b>{missing:.1f}ч</b>"
            )

            with conn() as c:
                c.execute(
                    "INSERT OR IGNORE INTO reminders(user_id,date) VALUES(?,?)",
                    (uid, today_str)
                )
                c.commit()

        except:
            pass

# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(msg):
    uid = msg.chat.id

    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO users(user_id,name) VALUES(?,?)",
            (uid, msg.from_user.first_name)
        )
        c.commit()

    bot.send_message(uid, "🚀 Tracker V2", reply_markup=main_menu())

# =========================
# ADMIN
# =========================

@bot.message_handler(commands=["admin"])
def admin(msg):
    if msg.chat.id not in ADMIN_IDS:
        return

    with conn() as c:
        u = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        l = c.execute("SELECT COUNT(*) FROM logs").fetchone()[0]

    bot.send_message(msg.chat.id, f"👤 {u}\n📝 {l}")

# =========================
# FLOW
# =========================

def flow(uid, text):
    step = state[uid]

    if step == "project":
        if text == "🔙 Назад":
            state.pop(uid, None)
            bot.send_message(uid, "Меню", reply_markup=main_menu())
            return

        temp[uid] = {"project": text}
        state[uid] = "hours"
        bot.send_message(uid, "Сколько часов?", reply_markup=hours_menu())

    elif step == "hours":
        try:
            h = float(text.replace(",", "."))
            if h <= 0 or h > 24:
                raise ValueError()

            save_log(uid, temp[uid]["project"], h)

            bot.send_message(uid, f"✅ {h}ч", reply_markup=main_menu())

        except:
            bot.send_message(uid, "0–24", reply_markup=hours_menu())
            return

        state.pop(uid, None)
        temp.pop(uid, None)

    elif step == "goal":
        try:
            g = float(text.replace(",", "."))
            with conn() as c:
                c.execute("UPDATE users SET goal=? WHERE user_id=?", (g, uid))
                c.commit()

            bot.send_message(uid, f"🎯 {g}ч", reply_markup=main_menu())

        except:
            bot.send_message(uid, "Ошибка")

        state.pop(uid, None)

# =========================
# HANDLER
# =========================

@bot.message_handler(func=lambda m: True)
def handler(msg):
    uid = msg.chat.id
    text = msg.text.strip()

    if text.startswith("+"):
        quick_add(uid, text)
        return

    if uid in state:
        flow(uid, text)
        return

    if text == "➕ Добавить":
        state[uid] = "project"
        bot.send_message(uid, "Проект", reply_markup=projects_menu())

    elif text == "📊 Сегодня":
        report_today(uid)

    elif text == "📆 Неделя":
        report_week(uid)

    elif text == "🔥 Streak":
        bot.send_message(uid, f"🔥 {streak(uid)}", reply_markup=main_menu())

    elif text == "🎯 Цель":
        state[uid] = "goal"
        bot.send_message(uid, "Цель", reply_markup=main_menu())

    elif text == "📁 Проекты":
        project_stats(uid)

    else:
        bot.send_message(uid, "Меню", reply_markup=main_menu())

# =========================
# SCHEDULER
# =========================

scheduler = BackgroundScheduler()

scheduler.add_job(send_reminders, "cron", hour=18, minute=0)
scheduler.start()

# =========================
# RUN
# =========================

print("Bot started")

while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(e)
        time.sleep(5)

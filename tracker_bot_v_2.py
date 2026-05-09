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

ADMIN_IDS = [1427099343]  # <-- вставь свой Telegram ID

DB = "tracker_v2.db"

bot = TeleBot(TOKEN, parse_mode="HTML")

# =========================
# DATABASE
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


def save_log(user_id, project, hours):
    with conn() as c:
        c.execute(
            """
            INSERT INTO logs(user_id, date, project, hours)
            VALUES(?,?,?,?)
            """,
            (user_id, today(), project, hours)
        )

        c.execute(
            """
            UPDATE users
            SET last_project=?
            WHERE user_id=?
            """,
            (project, user_id)
        )

        c.commit()


# =========================
# REPORTS
# =========================

def report_today(user_id):
    with conn() as c:

        total = c.execute(
            """
            SELECT COALESCE(SUM(hours),0)
            FROM logs
            WHERE user_id=? AND date=?
            """,
            (user_id, today())
        ).fetchone()[0]

        goal = c.execute(
            """
            SELECT goal
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        ).fetchone()

    goal_value = goal[0] if goal else 8

    percent = 0

    if goal_value > 0:
        percent = min(100, int((total / goal_value) * 100))

    text = (
        f"📊 <b>Сегодня</b>\n\n"
        f"⏱ {total:.1f}ч / {goal_value:.1f}ч\n"
        f"📈 Выполнено: {percent}%"
    )

    bot.send_message(
        user_id,
        text,
        reply_markup=main_menu()
    )


def report_week(user_id):
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    with conn() as c:
        total = c.execute(
            """
            SELECT COALESCE(SUM(hours),0)
            FROM logs
            WHERE user_id=? AND date>=?
            """,
            (user_id, since)
        ).fetchone()[0]

    bot.send_message(
        user_id,
        f"📆 За 7 дней: <b>{total:.1f}ч</b>",
        reply_markup=main_menu()
    )


def streak(user_id):
    with conn() as c:
        rows = c.execute(
            """
            SELECT DISTINCT date
            FROM logs
            WHERE user_id=?
            ORDER BY date DESC
            """,
            (user_id,)
        ).fetchall()

    dates = [r[0] for r in rows]

    if not dates:
        return 0

    current = datetime.now().date()
    streak_days = 0

    for d in dates:
        log_date = datetime.strptime(d, "%Y-%m-%d").date()

        if log_date == current:
            streak_days += 1
            current -= timedelta(days=1)
        else:
            break

    return streak_days


def project_stats(user_id):
    with conn() as c:
        rows = c.execute(
            """
            SELECT project, SUM(hours)
            FROM logs
            WHERE user_id=?
            GROUP BY project
            ORDER BY SUM(hours) DESC
            """,
            (user_id,)
        ).fetchall()

    if not rows:
        bot.send_message(
            user_id,
            "Нет данных",
            reply_markup=main_menu()
        )
        return

    text = "📁 <b>Проекты</b>\n\n"

    for project, hours in rows:
        text += f"• {project}: {hours:.1f}ч\n"

    bot.send_message(
        user_id,
        text,
        reply_markup=main_menu()
    )

# =========================
# QUICK ADD
# =========================

def quick_add(user_id, text):
    try:
        arr = text[1:].split()

        hours = float(arr[0].replace(",", "."))

        if hours <= 0 or hours > 24:
            raise ValueError()

        project = arr[1] if len(arr) > 1 else "Work"

        save_log(user_id, project, hours)

        bot.send_message(
            user_id,
            f"⚡ Добавлено: {hours}ч [{project}]",
            reply_markup=main_menu()
        )

    except:
        bot.send_message(
            user_id,
            "Формат:\n<code>+2 Work</code>",
            reply_markup=main_menu()
        )

# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(msg):
    user_id = msg.chat.id

    with conn() as c:
        c.execute(
            """
            INSERT OR IGNORE INTO users(user_id, name)
            VALUES(?,?)
            """,
            (user_id, msg.from_user.first_name)
        )

        c.commit()

    bot.send_message(
        user_id,
        "🚀 <b>Tracker V2 запущен</b>",
        reply_markup=main_menu()
    )

# =========================
# ADMIN
# =========================

@bot.message_handler(commands=["admin"])
def admin(msg):

    if msg.chat.id not in ADMIN_IDS:
        return

    with conn() as c:

        users = c.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        logs = c.execute(
            "SELECT COUNT(*) FROM logs"
        ).fetchone()[0]

    bot.send_message(
        msg.chat.id,
        f"👤 Users: {users}\n📝 Logs: {logs}"
    )

# =========================
# FLOW
# =========================

def process_flow(user_id, text):

    step = state[user_id]

    # ----------
    # PROJECT
    # ----------

    if step == "project":

        if text == "🔙 Назад":
            state.pop(user_id, None)

            bot.send_message(
                user_id,
                "Меню",
                reply_markup=main_menu()
            )
            return

        temp[user_id] = {
            "project": text
        }

        state[user_id] = "hours"

        bot.send_message(
            user_id,
            "Сколько часов?",
            reply_markup=hours_menu()
        )

    # ----------
    # HOURS
    # ----------

    elif step == "hours":

        if text == "🔙 Назад":

            state[user_id] = "project"

            bot.send_message(
                user_id,
                "Выбери проект",
                reply_markup=projects_menu()
            )

            return

        try:
            hours = float(text.replace(",", "."))

            if hours <= 0 or hours > 24:
                raise ValueError()

            project = temp[user_id]["project"]

            save_log(user_id, project, hours)

            bot.send_message(
                user_id,
                f"✅ Добавлено: {hours}ч [{project}]",
                reply_markup=main_menu()
            )

        except:
            bot.send_message(
                user_id,
                "Введите число от 0 до 24",
                reply_markup=hours_menu()
            )
            return

        state.pop(user_id, None)
        temp.pop(user_id, None)

    # ----------
    # GOAL
    # ----------

    elif step == "goal":

        try:
            goal = float(text.replace(",", "."))

            if goal <= 0 or goal > 24:
                raise ValueError()

            with conn() as c:
                c.execute(
                    """
                    UPDATE users
                    SET goal=?
                    WHERE user_id=?
                    """,
                    (goal, user_id)
                )

                c.commit()

            bot.send_message(
                user_id,
                f"🎯 Цель обновлена: {goal}ч",
                reply_markup=main_menu()
            )

        except:
            bot.send_message(
                user_id,
                "Введите число от 1 до 24",
                reply_markup=main_menu()
            )

        state.pop(user_id, None)

# =========================
# MAIN HANDLER
# =========================

@bot.message_handler(func=lambda m: True)
def handler(msg):

    user_id = msg.chat.id
    text = msg.text.strip()

    # QUICK ADD

    if text.startswith("+"):
        quick_add(user_id, text)
        return

    # FLOW

    if user_id in state:
        process_flow(user_id, text)
        return

    # MENU

    if text == "➕ Добавить":

        state[user_id] = "project"

        bot.send_message(
            user_id,
            "Выбери проект",
            reply_markup=projects_menu()
        )

    elif text == "📊 Сегодня":
        report_today(user_id)

    elif text == "📆 Неделя":
        report_week(user_id)

    elif text == "🔥 Streak":

        s = streak(user_id)

        bot.send_message(
            user_id,
            f"🔥 Серия: <b>{s}</b> дней",
            reply_markup=main_menu()
        )

    elif text == "🎯 Цель":

        state[user_id] = "goal"

        bot.send_message(
            user_id,
            "Введи дневную цель в часах",
            reply_markup=main_menu()
        )

    elif text == "📁 Проекты":
        project_stats(user_id)

    else:
        bot.send_message(
            user_id,
            "Используй меню 👇",
            reply_markup=main_menu()
        )

# =========================
# DAILY PUSH
# =========================

def daily_push():

    with conn() as c:
        users = c.execute(
            "SELECT user_id FROM users"
        ).fetchall()

    for (user_id,) in users:

        try:
            report_today(user_id)

        except Exception as e:
            print(f"Push error: {e}")

# =========================
# SCHEDULER
# =========================

scheduler = BackgroundScheduler()

scheduler.add_job(
    daily_push,
    "cron",
    hour=23,
    minute=0
)

scheduler.start()

# =========================
# RUN
# =========================

print("Bot started successfully")

while True:

    try:
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60
        )

    except Exception as e:

        print(f"Polling error: {e}")

        time.sleep(5)

import os
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

@bot.message_handler(commands=['start','month','top','reset','export','goal','graph','pomodoro','leaderboard'])
def start(msg):
    if msg.text.startswith('/month'):
        report_month(msg.chat.id); return
    if msg.text.startswith('/top'):
        project_stats(msg.chat.id); return
    if msg.text.startswith('/reset'):
        reset_logs(msg.chat.id); return
    if msg.text.startswith('/export'):
        export_logs(msg.chat.id); return
    if msg.text.startswith('/goal'):
        parts=msg.text.split()
        if len(parts)>1:
            set_goal(msg.chat.id, parts[1]); return
    if msg.text.startswith('/graph'):
        report_month(msg.chat.id); return
    if msg.text.startswith('/pomodoro'):
        bot.send_message(msg.chat.id,'🍅 Таймер запущен. Вернусь через 25 минут (demo).'); return
    if msg.text.startswith('/leaderboard'):
        leaderboard(msg.chat.id); return
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

def report_month(uid):
    since=(datetime.now()-timedelta(days=30)).strftime('%Y-%m-%d')
    with conn() as c:
        val=c.execute('SELECT COALESCE(SUM(hours),0) FROM logs WHERE user_id=? AND date>=?',(uid,since)).fetchone()[0]
    bot.send_message(uid,f'📅 За 30 дней: {val:.1f}ч')

def reset_logs(uid):
    with conn() as c:
        c.execute('DELETE FROM logs WHERE user_id=?',(uid,))
    bot.send_message(uid,'🗑 Данные очищены')

def export_logs(uid):
    with conn() as c:
        rows=c.execute('SELECT date,project,hours FROM logs WHERE user_id=? ORDER BY date DESC',(uid,)).fetchall()
    txt='date,project,hours
'+'
'.join([f'{a},{b},{d}' for a,b,d in rows])
    bot.send_document(uid, ('export.csv', txt.encode('utf-8')))

def set_goal(uid,val):
    try:
        g=float(val)
        with conn() as c:
            c.execute('UPDATE users SET goal=? WHERE user_id=?',(g,uid))
        bot.send_message(uid,f'🎯 Цель обновлена: {g}ч')
    except:
        bot.send_message(uid,'Используй: /goal 8')

def leaderboard(uid):
    with conn() as c:
        rows=c.execute('SELECT name, COALESCE((SELECT SUM(hours) FROM logs l WHERE l.user_id=u.user_id),0) total FROM users u ORDER BY total DESC LIMIT 10').fetchall()
    txt='🏆 Leaderboard\n'+'\n'.join([f'{i+1}. {n}: {t:.1f}ч' for i,(n,t) in enumerate(rows)])
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

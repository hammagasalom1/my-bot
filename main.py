import telebot
import sqlite3
from telebot import types

BOT_TOKEN = "8964494734:AAHlMZ-QRXsSvyN_MGZ8bioCvRX8N0aadYQ"
bot = telebot.TeleBot(BOT_TOKEN)

CHANNEL_USERNAME = "@majburiy_math_2"

# --- BAZA ---
def init_db():
    conn = sqlite3.connect('mega_bot_new.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, ref_count INTEGER DEFAULT 0, name TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS tests (code TEXT PRIMARY KEY, answers TEXT, title TEXT, author_id INTEGER, author_name TEXT, count INTEGER)')
    conn.commit()
    conn.close()

init_db()

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except:
        return False
    return False

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if not check_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))
        markup.add(types.InlineKeyboardButton("🔄 Tekshirish", callback_data="check_sub"))
        bot.send_message(user_id, f"⚠️ Botdan foydalanish uchun avval kanalimizga obuna bo'ling:\n{CHANNEL_USERNAME}", reply_markup=markup)
        return

    name = message.from_user.first_name
    conn = sqlite3.connect('mega_bot_new.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)', (user_id, name))
    conn.commit()
    conn.close()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Profil", "🔍 Kodli test")
    markup.row("🏆 Reyting", "🎁 Referal", "➕ Test qo'shish")
    bot.send_message(user_id, "Xush kelibsiz! Kerakli bo'limni tanlang.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check(call):
    if check_subscription(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Rahmat! Obuna tasdiqlandi.")
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "Siz hali obuna bo'lmadingiz!", show_alert=True)

# --- MENYU ---
@bot.message_handler(func=lambda message: message.text in ["👤 Profil", "🏆 Reyting", "🎁 Referal", "🔍 Kodli test", "➕ Test qo'shish"])
def menu_handler(message):
    if not check_subscription(message.chat.id):
        return start(message)
    
    if message.text == "👤 Profil":
        conn = sqlite3.connect('mega_bot_new.db')
        cursor = conn.cursor()
        cursor.execute('SELECT points, ref_count FROM users WHERE id = ?', (message.chat.id,))
        row = cursor.fetchone()
        conn.close()
        pts = row[0] if row else 0
        bot.send_message(message.chat.id, f"👤 Profilingiz:\n⭐ Ballar: {pts}")
        
    elif message.text == "🏆 Reyting":
        conn = sqlite3.connect('mega_bot_new.db')
        cursor = conn.cursor()
        cursor.execute('SELECT name, points FROM users ORDER BY points DESC LIMIT 10')
        top = cursor.fetchall()
        conn.close()
        text = "🏆 **Top 10 o'quvchilar:**\n\n"
        for i, u in enumerate(top):
            uname = u[0] if u[0] else "Foydalanuvchi"
            text += f"{i+1}. {uname} — ⭐ {u[1]} ball\n"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
    elif message.text == "🎁 Referal":
        bot_info = bot.get_me()
        bot.send_message(message.chat.id, f"🎁 Do'stlaringizni taklif qiling:\nhttps://t.me/{bot_info.username}?start=ref_{message.chat.id}")

    elif message.text == "🔍 Kodli test":
        bot.send_message(message.chat.id, "Test kodini kiriting (masalan: 1):")
        bot.register_next_step_handler(message, get_test_code)

    elif message.text == "➕ Test qo'shish":
        bot.send_message(message.chat.id, "Test nomini kiriting (masalan: Matematika):")
        bot.register_next_step_handler(message, get_test_title)

# --- TEST YARATISH JARAYONI ---
def get_test_title(message):
    title = message.text.strip()
    bot.send_message(message.chat.id, "Test kodini kiriting (masalan: 1):")
    bot.register_next_step_handler(message, lambda msg: get_test_code_input(msg, title))

def get_test_code_input(message, title):
    code = message.text.strip()
    bot.send_message(message.chat.id, "To'g'ri javoblarni ketma-ket yuboring (masalan: ABCD):")
    bot.register_next_step_handler(message, lambda msg: save_final_test(msg, title, code))

def save_final_test(message, title, code):
    answers = message.text.strip().upper()
    count = len(answers)
    author_id = message.chat.id
    author_name = message.from_user.first_name

    conn = sqlite3.connect('mega_bot_new.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO tests (code, answers, title, author_id, author_name, count) VALUES (?, ?, ?, ?, ?, ?)', 
                   (code, answers, title, author_id, author_name, count))
    conn.commit()
    conn.close()

    bot_info = bot.get_me()
    bot_username = bot_info.username

    text = (
        f"✅ **Test ishlanishga tayyor**\n"
        f"📝 Test nomi: *{title}*\n"
        f"🔢 Testlar soni: *{count} ta*\n"
        f"‼️ Test kodi: *{code}*\n"
        f"👤 Test yaratuvchisi: *{author_name}*\n\n"
        f"Test javoblarini quyidagi botga jo'nating:\n"
        f"👉 @{bot_username}\n"
        f"👉 @{bot_username}\n"
        f"👉 @{bot_username}\n\n"
        f"📌 Testda qatnashish uchun @{bot_username} ga kirib **{code}** kodini botga yuboring.\n\n"
        f"♻️ Test ishlanishga tayyor!!!"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- TEST YECHISH VA XABAR BERISH ---
def get_test_code(message):
    code = message.text.strip()
    conn = sqlite3.connect('mega_bot_new.db')
    cursor = conn.cursor()
    cursor.execute('SELECT answers, title, author_id FROM tests WHERE code = ?', (code,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        bot.send_message(message.chat.id, f"Test topildi! ({row[1]})\nJavoblaringizni yuboring (masalan: ABCD):")
        bot.register_next_step_handler(message, lambda msg: check_answers(msg, row[0], row[1], row[2]))
    else:
        bot.send_message(message.chat.id, "Bunday kodli test topilmadi.")

def check_answers(message, correct, title, author_id):
    ans = message.text.strip().upper()
    score = sum(1 for i, a in enumerate(ans) if i < len(correct) and a == correct[i])
    student_id = message.chat.id
    student_name = message.from_user.first_name

    conn = sqlite3.connect('mega_bot_new.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET points = points + ? WHERE id = ?', (score, student_id))
    conn.commit()
    conn.close()
    
    # O'quvchiga xabar
    bot.send_message(student_id, f"Test yakunlandi!\nTest nomi: {title}\nSizning javoblar: {ans}\nTo'g'ri javoblar: {correct}\nTo'plagan ballingiz: {score}")

    # Ustozga xabar yuborish
    try:
        teacher_text = (
            f"🔔 **Yangi natija!**\n\n"
            f"📖 Test: *{title}*\n"
            f"👤 O'quvchi: *{student_name}* (ID: `{student_id}`)\n"
            f"📝 O'quvchi javoblari: `{ans}`\n"
            f"⭐ To'plagan bali: *{score}*"
        )
        bot.send_message(author_id, teacher_text, parse_mode="Markdown")
    except:
        pass

if __name__ == "__main__":
    bot.polling(none_stop=True)



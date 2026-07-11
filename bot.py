import telebot
from telebot import types
import time
import threading

TOKEN = "8847806274:AAFzIJ3NEfVqT2spEiDLHNHqR4P6qmumfXI"
bot = telebot.TeleBot(TOKEN)
KANAL_ID = "@majburiy_math_2"

TEST_BAZASI = {
    "1": {"javoblar": "bacababcbbcdbsbbbbbbccbacbbcbb", "nomi": "Majburiy fanlar testi", "vaqt": 900},
    "2": {"javoblar": "a" * 90, "nomi": "DTM namunaviy test", "vaqt": 5400},
    "3": {"javoblar": "abc", "nomi": "Milliy sertifikat testi", "vaqt": 9000},
    "4": {"javoblar": "abb", "nomi": "Asosiy fanlar testi", "vaqt": 3600}
}

user_states = {}

def check_sub(user_id):
    try:
        member = bot.get_chat_member(KANAL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

@bot.message_handler(commands=['start'])
def start_message(message):
    show_main_menu(message.chat.id)

def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("📝 Test ishlash"))
    bot.send_message(chat_id, "Asosiy menyu:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📝 Test ishlash")
def test_ishlash_bolimi(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 Majburiy fanlar (Kod: 1)", "📝 DTM Test (Kod: 2)", "📜 Milliy Sertifikat (Kod: 3)", "🧮 Asosiy fanlar (Kod: 4)")
    bot.send_message(message.chat.id, "Qaysi bo'lim bo'yicha test ishlamoqchisiz?", reply_markup=markup)

bot.infinity_polling()

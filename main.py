import sqlite3
import logging
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardRemove
)

# Logging sozlamasi
logging.basicConfig(level=logging.INFO)

# =========================================================
# ASOSIY SOZLAMALAR
# =========================================================
BOT_TOKEN = "8847765694:AAFuN87LbEkvgTJLE6bZTgFLkJ1NQvLSVuI"
ADMIN_ID = 7649769072

# MAJBURIY OBUNA KANALLARI
CHANNELS = [
    {
        "name": "Majburiy Matematika", 
        "url": "https://t.me/majburiy_math_2", 
        "id": "@majburiy_math_2"
    }
]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =========================================================
# MA'LUMOTLAR BAZASI (SQLITE3)
# =========================================================
def init_db():
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            score INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            invites_count INTEGER DEFAULT 0
        )
    """)
    
    # Testlar jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_type TEXT,
            subject TEXT,
            question TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct_option TEXT,
            is_vip INTEGER DEFAULT 0
        )
    """)
    
    # Ustozlar testi
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teacher_quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER,
            subject TEXT,
            answers_key TEXT,
            time_limit INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Test natijalari
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            correct_count INTEGER,
            total_count INTEGER,
            user_answers TEXT
        )
    """)

    # PDF Kutubxona
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            file_id TEXT
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# --- YORDAMCHI FUNKSIYALAR ---
def get_user(user_id: int):
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, full_name, username, score, referred_by, invites_count FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(user_id: int, full_name: str, username: str, referrer_id: int = 0):
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (user_id, full_name, username, score, referred_by, invites_count) VALUES (?, ?, ?, 0, ?, 0)",
            (user_id, full_name, username, referrer_id)
        )
        if referrer_id != 0 and referrer_id != user_id:
            cursor.execute("UPDATE users SET score = score + 10, invites_count = invites_count + 1 WHERE user_id = ?", (referrer_id,))
        conn.commit()
    conn.close()

def update_user_score(user_id: int, points: int):
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET score = score + ? WHERE user_id = ?", (points, user_id))
    conn.commit()
    conn.close()

def get_top_users():
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, score FROM users ORDER BY score DESC LIMIT 10")
    top_users = cursor.fetchall()
    conn.close()
    return top_users

def get_all_users_count():
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_user_ids():
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_rank(score: int) -> str:
    if score < 50: return "🌱 Boshlovchi"
    elif score < 150: return "📖 Bilimdon"
    elif score < 300: return "🎓 Izlanuvchi"
    elif score < 600: return "⚡️ Bilimlar Ustasi"
    elif score < 1000: return "🔥 DTM Qiroli"
    else: return "🏆 Afsona"

# =========================================================
# MAJBURIY OBUNANI TEKSHIRISH
# =========================================================
async def check_subscriptions(user_id: int) -> bool:
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logging.error(f"Obuna tekshirishda xatolik: {e}")
            return True
    return True

def get_sub_keyboard():
    keyboard = []
    for ch in CHANNELS:
        keyboard.append([InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch["url"])])
    keyboard.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# =========================================================
# FSM HOLATLARI
# =========================================================
class CreateTeacherQuiz(StatesGroup):
    subject = State()
    answers_key = State()
    time_limit = State()

class SolveTeacherQuiz(StatesGroup):
    quiz_id = State()
    user_answers = State()

class BroadcastState(StatesGroup):
    message = State()

class AddBookState(StatesGroup):
    title = State()
    file = State()

class AddVipTestState(StatesGroup):
    question = State()
    options = State()
    correct = State()

# =========================================================
# TUGMALAR (KEYBOARDS) - Duel olib tashlandi
# =========================================================
def get_main_menu(user_id: int):
    buttons = [
        [KeyboardButton(text="🔒 Yopiq VIP Testlar"), KeyboardButton(text="🎯 DTM Blok Test (3+2)")],
        [KeyboardButton(text="📚 Raqamli Kutubxona"), KeyboardButton(text="👨‍🏫 Ustozlar bo'limi")],
        [KeyboardButton(text="🔑 Test topshirish"), KeyboardButton(text="👤 Profilim")],
        [KeyboardButton(text="🎁 Do'stlarni taklif qilish"), KeyboardButton(text="🏆 Liderlar ro'yxati")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="👑 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_teacher_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Yangi kodli test yaratish")],
            [KeyboardButton(text="📊 Mening testlarim natijalari")],
            [KeyboardButton(text="🛑 Testni yakunlash")],
            [KeyboardButton(text="⬅️ Bosh menyu")]
        ],
        resize_keyboard=True
    )

def get_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔒 VIP Test qo'shish")],
            [KeyboardButton(text="📚 Kutubxonaga kitob qo'shish")],
            [KeyboardButton(text="📢 Ommaviy xabar yuborish")],
            [KeyboardButton(text="📈 Bot statistikasi")],
            [KeyboardButton(text="🛑 Ixtiyoriy testni yakunlash (Admin)")],
            [KeyboardButton(text="⬅️ Bosh menyu")]
        ],
        resize_keyboard=True
    )

# =========================================================
# START VA BOSH HANDLERLAR
# =========================================================
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username or "Mavjud emas"

    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])

    add_user(user_id, full_name, username, referrer_id)

    if not await check_subscriptions(user_id):
        await message.answer(
            "⚠️ **Botdan foydalanish uchun rasmiy kanalga obuna bo'ling:**", 
            parse_mode="Markdown", 
            reply_markup=get_sub_keyboard()
        )
        return

    welcome_text = f"👋 **Salom, {full_name}!**\n🎓 **Imtihon hamrohi** botiga xush kelibsiz!\n👇 Kerakli bo'limni tanlang:"
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu(user_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    if await check_subscriptions(callback.from_user.id):
        await callback.answer("✅ Obuna tasdiqlandi!", show_alert=True)
        await callback.message.delete()
        await callback.message.answer("🎉 Xush kelibsiz!", reply_markup=get_main_menu(callback.from_user.id))
    else:
        await callback.answer("❌ Hali kanalga obuna bo'lmadingiz!", show_alert=True)

@dp.message(F.text == "⬅️ Bosh menyu")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Bosh menyudasiz:", reply_markup=get_main_menu(message.from_user.id))

# =========================================================
# 🔒 YOPIQ VIP TESTLAR
# =========================================================
@dp.message(F.text == "🔒 Yopiq VIP Testlar")
async def vip_tests_section(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("⚠️ Botdan foydalanish uchun avval kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return

    user = get_user(message.from_user.id)
    invites = user[5] if user else 0

    if invites < 2:
        bot_info = await bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
        
        lock_msg = (
            f"🔒 **Yopiq VIP Testlar bo'limi qulflangan!**\n\n"
            f"Ushbu maxfiy va murakkab testlarni yechish uchun **kamida 2 ta do'stingizni** botga taklif qilishingiz kerak.\n\n"
            f"📊 Siz taklif qildingiz: **{invites} / 2 ta**\n\n"
            f"🔗 Sizning taklif havolangiz:\n`{ref_link}`\n\n"
            f"💡 *Yana {2 - invites} ta do'stingiz ushbu havola orqali botga kirsa, bo'lim avtomatik ochiladi!*"
        )
        await message.answer(lock_msg, parse_mode="Markdown")
        return

    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, question, option_a, option_b, option_c, option_d FROM tests WHERE is_vip = 1 ORDER BY RANDOM() LIMIT 1")
    test = cursor.fetchone()
    conn.close()

    if not test:
        await message.answer("🔓 **VIP bo'lim ochilgan!** Hozirda testlar bazasi yangilanmoqda.")
        return

    t_id, q, a, b, c, d = test
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"A) {a}", callback_data=f"vip_ans_{t_id}_A"), InlineKeyboardButton(text=f"B) {b}", callback_data=f"vip_ans_{t_id}_B")],
        [InlineKeyboardButton(text=f"C) {c}", callback_data=f"vip_ans_{t_id}_C"), InlineKeyboardButton(text=f"D) {d}", callback_data=f"vip_ans_{t_id}_D")]
    ])
    await message.answer(f"🔒 **VIP TEST:**\n\n❓ {q}", reply_markup=kb)

@dp.callback_query(F.data.startswith("vip_ans_"))
async def handle_vip_answer(callback: types.CallbackQuery):
    _, _, t_id, user_ans = callback.data.split("_")
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT correct_option FROM tests WHERE id = ?", (t_id,))
    correct = cursor.fetchone()[0]
    conn.close()

    if user_ans == correct:
        update_user_score(callback.from_user.id, 5)
        await callback.answer("🎉 To'g'ri javob! +5 VIP ball!", show_alert=True)
    else:
        await callback.answer(f"❌ Noto'g'ri! To'g'ri javob: {correct}", show_alert=True)
    await callback.message.delete()

# =========================================================
# 🎯 DTM BLOK TEST
# =========================================================
@dp.message(F.text == "🎯 DTM Blok Test (3+2)")
async def dtm_block_test(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return

    msg = (
        "🎯 **DTM BLOK TEST SIMULYATSIYASI**\n\n"
        "Siz 5 ta fan bo'yicha imtihon topshirasiz:\n"
        "1. Ona tili (Majburiy) - 10 ta\n"
        "2. Matematika (Majburiy) - 10 ta\n"
        "3. Tarix (Majburiy) - 10 ta\n"
        "4. 1-Asosiy fan - 30 ta\n"
        "5. 2-Asosiy fan - 30 ta\n\n"
        "⏱ **Jami vaqt:** 3 soat\n"
        "📊 **Maksimal ball:** 189.0 ball\n\n"
        "🚀 *Tayyormisiz? Imtihonni boshlash uchun quyidagi tugmani bosing:*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Imtihonni boshlash", callback_data="start_dtm_block")]])
    await message.answer(msg, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "start_dtm_block")
async def start_dtm_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("📝 **DTM Imtihoni boshlandi!**\n\n1-Savol: 2x + 5 = 15 bo'lsa, x ni toping.\n\nA) 5\nB) 10\nC) 2\nD) 8")

# =========================================================
# 📚 RAQAMLI KUTUBXONA (PDF)
# =========================================================
@dp.message(F.text == "📚 Raqamli Kutubxona")
async def library_section(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("⚠️ Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return

    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM library")
    books = cursor.fetchall()
    conn.close()

    if not books:
        await message.answer("📚 Kutubxonada hozircha kitoblar mavjud emas.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=title, callback_data=f"get_book_{b_id}")] for b_id, title in books])
    await message.answer("📚 **Yuklab olish uchun darslikni tanlang:**", reply_markup=kb)

@dp.callback_query(F.data.startswith("get_book_"))
async def send_book(callback: types.CallbackQuery):
    b_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, file_id FROM library WHERE id = ?", (b_id,))
    book = cursor.fetchone()
    conn.close()

    if book:
        title, file_id = book
        await callback.message.answer_document(document=file_id, caption=f"📖 {title}")
    await callback.answer()

# =========================================================
# USTOZLAR BO'LIMI
# =========================================================
@dp.message(F.text == "👨‍🏫 Ustozlar bo'limi")
async def teacher_section(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("⚠️ Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return
    await message.answer("👨‍🏫 **Ustozlar bo'limiga xush kelibsiz!**", parse_mode="Markdown", reply_markup=get_teacher_menu())

@dp.message(F.text == "➕ Yangi kodli test yaratish")
async def start_create_quiz(message: types.Message, state: FSMContext):
    await state.set_state(CreateTeacherQuiz.subject)
    await message.answer("📚 Test fanini kiriting:", reply_markup=ReplyKeyboardRemove())

@dp.message(CreateTeacherQuiz.subject)
async def process_quiz_subject(message: types.Message, state: FSMContext):
    await state.update_data(subject=message.text)
    await state.set_state(CreateTeacherQuiz.answers_key)
    await message.answer("🔑 Javoblar kalitini kiriting (masalan: `1a2b3c...` yoki `abcd`):", parse_mode="Markdown")

@dp.message(CreateTeacherQuiz.answers_key)
async def process_quiz_key(message: types.Message, state: FSMContext):
    key = message.text.lower().replace(" ", "").replace("\n", "")
    await state.update_data(answers_key=key)
    await state.set_state(CreateTeacherQuiz.time_limit)
    await message.answer("⏱ Test uchun vaqt cheklovini kiriting (daqiqalarda, masalan: `30`). Cheklov bo'lmasa `0` deb yozing:")

@dp.message(CreateTeacherQuiz.time_limit)
async def process_quiz_time(message: types.Message, state: FSMContext):
    time_limit = int(message.text) if message.text.isdigit() else 0
    data = await state.get_data()
    
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO teacher_quizzes (teacher_id, subject, answers_key, time_limit, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (message.from_user.id, data['subject'], data['answers_key'], time_limit))
    quiz_id = cursor.lastrowid
    conn.commit()
    conn.close()

    time_txt = f"{time_limit} daqiqa" if time_limit > 0 else "Cheklovsiz"
    await message.answer(
        f"✅ **Test yaratildi!**\n\n📌 **Test Kodi:** `{quiz_id}`\n📚 **Fan:** {data['subject']}\n⏱ **Vaqt:** {time_txt}\n📢 Kodni o'quvchilarga yuboring!",
        parse_mode="Markdown",
        reply_markup=get_teacher_menu()
    )
    await state.clear()

@dp.message(F.text == "📊 Mening testlarim natijalari")
async def view_my_quizzes(message: types.Message):
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT quiz_id, subject, is_active FROM teacher_quizzes WHERE teacher_id = ?", (message.from_user.id,))
    quizzes = cursor.fetchall()

    if not quizzes:
        await message.answer("Sizda hali yaratilgan testlar yo'q.")
        conn.close()
        return

    text = "📊 **Siz yaratgan testlar natijalari:**\n\n"
    for q_id, subj, active in quizzes:
        status = "🟢 Faol" if active == 1 else "🔴 Yakunlangan"
        cursor.execute("SELECT user_name, correct_count, total_count FROM test_results WHERE quiz_id = ?", (q_id,))
        results = cursor.fetchall()
        text += f"🔹 **Test Kodi:** `{q_id}` | {subj} ({status})\n"
        if results:
            for name, corr, tot in results:
                text += f"  👤 {name}: {corr}/{tot} ta\n"
        else:
            text += "  ⚠️ Hali hech kim topshirmadi.\n"
        text += "-------------------------------\n"

    conn.close()
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_({"🛑 Testni yakunlash", "🛑 Ixtiyoriy testni yakunlash (Admin)"}))
async def finish_quiz_prompt(message: types.Message):
    await message.answer("🛑 Yakunlamoqchi bo'lgan test kodini kiriting:")

@dp.message(F.text)
async def process_finish_quiz(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        quiz_id = int(message.text)
        conn = sqlite3.connect("quiz_bot_full.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE teacher_quizzes SET is_active = 0 WHERE quiz_id = ?", (quiz_id,))
        conn.commit()
        conn.close()
        await message.answer(f"✅ **{quiz_id}**-sonli test yakunlandi!")

# =========================================================
# O'QUVCHILAR TEST TOPSHIRISH
# =========================================================
@dp.message(F.text == "🔑 Test topshirish")
async def start_solve_quiz(message: types.Message, state: FSMContext):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("⚠️ Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return

    await state.set_state(SolveTeacherQuiz.quiz_id)
    await message.answer("🔑 Ustozingiz bergan **Test kodi**ni kiriting:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

@dp.message(SolveTeacherQuiz.quiz_id)
async def process_solve_quiz_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiritasiz!")
        return

    quiz_id = int(message.text)
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("SELECT quiz_id, subject, answers_key, is_active FROM teacher_quizzes WHERE quiz_id = ?", (quiz_id,))
    quiz = cursor.fetchone()
    conn.close()

    if not quiz or quiz[3] == 0:
        await message.answer("❌ Test topilmadi yoki yakunlangan.", reply_markup=get_main_menu(message.from_user.id))
        await state.clear()
        return

    await state.update_data(quiz_id=quiz_id, subject=quiz[1], answers_key=quiz[2])
    await state.set_state(SolveTeacherQuiz.user_answers)
    await message.answer(f"📚 **Fan:** {quiz[1]}\n📝 Javoblarni kiriting (`1a2b...` yoki `abcd`):", parse_mode="Markdown")

@dp.message(SolveTeacherQuiz.user_answers)
async def process_solve_quiz_answers(message: types.Message, state: FSMContext):
    raw_user_key = message.text.lower().replace(" ", "").replace("\n", "")
    data = await state.get_data()
    correct_key = data['answers_key']
    user_key = "".join([c for c in raw_user_key if c.isalpha()])

    if len(user_key) != len(correct_key):
        await message.answer(f"⚠️ Javoblar soni {len(correct_key)} ta bo'lishi kerak!")
        return

    correct_count = sum(1 for i in range(len(correct_key)) if user_key[i] == correct_key[i])
    earned_score = correct_count * 2
    update_user_score(message.from_user.id, earned_score)

    await message.answer(
        f"🎉 **TEST YAKUNLANDI!**\n\n🎯 **Natijangiz:** {correct_count} / {len(correct_key)}\n💎 **To'plangan ball:** +{earned_score} ball",
        reply_markup=get_main_menu(message.from_user.id)
    )
    await state.clear()

# =========================================================
# PROFIL, REFERAL VA REYTING
# =========================================================
@dp.message(F.text == "👤 Profilim")
async def show_profile(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("⚠️ Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return

    user = get_user(message.from_user.id)
    if user:
        u_id, name, uname, score, ref_by, inv_count = user
        await message.answer(
            f"👤 **Profil:**\n🆔 **ID:** `{u_id}`\n✍️ **Ism:** {name}\n💎 **Ball:** {score}\n🎖 **Unvon:** {get_rank(score)}\n👥 **Takliflar:** {inv_count} ta",
            parse_mode="Markdown"
        )

@dp.message(F.text == "🎁 Do'stlarni taklif qilish")
async def invite_friends(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("⚠️ Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return

    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    await message.answer(f"🎁 **Taklif havolangiz:**\n`{ref_link}`\n\nHar bir do'stingiz uchun **+10 ball** va **VIP testlarga ruxsat** beriladi!", parse_mode="Markdown")

@dp.message(F.text == "🏆 Liderlar ro'yxati")
async def show_leaderboard(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("⚠️ Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return

    top = get_top_users()
    text = "🏆 **Top-10 Bilimdonlar:**\n\n"
    for i, (name, score) in enumerate(top, 1):
        text += f"{i}. **{name}** — {score} ball\n"
    await message.answer(text, parse_mode="Markdown")

# =========================================================
# ADMIN PANEL
# =========================================================
@dp.message(Command("admin"))
@dp.message(F.text == "👑 Admin Panel")
async def admin_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 **Admin Panel:**", reply_markup=get_admin_menu())

@dp.message(F.text == "🔒 VIP Test qo'shish")
async def add_vip_prompt(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.set_state(AddVipTestState.question)
    await message.answer("❓ Savol matnini kiriting:")

@dp.message(AddVipTestState.question)
async def add_vip_q(message: types.Message, state: FSMContext):
    await state.update_data(q=message.text)
    await state.set_state(AddVipTestState.options)
    await message.answer("4 ta variantni kiriting (vergul bilan, masalan: `5, 10, 15, 20`):")

@dp.message(AddVipTestState.options)
async def add_vip_opt(message: types.Message, state: FSMContext):
    opts = message.text.split(",")
    if len(opts) != 4:
        await message.answer("4 ta variant kiriting!")
        return
    await state.update_data(a=opts[0].strip(), b=opts[1].strip(), c=opts[2].strip(), d=opts[3].strip())
    await state.set_state(AddVopTestState.correct if 'AddVopTestState' in globals() else AddVipTestState.correct)
    await message.answer("To'g'ri variant harfini kiriting (A, B, C yoki D):")

@dp.message(AddVipTestState.correct)
async def add_vip_corr(message: types.Message, state: FSMContext):
    corr = message.text.upper().strip()
    data = await state.get_data()
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tests (test_type, subject, question, option_a, option_b, option_c, option_d, correct_option, is_vip)
        VALUES ('VIP', 'Aralash', ?, ?, ?, ?, ?, ?, 1)
    """, (data['q'], data['a'], data['b'], data['c'], data['d'], corr))
    conn.commit()
    conn.close()
    await message.answer("✅ VIP Test bazaga qo'shildi!", reply_markup=get_admin_menu())
    await state.clear()

@dp.message(F.text == "📚 Kutubxonaga kitob qo'shish")
async def add_book_prompt(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.set_state(AddBookState.title)
    await message.answer("📖 Kitob nomini kiriting:")

@dp.message(AddBookState.title)
async def add_book_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddBookState.file)
    await message.answer("📁 PDF faylni yuboring:")

@dp.message(AddBookState.file, F.document)
async def add_book_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("quiz_bot_full.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO library (title, file_id) VALUES (?, ?)", (data['title'], message.document.file_id))
    conn.commit()
    conn.close()
    await message.answer("✅ Kitob qo'shildi!", reply_markup=get_admin_menu())
    await state.clear()

@dp.message(F.text == "📢 Ommaviy xabar yuborish")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.set_state(BroadcastState.message)
    await message.answer("📢 Yubormoqchi bo'lgan xabaringizni yozing:")

@dp.message(BroadcastState.message)
async def process_broadcast(message: types.Message, state: FSMContext):
    users = get_all_user_ids()
    count = 0
    for u_id in users:
        try:
            await message.copy_to(chat_id=u_id)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"✅ Xabar **{count}** kishiga yuborildi!", reply_markup=get_admin_menu())
    await state.clear()

@dp.message(F.text == "📈 Bot statistikasi")
async def admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    users_cnt = get_all_users_count()
    await message.answer(f"📊 **Jami foydalanuvchilar:** {users_cnt} ta")

# =========================================================
# BOTNI ISHGA TUSHIRISH
# =========================================================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


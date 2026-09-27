"""
Telegram Bot - aiogram 3.x
Railway + main.py integratsiyasi uchun
"""

import asyncio
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, Contact,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import db
from auth import hash_parol, tekshir_parol
from calculator import hisobla


# ==================== BOT SETUP ====================

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==================== FSM STATES ====================

class VaqtBlokStates(StatesGroup):
    kutish_soat = State()
    kutish_bekor = State()


class MaxfiylikStates(StatesGroup):
    kutish_parol = State()


# ==================== YORDAMCHI FUNKSIYALAR ====================

def webapp_tugma():
    """Web App ochish tugmasi"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🌐 Web App ochish",
            web_app=WebAppInfo(url=config.WEBAPP_URL)
        )
    ]])


def kontakt_tugma():
    """Kontakt yuborish tugmasi"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(
            text="📱 Kontakt yuborish",
            request_contact=True
        )]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def parolni_tekshir(parol: str) -> bool:
    """Parol 5 xonalik son ekanligini tekshirish"""
    return parol.isdigit() and len(parol) == config.PAROL_LENGTH


# ==================== /START ====================

@dp.message(CommandStart())
async def start_handler(message: Message):
    """Start buyrug'i"""
    chat_id = message.chat.id
    user = await db.get_user(chat_id)

    if user:
        await message.answer(
            "👋 Xush kelibsiz!\n\n"
            "📊 Kalkulyator sifatida ishlayman.\n"
            "Istalgan matematik ifodani yuboring:\n"
            "Masalan: `12+12` yoki `(5*8)/2`",
            parse_mode="Markdown"
        )
        return

    await message.answer(
        "👋 Assalomu alaykum!\n\n"
        "Botdan foydalanish uchun avval ro'yxatdan o'ting.\n"
        "📱 Pastdagi tugma orqali kontaktingizni yuboring:",
        reply_markup=kontakt_tugma()
    )


@dp.message(F.contact)
async def contact_handler(message: Message):
    """Kontakt qabul qilish"""
    contact: Contact = message.contact
    chat_id = message.chat.id

    if contact.user_id != chat_id:
        await message.answer("❌ Faqat o'zingizning kontaktingizni yuboring!")
        return

    ism = message.from_user.first_name or ""
    familya = message.from_user.last_name or ""
    username = message.from_user.username or ""
    telefon = contact.phone_number

    await db.add_user(chat_id, ism, familya, username, telefon)

    await message.answer(
        "✅ Ro'yxatdan o'tdingiz!\n\n"
        "📊 Endi kalkulyator sifatida ishlayman.\n"
        "Istalgan matematik ifodani yuboring:\n"
        "Masalan: `12+12` yoki `(5*8)/2`",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )


# ==================== /PAROL.XXXXX (PAROL QO'YISH) ====================

@dp.message(F.text.regexp(r'^/parol\.\d{5}$'))
async def parol_quyish(message: Message):
    """
    Yashirin buyruq: /parol.XXXXX
    Masalan: /parol.23234
    """
    chat_id = message.chat.id
    user = await db.get_user(chat_id)

    if not user:
        await message.answer("❗ Avval /start bosing")
        return

    parol = message.text.split(".")[1].strip()

    if not parolni_tekshir(parol):
        await message.answer(
            f"❌ Parol {config.PAROL_LENGTH} xonalik son bo'lishi kerak"
        )
        return

    await db.update_parol(chat_id, hash_parol(parol))

    try:
        await message.delete()
    except Exception:
        pass

    await message.answer(
        f"✅ Parol saqlandi!\n\n"
        f"📊 Endi kalkulyatordan foydalanishingiz mumkin."
    )


# ==================== /PAROLUZGAR.XXXXX (PAROLNI O'ZGARTIRISH) ====================

@dp.message(F.text.regexp(r'^/paroluzgar\.\d{5}$'))
async def parol_uzgartirish(message: Message):
    """
    Yashirin buyruq: /paroluzgar.XXXXX
    Masalan: /paroluzgar.12123
    """
    chat_id = message.chat.id
    user = await db.get_user(chat_id)

    if not user:
        await message.answer("❗ Avval /start bosing")
        return

    if not user['parol_hash']:
        await message.answer(
            "❗ Sizda parol yo'q.\n"
            "Avval /parol.XXXXX orqali parol qo'ying"
        )
        return

    yangi_parol = message.text.split(".")[1].strip()

    if not parolni_tekshir(yangi_parol):
        await message.answer(
            f"❌ Parol {config.PAROL_LENGTH} xonalik son bo'lishi kerak"
        )
        return

    await db.update_parol(chat_id, hash_parol(yangi_parol))

    try:
        await message.delete()
    except Exception:
        pass

    await message.answer(
        f"✅ Parol o'zgartirildi!\n\n"
        f"🔐 Yangi parolingizni eslab qoling."
    )


# ==================== KALKULYATOR ====================

@dp.message(F.text, ~F.text.startswith('/'))
async def kalkulyator_handler(message: Message, state: FSMContext):
    """Kalkulyator - oddiy matn xabarlar"""
    current_state = await state.get_state()
    if current_state is not None:
        return

    chat_id = message.chat.id
    user = await db.get_user(chat_id)

    if not user:
        await message.answer("❗ Avval /start bosing va ro'yxatdan o'ting")
        return

    natija, xato = hisobla(message.text)

    if xato:
        await message.answer(xato)
        return

    await message.answer(
        f"📊 `{message.text}` = *{natija}*",
        parse_mode="Markdown",
        reply_markup=webapp_tugma()
    )


# ==================== /VAQTBLOK ====================

@dp.message(Command("vaqtblok"))
async def vaqtblok_start(message: Message, state: FSMContext):
    """Yashirin buyruq: /vaqtblok"""
    chat_id = message.chat.id
    user = await db.get_user(chat_id)

    if not user:
        await message.answer("❗ Avval /start bosing")
        return

    if not user['parol_hash']:
        await message.answer(
            "❗ Avval /parol.XXXXX orqali parol qo'ying"
        )
        return

    if user['blok_vaqt'] and user['blok_vaqt'] > datetime.now():
        await state.set_state(VaqtBlokStates.kutish_bekor)
        await message.answer("🔓 Blokni bekor qilish uchun 3 xonalik kodni yozing:")
        return

    await message.answer(
        "⏱️ Nechi soat? (faqat son, masalan: 3)\n"
        "Bekor qilish uchun /bekor yozing"
    )
    await state.set_state(VaqtBlokStates.kutish_soat)


@dp.message(VaqtBlokStates.kutish_soat)
async def vaqtblok_soat(message: Message, state: FSMContext):
    """Soatni qabul qilish"""
    if message.text.lower() == "/bekor":
        await state.clear()
        await message.answer("❌ Bekor qilindi")
        return

    try:
        soat = int(message.text.strip())
        if soat < 1 or soat > config.BLOK_MAX_HOURS:
            raise ValueError
    except ValueError:
        await message.answer(
            f"❌ 1 dan {config.BLOK_MAX_HOURS} gacha son yozing:"
        )
        return

    kod = str(random.randint(100, 999))
    blok_vaqt = datetime.now() + timedelta(hours=soat)

    chat_id = message.chat.id
    await db.update_blok(chat_id, blok_vaqt, kod, soat)
    await state.clear()

    await message.answer(
        f"🔒 Blok o'rnatildi: *{soat} soat*\n\n"
        f"🔑 Kod: `{kod}` (eslab qoling!)\n\n"
        f"Bekor qilish uchun yana /vaqtblok yozib kodni kiriting.",
        parse_mode="Markdown"
    )


@dp.message(VaqtBlokStates.kutish_bekor)
async def vaqtblok_bekor(message: Message, state: FSMContext):
    """Blokni bekor qilish"""
    chat_id = message.chat.id
    user = await db.get_user(chat_id)

    if message.text.strip() != user['blok_son']:
        await state.clear()
        await message.answer("❌ Noto'g'ri kod")
        return

    await db.clear_blok(chat_id)
    await state.clear()
    await message.answer("✅ Blok bekor qilindi!")


# ==================== /MAXFIYLIK ====================

@dp.message(Command("maxfiylik"))
async def maxfiylik_start(message: Message, state: FSMContext):
    """Yashirin buyruq: /maxfiylik"""
    chat_id = message.chat.id
    user = await db.get_user(chat_id)

    if not user:
        await message.answer("❗ Avval /start bosing")
        return

    if not user['parol_hash']:
        await message.answer(
            "❗ Avval /parol.XXXXX orqali parol qo'ying"
        )
        return

    await state.set_state(MaxfiylikStates.kutish_parol)
    await message.answer("🔐 Parolni yozing:")


@dp.message(MaxfiylikStates.kutish_parol)
async def maxfiylik_parol(message: Message, state: FSMContext):
    """Parolni tekshirish"""
    chat_id = message.chat.id
    user = await db.get_user(chat_id)

    if not tekshir_parol(message.text.strip(), user['parol_hash']):
        await state.clear()
        await message.answer("❌ Noto'g'ri parol")
        return

    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha", callback_data="maxfiylik_ha"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="maxfiylik_yoq")
    ]])

    await message.answer(
        f"🔒 {config.MAXFIYLIK_KUN} kun davomida maxfiy bo'lishni "
        f"xohlaysizmi?",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "maxfiylik_ha")
async def maxfiylik_ha(callback: CallbackQuery):
    """Maxfiylikni yoqish"""
    chat_id = callback.from_user.id
    await db.update_maxfiylik(chat_id, True)
    await callback.message.edit_text(
        f"✅ Maxfiylik yoqildi: {config.MAXFIYLIK_KUN} kun"
    )
    await callback.answer()


@dp.callback_query(F.data == "maxfiylik_yoq")
async def maxfiylik_yoq(callback: CallbackQuery):
    """Maxfiylikni o'chirish"""
    await callback.message.edit_text("❌ Bekor qilindi")
    await callback.answer()


# ==================== /ADMINPANEL ====================

@dp.message(Command("adminpanel"))
async def adminpanel(message: Message):
    """Admin panel (faqat admin uchun)"""
    if message.from_user.id != config.ADMIN_ID:
        return

    users = await db.get_all_users()
    total = len(users)
    bloklangan = sum(1 for u in users if u['blok_vaqt']
                     and u['blok_vaqt'] > datetime.now())
    maxfiy = sum(1 for u in users if u['maxfiylik'])

    matn = (
        f"👑 *ADMIN PANEL*\n\n"
        f"👥 Jami foydalanuvchilar: *{total}*\n"
        f"🔒 Bloklangan: *{bloklangan}*\n"
        f"🕵️ Maxfiy: *{maxfiy}*\n\n"
        f"📋 *Foydalanuvchilar ro'yxati:*\n"
    )

    for u in users[:20]:
        ism = f"{u['ism'] or ''} {u['familya'] or ''}".strip()
        matn += (
            f"\n👤 {ism}\n"
            f"   ID: `{u['chat_id']}`\n"
            f"   @{u['username'] or 'yoq'}\n"
            f"   📞 {u['telefon']}\n"
            f"   🔐 {'✅' if u['parol_hash'] else '❌'}\n"
        )

    if total > 20:
        matn += f"\n... va yana {total - 20} ta"

    await message.answer(matn, parse_mode="Markdown")


# ==================== MAIN ====================
# ⚠️ MUHIM: Bu qism faqat python bot.py bilan ishga tushganda chaqiriladi

async def main():
    """Faqat python bot.py bilan ishga tushganda"""
    await db.connect()
    print("🤖 Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
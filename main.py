import logging
import os
import re
from threading import Thread
from flask import Flask

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# PDF <-> WORD konvertatsiya uchun
from pdf2docx import Converter
from docx import Document

# Render & UptimeRobot uchun veb-server (Flask)
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is active and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ADMIN MA'LUMOTLARI
ADMIN_USERNAME = "@ttmg_2024"
ADMIN_ID = 6220470834

# Bot holatlari (States)
(
    SELECT_TYPE,
    GET_DETAILS,
    CONFIRM_PAYMENT,
    SET_CARD_HOLDER,
    SET_CARD_NUMBER,
    ADMIN_SEND_FILE,
    USER_REPLY_STATE,
    CONVERT_PDF_TO_WORD,
    CONVERT_WORD_TO_PDF,
) = range(9)

# Karta ma'lumotlari
CARD_DATA = {
    "number": "Biriktirilmagan",
    "holder": "Biriktirilmagan"
}

# Buyurtmalar ro'yxati
ORDERS_LIST = []

# --- KLIENT UCHUN PASTKI TUGMALAR (ASOSIY MENYU) ---
def get_user_reply_keyboard():
    keyboard = [
        [KeyboardButton("📚 Kurs ishi"), KeyboardButton("📝 Mustaqil ish")],
        [KeyboardButton("📑 Referat / Boshqa")],
        [KeyboardButton("📄 Word -> PDF"), KeyboardButton("📑 PDF -> Word")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- KLIENT UCHUN TO'LOV REKVIZITLARI MAVJUD PASTKI TUGMA ---
def get_user_payment_reply_keyboard():
    keyboard = [
        [KeyboardButton("💳 To'lov rekvizitlari")],
        [KeyboardButton("📚 Kurs ishi"), KeyboardButton("📝 Mustaqil ish")],
        [KeyboardButton("📑 Referat / Boshqa")],
        [KeyboardButton("📄 Word -> PDF"), KeyboardButton("📑 PDF -> Word")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- ADMIN UCHUN PASTKI TUGMALAR ---
def get_admin_reply_keyboard():
    keyboard = [
        [KeyboardButton("📦 Barcha buyurtmalar"), KeyboardButton("💳 Karta sozlamasi")],
        [KeyboardButton("ℹ️ Admin haqida")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- START (FOYDALANUVCHILAR VA ADMIN UCHUN) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id == ADMIN_ID or (user.username and user.username.lower() == "ttmg_2024"):
        await update.message.reply_text(
            "👑 **Xush kelibsiz, Admin!**\n\n"
            "Botni boshqarish va buyurtmalarni ko'rish uchun pastdagi menyu tugmalaridan foydalaning:",
            reply_markup=get_admin_reply_keyboard(),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 **Xush kelibsiz!**\n\n"
        "Men orqali kurs ishlari, mustaqil ishlar va boshqa topshiriqlarga buyurtma berishingiz hamda fayllaringizni PDF/Word formatlarga o'tkazishingiz mumkin.\n"
        "Boshlash uchun pastdagi tugmalardan birini tanlang:",
        reply_markup=get_user_reply_keyboard(),
        parse_mode="Markdown"
    )
    return SELECT_TYPE

# --- ADMIN BUYRUG'I (/admin) ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID and (not user.username or user.username.lower() != "ttmg_2024"):
        await update.message.reply_text("❌ Siz admin emassiz!")
        return

    await update.message.reply_text(
        "🛠 **Admin paneli:**",
        reply_markup=get_admin_reply_keyboard(),
        parse_mode="Markdown"
    )

# --- BUYURTMA TURI SECHILGANDA ---
async def type_selected_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    work_type = update.message.text.replace("📚 ", "").replace("📝 ", "").replace("📑 ", "")
    context.user_data["work_type"] = work_type
    
    back_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="go_back_to_menu")]
    ])
    
    await update.message.reply_text(
        f"✅ Tanlandi: **{work_type}**\n\n"
        "Iltimos, topshiriq haqida batafsil ma'lumot yuboring:\n"
        "• Fan nomi\n• Mavzu\n• Necha bet\n• Deadline",
        reply_markup=back_btn,
        parse_mode="Markdown"
    )
    return GET_DETAILS

# --- "ORQAGA" TUGMASI ISHLOVCHISI ---
async def go_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🔄 Bekor qilindi.")
    await query.message.reply_text(
        "Asosiy menyuga qaytdingiz. Qayta tanlang:",
        reply_markup=get_user_reply_keyboard()
    )
    return SELECT_TYPE

# --- MATN YUBORILGANDA ADMINGA XABAR VA PASTKI TUGMAGA TO'LOV REKVIZITLARI QO'SHILADI ---
async def get_details_and_show_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    details_text = update.message.text
    context.user_data["details"] = details_text

    await update.message.reply_text(
        "🎉 **Topshiriq ma'lumotlari qabul qilindi!**\n\n"
        "Admin tahlil qilib sizga narxni yuboradi to'lov rekvizitlari orqali to'lovni amalga oshirasiz.",
        reply_markup=get_user_payment_reply_keyboard(),
        parse_mode="Markdown"
    )

    admin_text = (
        f"📥 **YANGI TOPSHIRIQ MAVZUSI KELDI!**\n\n"
        f"👤 **Mijoz:** [{user.full_name}](tg://user?id={user.id})\n"
        f"🔗 **Username:** @{user.username if user.username else 'Yo\'q'}\n"
        f"🆔 **Mijoz ID:** `{user.id}`\n"
        f"📌 **Turi:** {context.user_data.get('work_type')}\n"
        f"📝 **Batafsil:** {details_text}\n\n"
        f"⚠️ *Mijozga narxni belgilab yuborishingiz kutilmoqda.*"
    )

    admin_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Javob berish / Narx yuborish", callback_data=f"reply_to_{user.id}")]
    ])

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=admin_btn,
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Adminga mavzu xabarini yuborishda xatolik: {e}")

    return CONFIRM_PAYMENT

# --- TO'LOV REKVIZITLARINI KO'RSATISH ---
async def show_payment_details_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💳 **To'lov rekvizitlari:**\n\n"
        f"Karta raqami: `{CARD_DATA['number']}`\n"
        f"Egalik qiluvchi: **{CARD_DATA['holder']}**\n\n"
        "To'lovni amalga oshirib, chekni (rasm yoki PDF fayl ko'rinishida) shu yerga yuboring."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    return CONFIRM_PAYMENT

# --- TO'LOV CHEKINI QABUL QILISH ---
async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    receipt_photo_id = None
    receipt_doc_id = None

    if update.message.photo:
        receipt_photo_id = update.message.photo[-1].file_id
    elif update.message.document:
        receipt_doc_id = update.message.document.file_id
    else:
        await update.message.reply_text("Iltimos, to'lov chekini rasm yoki PDF fayl ko'rinishida yuboring.")
        return CONFIRM_PAYMENT

    await update.message.reply_text(
        "✅ To'lov cheki qabul qilindi! Admin tez orada ko'rib chiqadi.",
        reply_markup=get_user_reply_keyboard()
    )

    ORDERS_LIST.append({
        "user": user.full_name,
        "username": user.username,
        "user_id": user.id,
        "work_type": context.user_data.get('work_type', 'Noma\'lum'),
        "details": context.user_data.get('details', 'Yo\'q')
    })

    admin_text = (
        f"📥 **YANGI BUYURTMA!**\n"
        f"🧾 **TO'LOV CHEKI KELDI**\n\n"
        f"👤 **Mijoz:** [{user.full_name}](tg://user?id={user.id})\n"
        f"🔗 **Username:** @{user.username if user.username else 'Yo\'q'}\n"
        f"🆔 **Mijoz ID:** `{user.id}`\n"
        f"📌 **Turi:** {context.user_data.get('work_type')}\n"
        f"📝 **Batafsil:** {context.user_data.get('details')}\n\n"
        f"💬 **Mijozga tayyor ishni yuborish uchun pastdagi tugmani bosing:**"
    )

    admin_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Javob berish / Fayl yuborish", callback_data=f"reply_to_{user.id}")]
    ])

    if receipt_photo_id:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=receipt_photo_id, caption=admin_text, reply_markup=admin_btn, parse_mode="Markdown")
    elif receipt_doc_id:
        await context.bot.send_document(chat_id=ADMIN_ID, document=receipt_doc_id, caption=admin_text, reply_markup=admin_btn, parse_mode="Markdown")

    return ConversationHandler.END

# --- KONVERTATSIYA TUGMALARI BO'LIMI ---
async def start_pdf_to_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="go_back_to_menu")]])
    await update.message.reply_text(
        "📑 **PDF -> Word rejimi:**\n\nIltimos, Word-ga o'tkazmoqchi bo'lgan **PDF** faylingizni yuboring:",
        reply_markup=back_btn,
        parse_mode="Markdown"
    )
    return CONVERT_PDF_TO_WORD

async def start_word_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="go_back_to_menu")]])
    await update.message.reply_text(
        "📄 **Word -> PDF rejimi:**\n\nIltimos, PDF-ga o'tkazmoqchi bo'lgan **Word (.docx)** faylingizni yuboring:",
        reply_markup=back_btn,
        parse_mode="Markdown"
    )
    return CONVERT_WORD_TO_PDF

# --- PDF -> WORD KONVERTATSIYASI ---
async def handle_pdf_to_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document or not update.message.document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("❌ Iltimos, faqat `.pdf` formatidagi fayl yuboring!")
        return CONVERT_PDF_TO_WORD

    msg = await update.message.reply_text("⏳ PDF fayl Word ga o'tkazilmoqda, kuting...")
    
    pdf_file = await update.message.document.get_file()
    pdf_path = f"temp_{update.effective_user.id}.pdf"
    docx_path = f"converted_{update.effective_user.id}.docx"
    
    await pdf_file.download_to_drive(pdf_path)

    try:
        cv = Converter(pdf_path)
        cv.convert(docx_path, start=0, end=None)
        cv.close()

        await update.message.reply_document(
            document=open(docx_path, 'rb'),
            filename=f"{update.message.document.file_name.rsplit('.', 1)[0]}.docx",
            caption="✅ **Faylingiz Word formatiga o'tkazildi!**",
            reply_markup=get_user_reply_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Faylni o'tkazishda xatolik yuz berdi: {e}")
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(docx_path):
            os.remove(docx_path)
        await msg.delete()

    return ConversationHandler.END

# --- WORD -> PDF KONVERTATSIYASI ---
async def handle_word_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc_name = update.message.document.file_name.lower() if update.message.document else ""
    if not update.message.document or not (doc_name.endswith('.docx') or doc_name.endswith('.doc')):
        await update.message.reply_text("❌ Iltimos, faqat `.docx` yoki `.doc` formatidagi Word fayl yuboring!")
        return CONVERT_WORD_TO_PDF

    msg = await update.message.reply_text("⏳ Word fayli PDF ga o'tkazilmoqda, kuting...")

    word_file = await update.message.document.get_file()
    docx_path = f"temp_{update.effective_user.id}.docx"
    pdf_path = f"converted_{update.effective_user.id}.pdf"

    await word_file.download_to_drive(docx_path)

    try:
        # Tizimda LibreOffice orqali konvertatsiya qilish
        exit_code = os.system(f"soffice --headless --convert-to pdf {docx_path} --outdir .")
        temp_converted_pdf = docx_path.replace('.docx', '.pdf').replace('.doc', '.pdf')
        
        if os.path.exists(temp_converted_pdf):
            os.rename(temp_converted_pdf, pdf_path)
            await update.message.reply_document(
                document=open(pdf_path, 'rb'),
                filename=f"{update.message.document.file_name.rsplit('.', 1)[0]}.pdf",
                caption="✅ **Faylingiz PDF formatiga o'tkazildi!**",
                reply_markup=get_user_reply_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Serverda LibreOffice topilmadi yoki konvertatsiya qilishda xatolik yuz berdi.")
    except Exception as e:
        await update.message.reply_text(f"❌ Faylni o'tkazishda xatolik yuz berdi: {e}")
    finally:
        if os.path.exists(docx_path):
            os.remove(docx_path)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        await msg.delete()

    return ConversationHandler.END

# --- ADMIN TUGMALARI ISHLOVCHILARI ---
async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID and (not user.username or user.username.lower() != "ttmg_2024"):
        return

    text = update.message.text

    if text == "📦 Barcha buyurtmalar":
        if not ORDERS_LIST:
            await update.message.reply_text("📦 **Barcha buyurtmalar:**\n\nHozircha hech qanday buyurtma mavjud emas.", parse_mode="Markdown")
        else:
            msg = f"📦 **Jami buyurtmalar soni:** {len(ORDERS_LIST)} ta\n\n"
            keyboard = []
            for idx, order in enumerate(ORDERS_LIST, 0):
                msg += (
                    f"**#{idx + 1} Buyurtma**\n"
                    f"👤 Mijoz: [{order['user']}](tg://user?id={order['user_id']})\n"
                    f"🔗 Username: @{order['username'] if order['username'] else 'Yo\'q'}\n"
                    f"🆔 ID: `{order['user_id']}`\n"
                    f"📌 Turi: {order['work_type']}\n"
                    f"📝 Batafsil: {order['details']}\n"
                    f"-------------------------------\n"
                )
                keyboard.append([
                    InlineKeyboardButton(f"📤 Fayl yuborish (#{idx + 1})", callback_data=f"reply_to_{order['user_id']}"),
                    InlineKeyboardButton(f"❌ O'chirish", callback_data=f"del_order_{idx}")
                ])
            keyboard.append([InlineKeyboardButton("🗑 Barchasini tozalash", callback_data="clear_all_orders")])
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif text == "💳 Karta sozlamasi":
        msg = (
            "💳 **Hozirgi karta ma'lumotlari:**\n\n"
            f"• Raqami: `{CARD_DATA['number']}`\n"
            f"• Egasining ismi: **{CARD_DATA['holder']}**\n\n"
            "Kartani o'zgartirish uchun pastdagi tugmani bosing:"
        )
        keyboard = [[InlineKeyboardButton("✏️ Kartani yangilash", callback_data="change_card_start")]]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif text == "ℹ️ Admin haqida":
        await update.message.reply_text(
            f"👑 **Admin:** {ADMIN_USERNAME}\n"
            f"🆔 **Admin ID:** `{ADMIN_ID}`\n\n"
            f"📊 **Jami buyurtmalar soni:** {len(ORDERS_LIST)} ta",
            parse_mode="Markdown"
        )

# --- INLINE CALLBACK HANDLER ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("del_order_"):
        idx = int(query.data.split("_")[2])
        if 0 <= idx < len(ORDERS_LIST):
            ORDERS_LIST.pop(idx)
            await query.answer("Buyurtma o'chirildi!", show_alert=True)
            await query.edit_message_text("✅ Buyurtma muvaffaqiyatli o'chirildi!")

    elif query.data == "clear_all_orders":
        ORDERS_LIST.clear()
        await query.answer("Barcha buyurtmalar tozalandi!", show_alert=True)
        await query.edit_message_text("📦 **Barcha buyurtmalar to'liq tozalandi!**")

    elif query.data == "change_card_start":
        await query.message.reply_text("📝 Karta egasining **Ism va Familiya**sini kiriting:")
        return SET_CARD_HOLDER

    elif query.data.startswith("reply_to_"):
        target_id = int(query.data.split("_")[2])
        context.user_data["target_user_id"] = target_id
        await query.message.reply_text(
            f"📤 **Mijozga (ID: `{target_id}`) fayl yoki javob yuborish rejimidasiz.**\n\n"
            f"Iltimos, klientga yetkazilishi kerak bo'lgan **fayl, PDF, Word, rasm yoki matn**ni yuboring:",
            parse_mode="Markdown"
        )
        return ADMIN_SEND_FILE

# --- ADMIN FAYL YUBORISHI ---
async def send_file_from_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user_id = context.user_data.get("target_user_id")
    if not target_user_id:
        await update.message.reply_text("❌ Xatolik: Mijoz aniqlanmadi!")
        return ConversationHandler.END

    client_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Adminga savol yuborish", callback_data="user_ask_admin")]
    ])

    try:
        await update.message.copy(chat_id=target_user_id, reply_markup=client_keyboard)
        await update.message.reply_text(f"✅ **Tayyor fayl/rasm mijozga (ID: `{target_user_id}`) muvaffaqiyatli yetkazildi!**", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Faylni yetkazishda xatolik: {e}")

    return ConversationHandler.END

# --- MIJOZ JAVOBI ---
async def user_ask_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📝 Adminga yubormoqchi bo'lgan xabaringiz yoki faylingizni kiriting:")
    return USER_REPLY_STATE

async def send_user_reply_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_btn = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Javob berish / Fayl yuborish", callback_data=f"reply_to_{user.id}")]])

    forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 **MIJOZDAN YANGI XABAR!**\n👤 **Mijoz:** [{user.full_name}](tg://user?id={user.id})\n🆔 **ID:** `{user.id}`",
        reply_markup=admin_btn,
        parse_mode="Markdown"
    )
    await update.message.reply_text("✅ Xabaringiz adminga yetkazildi!")
    return ConversationHandler.END

# --- KARTANI BOSQICHMA-BOSQICH YANGILASH ---
async def save_card_holder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_card_holder"] = update.message.text.strip()
    await update.message.reply_text("💳 Endi **Karta raqami**ni kiriting (masalan: `8600123456789012`):", parse_mode="Markdown")
    return SET_CARD_NUMBER

async def save_card_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    CARD_DATA["holder"] = context.user_data.get("new_card_holder", "Biriktirilmagan")
    CARD_DATA["number"] = update.message.text.strip()

    await update.message.reply_text(
        f"✅ **Karta muvaffaqiyatli yangilandi!**\n\n"
        f"• Egasi: **{CARD_DATA['holder']}**\n"
        f"• Raqami: `{CARD_DATA['number']}`",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Jarayon bekor qilindi.", reply_markup=get_user_reply_keyboard())
    return ConversationHandler.END
                    

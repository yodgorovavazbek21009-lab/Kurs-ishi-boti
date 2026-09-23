import logging
import os
from threading import Thread
from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

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

ADMIN_USERNAME = "@bukhara05"
ADMIN_ID = 6935366567

# Bot holatlari (States)
SELECT_TYPE, GET_DETAILS, GET_FILE, CONFIRM_PAYMENT, SET_CARD_STATE = range(5)

# Karta ma'lumotlari xotirada saqlanadi
CARD_DATA = {
    "number": "Biriktirilmagan",
    "holder": "Biriktirilmagan"
}

# --- ADMIN MENYUSI TUGMALARI ---
def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("💳 Kartani ko'rish / o'zgartirish", callback_data="admin_card_menu")],
        [InlineKeyboardButton("ℹ️ Admin haqida", callback_data="admin_info")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- FOYDALANUVCHILAR UCHUN START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Agar admin /start bossa, buyurtma berish emas, Admin paneli ochiladi
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "👑 **Xush kelibsiz, Admin!**\n\n"
            "Siz admin bo'lganingiz uchun buyurtma bera olmaysiz. Botni boshqarish uchun quyidagi admin panelidan foydalaning:",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Oddiy foydalanuvchilar uchun menyu
    keyboard = [
        [InlineKeyboardButton("📚 Kurs ishi", callback_data="type_Kurs ishi")],
        [InlineKeyboardButton("📝 Mustaqil ish", callback_data="type_Mustaqil ish")],
        [InlineKeyboardButton("📑 Referat / Boshqa", callback_data="type_Boshqa topshiriq")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Eski reply-tugmalarni tozalash
    remove_keyboard = ReplyKeyboardRemove()
    await update.message.reply_text("...", reply_markup=remove_keyboard)
    
    await update.message.reply_text(
        "👋 **Xush kelibsiz!**\n\n"
        "Men orqali kurs ishlari, mustaqil ishlar va boshqa topshiriqlarga buyurtma berishingiz mumkin.\n"
        "Boshlash uchun kerakli bo'limni tanlang:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return SELECT_TYPE

# --- ADMIN BUYRUG'I (/admin) ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return

    await update.message.reply_text(
        "🛠 **Admin paneli:**",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )

# --- ADMIN TUGMALARI ISHLOVCHISI ---
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("Sizga ruxsat berilmagan!", show_alert=True)
        return

    await query.answer()

    if query.data == "admin_card_menu":
        msg = (
            "💳 **Hozirgi karta ma'lumotlari:**\n\n"
            f"• Raqami: `{CARD_DATA['number']}`\n"
            f"• Egasining ismi: **{CARD_DATA['holder']}**\n\n"
            "Kartani o'zgartirish uchun pastdagi tugmani bosing:"
        )
        keyboard = [
            [InlineKeyboardButton("✏️ Kartani yangilash", callback_data="change_card_start")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "admin_info":
        await query.edit_message_text(
            f"👑 **Admin:** {ADMIN_USERNAME}\n"
            f"🆔 **Admin ID:** `{ADMIN_ID}`\n\n"
            "Bot faol ishlamoqda.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")]]),
            parse_mode="Markdown"
        )

    elif query.data == "admin_back":
        await query.edit_message_text(
            "🛠 **Admin paneli:**",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )

    elif query.data == "change_card_start":
        await query.edit_message_text(
            "📝 **Yangi karta ma'lumotlarini yuboring:**\n\n"
            "Format: `KARTA_RAQAM ISMI`\n"
            "Masalan: `8600123456789012 BAXODIR JUMAYEV`",
            parse_mode="Markdown"
        )
        return SET_CARD_STATE

# --- ADMIN KARTANI TUGMA ORQALI O'ZGARTIRISHI ---
async def save_new_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    text = update.message.text.strip().split(maxsplit=1)
    if len(text) < 2:
        await update.message.reply_text("❌ Noto'g me'morchilik! Iltimos, karta raqami va ismini birga yuboring.\nMasalan: `8600123456789012 BAXODIR JUMAYEV`", parse_mode="Markdown")
        return SET_CARD_STATE

    CARD_DATA["number"] = text[0]
    CARD_DATA["holder"] = text[1]

    await update.message.reply_text(
        f"✅ **Karta muvaffaqiyatli yangilandi!**\n\n"
        f"Raqami: `{CARD_DATA['number']}`\n"
        f"Egasi: **{CARD_DATA['holder']}**",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- BUYURTMA OLISH JARAYONI (FOYDALANUVCHILAR UCHUN) ---
async def type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    work_type = query.data.split("_")[1]
    context.user_data["work_type"] = work_type
    
    await query.edit_message_text(
        f"✅ Tanlandi: **{work_type}**\n\n"
        "Iltimos, topshiriq haqida batafsil ma'lumot yuboring:\n"
        "• Fan nomi\n• Mavzu\n• Necha bet\n• Deadline",
        parse_mode="Markdown"
    )
    return GET_DETAILS

async def get_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["details"] = update.message.text
    
    keyboard = [[InlineKeyboardButton("⏭ Faylsiz davom etish", callback_data="skip_file")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Mavzuga oid fayl bo'lsa yuboring yoki **'Faylsiz davom etish'** bosing:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return GET_FILE

async def get_file_and_show_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        if update.message.document:
            context.user_data["file_id"] = update.message.document.file_id
            context.user_data["file_type"] = "document"
        elif update.message.photo:
            context.user_data["file_id"] = update.message.photo[-1].file_id
            context.user_data["file_type"] = "photo"
    
    msg = (
        "💳 **To'lov rekvizitlari:**\n\n"
        f"Karta raqami: `{CARD_DATA['number']}`\n"
        f"Egalik qiluvchi: **{CARD_DATA['holder']}**\n\n"
        "To'lov chekini (rasm/skrinshot) shu yerga yuboring."
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    return CONFIRM_PAYMENT

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    receipt_photo_id = update.message.photo[-1].file_id if update.message.photo else None
    
    if not receipt_photo_id:
        await update.message.reply_text("Iltimos, to'lov chekini rasm ko'rinishida yuboring.")
        return CONFIRM_PAYMENT

    await update.message.reply_text("🎉 Buyurtma qabul qilindi\nAdmin siz bilan bogʻlanadi")

    admin_text = (
        f"📥 **YANGI BUYURTMA!**\n\n"
        f"👤 **Mijoz:** [{user.full_name}](tg://user?id={user.id})\n"
        f"🆔 **Mijoz ID:** `{user.id}`\n"
        f"📌 **Turi:** {context.user_data.get('work_type')}\n"
        f"📝 **Batafsil:** {context.user_data.get('details')}\n"
    )

    await context.bot.send_photo(chat_id=ADMIN_ID, photo=receipt_photo_id, caption=admin_text, parse_mode="Markdown")

    if "file_id" in context.user_data:
        ftype = context.user_data["file_type"]
        if ftype == "document":
            await context.bot.send_document(chat_id=ADMIN_ID, document=context.user_data["file_id"], caption="📎 Topshiriq fayli")
        elif ftype == "photo":
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=context.user_data["file_id"], caption="📎 Topshiriq rasmi")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Jarayon bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- XABARLAR VA JAVOB CATCHER ---
async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_ID:
        return

    forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"👆 Mijoz ID: `{user.id}`\nJavob berish uchun ushbu xabarga **Reply (Javob berish)** qiling.",
        parse_mode="Markdown",
        reply_to_message_id=forwarded_msg.message_id
    )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if update.message.reply_to_message:
        reply_msg = update.message.reply_to_message
        if reply_msg.forward_from:
            target_user_id = reply_msg.forward_from.id
            try:
                await update.message.copy(chat_id=target_user_id)
                await update.message.reply_text("✅ Javobingiz mijozga yetkazildi!")
            except Exception as e:
                await update.message.reply_text(f"❌ Xatolik: {e}")

def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        print("Xatolik: BOT_TOKEN topilmadi!")
        return

    # Flask serverni yurgizish
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Admin karta sozlashi uchun alohida conversation handler
    admin_card_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^change_card_start$")],
        states={
            SET_CARD_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID), save_new_card)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    # Mijozlar uchun conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_TYPE: [CallbackQueryHandler(type_selected, pattern="^type_")],
            GET_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_details)],
            GET_FILE: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, get_file_and_show_payment),
                CallbackQueryHandler(get_file_and_show_payment, pattern="^skip_file$")
            ],
            CONFIRM_PAYMENT: [MessageHandler(filters.PHOTO, receive_receipt)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(admin_card_handler)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_|change_card_)"))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.REPLY & filters.User(ADMIN_ID), handle_admin_reply))
    app.add_handler(MessageHandler(~filters.COMMAND & ~filters.User(ADMIN_ID), handle_user_messages))

    print("Bot muvaffaqiyatli ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

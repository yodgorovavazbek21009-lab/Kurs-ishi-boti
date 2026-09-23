import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# Logging (Serverda xatoliklarni ko'rish uchun)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

ADMIN_USERNAME = "@bukhara05"
ADMIN_ID = 6935366567

SELECT_TYPE, GET_DETAILS, GET_FILE, CONFIRM_PAYMENT, ADMIN_SEND_WORK = range(5)

CARD_DATA = {
    "number": "Biriktirilmagan",
    "holder": "Biriktirilmagan"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buyrug'i bosilganda ishlaydi"""
    keyboard = [
        [InlineKeyboardButton("📚 Kurs ishi", callback_data="type_Kurs ishi")],
        [InlineKeyboardButton("📝 Mustaqil ish", callback_data="type_Mustaqil ish")],
        [InlineKeyboardButton("📑 Referat / Boshqa", callback_data="type_Boshqa topshiriq")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 **Xush kelibsiz!**\n\n"
        "Men orqali kurs ishlari, mustaqil ishlar va boshqa topshiriqlarga buyurtma berishingiz mumkin.\n"
        "Boshlash uchun kerakli bo'limni tanlang:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return SELECT_TYPE

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

    await update.message.reply_text("🎉 **Buyurtmangiz qabul qilindi!** Admin siz bilan bog'lanadi.")

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
            await context.bot.send_document(chat_id=ADMIN_ID, document=context.user_data["file_id"], caption="📎 Fayl")
        elif ftype == "photo":
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=context.user_data["file_id"], caption="📎 Rasm")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Buyurtma bekor qilindi.")
    return ConversationHandler.END

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_ID:
        return

    forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"👆 Mijoz ID: `{user.id}`\nJavob berish uchun ushbu xabarga **Reply** qiling.",
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

async def set_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Format: `/setcard KARTA_RAQAM ISMI`", parse_mode="Markdown")
        return
    CARD_DATA["number"] = context.args[0]
    CARD_DATA["holder"] = " ".join(context.args[1:])
    await update.message.reply_text(f"✅ Karta yangilandi:\n`{CARD_DATA['number']}` - **{CARD_DATA['holder']}**", parse_mode="Markdown")

def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        print("XatoliK: BOT_TOKEN topilmadi!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

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

    app.add_handler(CommandHandler("setcard", set_card))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.REPLY & filters.User(ADMIN_ID), handle_admin_reply))
    app.add_handler(MessageHandler(~filters.COMMAND & ~filters.User(ADMIN_ID), handle_user_messages))

    print("Bot muvaffaqiyatli ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    

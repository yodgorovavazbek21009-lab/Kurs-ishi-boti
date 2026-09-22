import logging
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

# Admin Telegram usernamesi va ID o'zgaruvchisi
ADMIN_USERNAME = "@bukhara05"
# Eslatma: Adminning haqiqiy numeric ID sini bilganingizdan so'ng ushbu o'zgaruvchiga yozing (masalan: 123456789)
ADMIN_ID = None  

# Conversation bosqichlari
SELECT_TYPE, GET_DETAILS, GET_FILE, CONFIRM_PAYMENT, ADMIN_SEND_WORK = range(5)

# Karta ma'lumotlari
CARD_NUMBER = "8600123456789012"  # Bu yerga o'z karta raqamingizni yozing
CARD_HOLDER = "F.I.SH"             # Karta egasining ismi-sharifi

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buyrug'i berilganda bosh menyuni chiqarish"""
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
    """Topshiriq turi tanlanganda"""
    query = update.callback_query
    await query.answer()
    
    work_type = query.data.split("_")[1]
    context.user_data["work_type"] = work_type
    
    await query.edit_message_text(
        f"✅ Tanlandi: **{work_type}**\n\n"
        "Iltimos, topshiriq haqida batafsil ma'lumot yuboring:\n"
        "• Fan nomi\n"
        "• Mavzu\n"
        "• Necha bet bo'lishi kerak\n"
        "• Topshirish muddati (deadline)",
        parse_mode="Markdown"
    )
    return GET_DETAILS

async def get_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mijozdan topshiriq ma'lumotlarini qabul qilish"""
    context.user_data["details"] = update.message.text
    
    keyboard = [[InlineKeyboardButton("⏭ Faylsiz davom etish", callback_data="skip_file")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Mavzuga oid fayl, metodichka yoki qo'shimcha resurs bo'lsa yuboring (fayl yoki rasm formatida).\n"
        "Agar fayl bo'lmasa, **'Faylsiz davom etish'** tugmasini bosing:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return GET_FILE

async def get_file_and_show_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Faylni qabul qilish va to'lov rekvizitlarini ko'rsatish"""
    if update.message:
        if update.message.document:
            context.user_data["file_id"] = update.message.document.file_id
            context.user_data["file_type"] = "document"
        elif update.message.photo:
            context.user_data["file_id"] = update.message.photo[-1].file_id
            context.user_data["file_type"] = "photo"
    
    # To'lov ma'lumotlarini chiqarish (Karta raqami copy bo'ladigan formatda)
    msg = (
        "💳 **To'lov rekvizitlari:**\n\n"
        f"Karta raqami: `{CARD_NUMBER}` *(nusxa olish uchun ustiga bosing)*\n"
        f"Egalik qiluvchi: **{CARD_HOLDER}**\n\n"
        "To'lovni amalga oshirgach, **to'lov chekini (rasm yoki skrinshot)** shu yerga yuboring."
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    return CONFIRM_PAYMENT

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lov chekini qabul qilish va Adminga avtomatik yuborish"""
    user = update.effective_user
    receipt_photo_id = update.message.photo[-1].file_id if update.message.photo else None
    
    if not receipt_photo_id:
        await update.message.reply_text("Iltimos, to'lov chekini rasm ko'rinishida yuboring.")
        return CONFIRM_PAYMENT

    await update.message.reply_text(
        "🎉 **Buyurtmangiz qabul qilindi!**\n\n"
        "Admin to'lovni va ma'lumotlarni tekshirib, tez orada siz bilan bog'lanadi.\n"
        "Tayyor ish shu bot orqali yetkazib beriladi.",
        parse_mode="Markdown"
    )

    # Admin uchun xabar shakllantirish
    admin_text = (
        f"📥 **YANGI BUYURTMA!**\n\n"
        f"👤 **Mijoz:** [{user.full_name}](tg://user?id={user.id})\n"
        f"🆔 **Mijoz ID:** `{user.id}`\n"
        f"Username: @{user.username if user.username else 'Mavjud emas'}\n\n"
        f"📌 **Turi:** {context.user_data.get('work_type')}\n"
        f"📝 **Batafsil:** {context.user_data.get('details')}\n"
    )

    # Adminga yozish (agar ADMIN_ID kiritilgan bo'lsa)
    target_chat = ADMIN_ID if ADMIN_ID else ADMIN_USERNAME

    # 1. Chekni va matnni yuborish
    await context.bot.send_photo(
        chat_id=target_chat,
        photo=receipt_photo_id,
        caption=admin_text,
        parse_mode="Markdown"
    )

    # 2. Qo'shimcha topshiriq fayli bo'lsa, uni ham yuborish
    if "file_id" in context.user_data:
        ftype = context.user_data["file_type"]
        if ftype == "document":
            await context.bot.send_document(chat_id=target_chat, document=context.user_data["file_id"], caption="📎 Topshiriq fayli")
        elif ftype == "photo":
            await context.bot.send_photo(chat_id=target_chat, photo=context.user_data["file_id"], caption="📎 Topshiriq rasmi")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jarayonni bekor qilish"""
    await update.message.reply_text("Buyurtma berish bekor qilindi.")
    return ConversationHandler.END

# --- ADMIN BO'LIMI: Tayyor ishni mijozga yetkazish ---
async def send_work_to_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin buyrug'i: /send CLIENT_ID"""
    user_id = update.effective_user.id
    
    # Faqat admin ishlata olishi uchun (ADMIN_ID sozlanganda)
    if ADMIN_ID and user_id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ **Xatolik!** Mijoz ID si ko'rsatilmadi.\n\n"
            "**Foydalanish:** `/send CLIENT_ID` (masalan: `/send 123456789`)\n"
            "Keyin tayyor faylni yuborasiz.",
            parse_mode="Markdown"
        )
        return

    context.user_data["target_client_id"] = context.args[0]
    await update.message.reply_text(
        f"📤 ID: `{context.args[0]}` bo'lgan mijozga tayyor ishni yuboring (fayl, rasm yoki matn shaklida):",
        parse_mode="Markdown"
    )
    return ADMIN_SEND_WORK

async def forward_work_to_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin yuborgan fayl yoki xabarni mijozga yetkazish"""
    client_id = context.user_data.get("target_client_id")
    
    try:
        await context.bot.send_message(
            chat_id=client_id,
            text="✅ **Sizning buyurtmangiz tayyor bo'ldi!**\nQuyida tayyor topshiriqni yuklab olishingiz mumkin:"
        )
        await update.message.copy(chat_id=client_id)
        await update.message.reply_text("✅ Tayyor ish mijozga muvaffaqiyatli yetkazildi!")
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {e}")

    return ConversationHandler.END

def main():
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # BotFather'dan olingan token kiritiladi
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("send", send_work_to_client)
        ],
        states={
            SELECT_TYPE: [CallbackQueryHandler(type_selected, pattern="^type_")],
            GET_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_details)],
            GET_FILE: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, get_file_and_show_payment),
                CallbackQueryHandler(get_file_and_show_payment, pattern="^skip_file$")
            ],
            CONFIRM_PAYMENT: [MessageHandler(filters.PHOTO, receive_receipt)],
            ADMIN_SEND_WORK: [MessageHandler(filters.ALL & ~filters.COMMAND, forward_work_to_client)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()

import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот обновлён через GitHub Actions. Напиши что-нибудь — я повторю.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Повторяем текст
    if update.message and update.message.text:
        await update.message.reply_text(update.message.text)

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN отсутствует. Заполни его в файле .env")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    # Long polling — без вебхуков и домена
    app.run_polling()

if __name__ == "__main__":
    main()

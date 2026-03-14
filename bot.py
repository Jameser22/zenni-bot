import os
import random
import sqlite3
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))

HASHTAG = "#фондцитатзенни"

client = OpenAI(api_key=OPENAI_KEY)

db = sqlite3.connect("quotes.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS quotes(
id INTEGER PRIMARY KEY AUTOINCREMENT,
text TEXT
)
""")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Бот работает. chat_id: {chat_id}")

async def save_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    text = update.message.text

    if HASHTAG in text.lower():

        cursor.execute(
            "INSERT INTO quotes(text) VALUES(?)",
            (text,)
        )

        db.commit()

async def zenstory(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute("SELECT text FROM quotes")
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Нет цитат")
        return

    quote = random.choice(rows)[0]

    prompt = f"""
Напиши короткую историю с очень черным юмором.
Можно мат.

Основа цитаты:

{quote}
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )

    story = response.output_text

    await update.message.reply_text(
        f"📚 Фонд цитат\n\n{quote}\n\nИстория:\n{story}"
    )

def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("zenstory", zenstory))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_quote))

    app.run_polling()

if __name__ == "__main__":
    main()
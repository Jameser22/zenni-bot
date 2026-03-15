import os
import re
import html
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone, time
from typing import Optional

from openai import OpenAI
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini").strip()

DAILY_SUMMARY_HOUR = int(os.getenv("DAILY_SUMMARY_HOUR", "12"))
DAILY_SUMMARY_MINUTE = int(os.getenv("DAILY_SUMMARY_MINUTE", "0"))
MAX_MESSAGES_FOR_SUMMARY = int(os.getenv("MAX_MESSAGES_FOR_SUMMARY", "200"))

HASHTAG = "#фондцитатзенни"
DB_PATH = "quotes.db"

if not TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise RuntimeError("Нет OPENAI_API_KEY")
if not ALLOWED_CHAT_ID:
    raise RuntimeError("Нет ALLOWED_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(chat_id, message_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        message_id INTEGER,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(chat_id, message_id)
    )
    """)

    conn.commit()
    conn.close()


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def save_message(
    chat_id: int,
    message_id: int,
    user_id: Optional[int],
    username: Optional[str],
    full_name: Optional[str],
    text: str,
) -> bool:
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO messages (
                chat_id, message_id, user_id, username, full_name, text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                message_id,
                user_id,
                username,
                full_name,
                normalize_text(text),
                utc_now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def save_quote(chat_id: int, message_id: int, text: str) -> bool:
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO quotes (chat_id, message_id, text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, message_id, normalize_text(text), utc_now().isoformat()),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def count_quotes(chat_id: int) -> int:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM quotes WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return int(row["c"])


def get_random_quotes(chat_id: int, limit: int = 3) -> list[str]:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT text
        FROM quotes
        WHERE chat_id = ?
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (chat_id, limit),
    )
    rows = [r["text"] for r in cur.fetchall()]
    conn.close()
    return rows


def get_messages_since(chat_id: int, dt_from: datetime, limit: int) -> list[sqlite3.Row]:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT username, full_name, text, created_at
        FROM messages
        WHERE chat_id = ?
          AND created_at >= ?
        ORDER BY created_at ASC
        LIMIT ?
        """,
        (chat_id, dt_from.isoformat(), limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def format_messages_for_prompt(rows: list[sqlite3.Row]) -> str:
    lines = []
    for row in rows:
        author = row["full_name"] or row["username"] or "кто-то"
        text = row["text"]
        lines.append(f"{author}: {text}")
    return "\n".join(lines)


def build_day_prompt(messages_blob: str) -> str:
    return f"""
Ты анализируешь сообщения группового чата и пишешь краткие саркастические итоги дня.

Задача:
- сделать короткую, смешную, едкую сводку;
- стиль: сарказм, черный юмор, ирония, наблюдательность;
- можно немного разговорного мата;
- можно 2-5 смайликов;
- никаких списков из 20 пунктов;
- итог должен быть компактным и читабельным;
- выдели 3-5 главных наблюдений;
- в конце дай общий язвительный вывод.

Ограничения:
- без угроз;
- без призывов к насилию;
- без унижения людей по защищённым признакам;
- без сексуального насилия;
- не придумывай фактов, которых не видно в сообщениях.

Сообщения чата:
{messages_blob}
""".strip()


def build_roast_prompt(messages_blob: str) -> str:
    return f"""
Ты анализируешь сообщения группового чата и пишешь жёсткую, но короткую прожарку дня.

Стиль:
- сарказм;
- черный юмор;
- злая ирония;
- разговорный стиль;
- немного мата допустимо;
- 3-5 смайликов максимум;
- коротко, плотно, смешно.

Нужно:
- вытащить самые нелепые, странные и смешные паттерны дня;
- сделать ощущение, что чат сам себя закопал;
- финал — один добивающий вывод.

Ограничения:
- без призывов к насилию;
- без сексуального насилия;
- без унижения людей по защищённым признакам;
- не выдумывай события, которых нет в сообщениях.

Сообщения чата:
{messages_blob}
""".strip()


def build_story_prompt(quotes: list[str]) -> str:
    joined = "\n\n".join(f"{i+1}) {q}" for i, q in enumerate(quotes))
    return f"""
Напиши одну альтернативную историю на русском на основе трёх цитат.

Основа:
{joined}

Стиль:
- грязная барная атмосфера;
- черный юмор;
- сарказм;
- абсурд;
- мат допустим;
- 2-5 смайликов;
- цельный сюжет;
- финал короткий и добивающий.

Ограничения:
- без призывов к насилию;
- без сексуального насилия;
- без унижения по защищённым признакам.

Верни только историю.
""".strip()


def call_responses_api(prompt: str) -> str:
    response = client.responses.create(
        model=OPENAI_TEXT_MODEL,
        input=prompt,
    )
    text = (response.output_text or "").strip()
    return text or "Не смог ничего внятного родить."


def parse_period_arg(arg: Optional[str]) -> timedelta:
    if not arg:
        return timedelta(hours=24)

    arg = arg.strip().lower()
    match = re.fullmatch(r"(\d+)([hd])", arg)
    if not match:
        return timedelta(hours=24)

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)

    return timedelta(hours=24)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        f"Бот работает.\nchat_id: {update.effective_chat.id}"
    )


async def save_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    full_name = " ".join(
        part for part in [
            user.first_name if user else None,
            user.last_name if user else None,
        ] if part
    ) or None

    text = update.message.text.strip()

    save_message(
        chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
        user_id=user.id if user else None,
        username=user.username if user else None,
        full_name=full_name,
        text=text,
    )

    if HASHTAG in text.lower():
        created = save_quote(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
            text=text,
        )
        if created:
            await update.message.reply_text("📌 Цитата добавлена в фонд")


async def zenstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    quotes_total = count_quotes(update.effective_chat.id)
    await update.message.reply_text(f"Цитат в базе: {quotes_total}")


async def day_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    period = timedelta(hours=24)
    dt_from = utc_now() - period
    rows = get_messages_since(update.effective_chat.id, dt_from, MAX_MESSAGES_FOR_SUMMARY)

    if not rows:
        await update.message.reply_text("За последние сутки у меня пусто.")
        return

    messages_blob = format_messages_for_prompt(rows)
    text = await asyncio.to_thread(call_responses_api, build_day_prompt(messages_blob))

    await update.message.reply_text(f"📊 Итоги дня\n\n{text}")


async def roast_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    period = timedelta(hours=24)
    dt_from = utc_now() - period
    rows = get_messages_since(update.effective_chat.id, dt_from, MAX_MESSAGES_FOR_SUMMARY)

    if not rows:
        await update.message.reply_text("За последние сутки прожаривать особо некого.")
        return

    messages_blob = format_messages_for_prompt(rows)
    text = await asyncio.to_thread(call_responses_api, build_roast_prompt(messages_blob))

    await update.message.reply_text(f"🔥 Прожарка дня\n\n{text}")


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    arg = context.args[0] if context.args else None
    period = parse_period_arg(arg)
    dt_from = utc_now() - period
    rows = get_messages_since(update.effective_chat.id, dt_from, MAX_MESSAGES_FOR_SUMMARY)

    if not rows:
        await update.message.reply_text("За этот период у меня пусто.")
        return

    label = arg or "24h"
    messages_blob = format_messages_for_prompt(rows)
    text = await asyncio.to_thread(call_responses_api, build_day_prompt(messages_blob))

    await update.message.reply_text(f"📎 Сводка за {html.escape(label)}\n\n{text}")


async def zenstory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    quotes = get_random_quotes(update.effective_chat.id, 3)
    if len(quotes) < 3:
        await update.message.reply_text("Нужно минимум 3 цитаты в фонде.")
        return

    story = await asyncio.to_thread(call_responses_api, build_story_prompt(quotes))
    await update.message.reply_text(f"📚 Кулстори\n\n{story}")


async def daily_noon_summary(context: ContextTypes.DEFAULT_TYPE):
    rows = get_messages_since(
        ALLOWED_CHAT_ID,
        utc_now() - timedelta(hours=24),
        MAX_MESSAGES_FOR_SUMMARY,
    )

    if not rows:
        return

    messages_blob = format_messages_for_prompt(rows)
    text = await asyncio.to_thread(call_responses_api, build_day_prompt(messages_blob))

    await context.bot.send_message(
        chat_id=ALLOWED_CHAT_ID,
        text=f"📊 Полуденные итоги\n\n{text}",
    )


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("zenstats", zenstats))
    app.add_handler(CommandHandler("day", day_summary))
    app.add_handler(CommandHandler("roast", roast_summary))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("zenstory", zenstory))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_all_messages,
        )
    )

    if app.job_queue:
        app.job_queue.run_daily(
            daily_noon_summary,
            time=time(hour=DAILY_SUMMARY_HOUR, minute=DAILY_SUMMARY_MINUTE),
            name="daily_noon_summary",
        )

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
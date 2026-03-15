import os
import io
import re
import json
import base64
import random
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from openai import OpenAI
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))

OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini").strip()
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()
LAST_USED_WINDOW = int(os.getenv("LAST_USED_WINDOW", "10"))

TARGET_HASHTAG = "#фондцитатзенни"
DB_PATH = "quotes.db"
ARCHIVE_PATH = "quotes_archive.txt"

if not TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise RuntimeError("Нет OPENAI_API_KEY")
if not ALLOWED_CHAT_ID:
    raise RuntimeError("Нет ALLOWED_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        message_id INTEGER,
        author_id INTEGER,
        text TEXT NOT NULL,
        source_type TEXT NOT NULL DEFAULT 'telegram',
        created_at TEXT NOT NULL,
        UNIQUE(chat_id, message_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS quote_votes (
        quote_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        vote_value INTEGER NOT NULL,
        vote_label TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(quote_id, user_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS generated_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_id INTEGER NOT NULL,
        content_kind TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def trim_text(text: str, limit: int = 240) -> str:
    text = normalize_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def allowed_chat(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == ALLOWED_CHAT_ID)


def has_target_hashtag(text: str) -> bool:
    return TARGET_HASHTAG in text.lower()


def save_quote_to_db(
    chat_id: int,
    message_id: Optional[int],
    author_id: Optional[int],
    text: str,
    source_type: str = "telegram",
) -> tuple[int, bool]:
    normalized = normalize_text(text)

    conn = db()
    cur = conn.cursor()

    if message_id is not None:
        cur.execute(
            "SELECT id FROM quotes WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id),
        )
        existing = cur.fetchone()
        if existing:
            conn.close()
            return int(existing["id"]), False

    cur.execute(
        "SELECT id FROM quotes WHERE chat_id = ? AND text = ?",
        (chat_id, normalized),
    )
    existing_by_text = cur.fetchone()
    if existing_by_text:
        conn.close()
        return int(existing_by_text["id"]), False

    cur.execute(
        """
        INSERT INTO quotes (chat_id, message_id, author_id, text, source_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (chat_id, message_id, author_id, normalized, source_type, utc_now()),
    )
    quote_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(quote_id), True


def get_quote_by_id(quote_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_quote_by_message(chat_id: int, message_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM quotes WHERE chat_id = ? AND message_id = ?",
        (chat_id, message_id),
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_quotes_count() -> int:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM quotes WHERE chat_id = ?", (ALLOWED_CHAT_ID,))
    row = cur.fetchone()
    conn.close()
    return int(row["c"])


def get_recent_quote_ids(content_kind: str, limit: int) -> list[int]:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT quote_id
        FROM generated_history
        WHERE content_kind = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (content_kind, limit),
    )
    ids = [int(row["quote_id"]) for row in cur.fetchall()]
    conn.close()
    return ids


def mark_quote_used(quote_id: int, content_kind: str):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO generated_history (quote_id, content_kind, created_at)
        VALUES (?, ?, ?)
        """,
        (quote_id, content_kind, utc_now()),
    )
    conn.commit()
    conn.close()


def pick_random_quote(content_kind: str, preferred_quote_id: Optional[int] = None):
    if preferred_quote_id:
        row = get_quote_by_id(preferred_quote_id)
        if row:
            return row

    recent_ids = get_recent_quote_ids(content_kind=content_kind, limit=LAST_USED_WINDOW)

    conn = db()
    cur = conn.cursor()

    if recent_ids:
        placeholders = ",".join("?" * len(recent_ids))
        query = f"""
            SELECT *
            FROM quotes
            WHERE chat_id = ?
              AND id NOT IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT 1
        """
        params = [ALLOWED_CHAT_ID, *recent_ids]
        cur.execute(query, params)
        row = cur.fetchone()
        if row:
            conn.close()
            return row

    cur.execute(
        """
        SELECT *
        FROM quotes
        WHERE chat_id = ?
        ORDER BY RANDOM()
        LIMIT 1
        """,
        (ALLOWED_CHAT_ID,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_vote_summary(quote_id: int) -> dict:
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            COALESCE(SUM(vote_value), 0) AS total_score,
            COUNT(*) AS voters
        FROM quote_votes
        WHERE quote_id = ?
        """,
        (quote_id,),
    )
    totals = cur.fetchone()

    cur.execute(
        """
        SELECT vote_value, COUNT(*) AS c
        FROM quote_votes
        WHERE quote_id = ?
        GROUP BY vote_value
        """,
        (quote_id,),
    )
    rows = cur.fetchall()
    conn.close()

    counts = {
        1: 0,
        2: 0,
        3: 0,
        -2: 0,
    }

    for row in rows:
        counts[int(row["vote_value"])] = int(row["c"])

    return {
        "total_score": int(totals["total_score"]),
        "voters": int(totals["voters"]),
        "count_1": counts[1],
        "count_2": counts[2],
        "count_3": counts[3],
        "count_-2": counts[-2],
    }


def save_vote(quote_id: int, user_id: int, vote_value: int, vote_label: str):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO quote_votes (quote_id, user_id, vote_value, vote_label, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(quote_id, user_id)
        DO UPDATE SET
            vote_value = excluded.vote_value,
            vote_label = excluded.vote_label,
            updated_at = excluded.updated_at
        """,
        (quote_id, user_id, vote_value, vote_label, utc_now()),
    )
    conn.commit()
    conn.close()


def get_ranked_quotes(limit: int = 10, reverse_bad: bool = False):
    conn = db()
    cur = conn.cursor()

    order_clause = "ASC, voters DESC, q.id DESC" if reverse_bad else "DESC, voters DESC, q.id DESC"

    cur.execute(
        f"""
        SELECT
            q.id,
            q.text,
            COALESCE(SUM(v.vote_value), 0) AS total_score,
            COUNT(v.user_id) AS voters
        FROM quotes q
        LEFT JOIN quote_votes v ON v.quote_id = q.id
        WHERE q.chat_id = ?
        GROUP BY q.id
        ORDER BY total_score {order_clause}
        LIMIT ?
        """,
        (ALLOWED_CHAT_ID, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def build_vote_keyboard(quote_id: int) -> InlineKeyboardMarkup:
    s = get_vote_summary(quote_id)

    keyboard = [
        [
            InlineKeyboardButton(f"😂 Ор x{s['count_1']}", callback_data=f"vote|{quote_id}|1"),
            InlineKeyboardButton(f"💀 Умер x{s['count_2']}", callback_data=f"vote|{quote_id}|2"),
        ],
        [
            InlineKeyboardButton(f"👑 Легенда x{s['count_3']}", callback_data=f"vote|{quote_id}|3"),
            InlineKeyboardButton(f"💩 Хуйня x{s['count_-2']}", callback_data=f"vote|{quote_id}|-2"),
        ],
        [
            InlineKeyboardButton(
                f"🏆 {s['total_score']} очков · {s['voters']} голосов",
                callback_data=f"stats|{quote_id}"
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def story_prompt(quote_text: str) -> str:
    return f"""
Напиши на русском короткую мини-историю по цитате.

Стиль:
- очень черный юмор
- сарказм
- злая ирония
- матерный разговорный стиль допустим
- ощущение, будто это грязная кулстори из чата после 3 ночи
- цельный сюжет
- 700-1100 знаков
- можно использовать смайлики умеренно
- финал должен добивать
- верни только историю

Можно использовать персонажей как локальный лор:
- Господин Диего: маленький, религиозный, самоуверенный, с дикой барной энергетикой
- Хороший Марк: длинный, худой, задротистый, южный, нелепо похотливый
- Кэт: ухоженная, резкая, красивая, с ледяным взглядом
- Настёныш: техно-хаос, милая внешность, ощущение контролируемого кошмара
- Юрич: носатый бармен и апостол бессмысленной суеты

Важно:
- это должны быть гротескные, сатирические, вымышленные версии персонажей
- без призывов к насилию
- без сексуального насилия
- без унижения по защищённым признакам
- без порнографических сцен

Цитата:
{quote_text}
""".strip()


def legend_prompt(quote_text: str) -> str:
    return f"""
Напиши на русском абсурдную легенду по цитате, как будто это древний городской миф из фонда цитат.

Стиль:
- чернушный
- очень саркастичный
- высокий пафос, смешанный с помойкой и баром
- много образности
- можно мат
- можно эмодзи умеренно
- ощущение псевдо-священного писания для деградантов
- 900-1400 знаков
- финал как проклятие, мораль или пророчество
- верни только легенду

Можно использовать персонажей как местный пантеон:
- Господин Диего
- Хороший Марк
- Кэт
- Настёныш
- Юрич

Важно:
- держи это сатирой и абсурдом
- не делай реальных угроз
- не давай инструкций по вреду
- не унижай людей по защищённым признакам

Цитата:
{quote_text}
""".strip()


def meme_prompt(quote_text: str) -> str:
    return f"""
Create one finished satirical caricature illustration based on this Russian quote.

Quote:
{quote_text}

Style:
- grotesque caricature
- dark absurd humor
- messy bar / nightlife chaos
- exaggerated faces
- absurd social energy
- rich comic details
- expressive poses
- editorial satire feeling
- no text inside image
- no speech bubbles
- no watermark
- readable composition
""".strip()


def generate_story(quote_text: str) -> str:
    response = client.responses.create(
        model=OPENAI_TEXT_MODEL,
        input=story_prompt(quote_text),
    )
    text = (response.output_text or "").strip()
    return text or "Не смог придумать историю."


def generate_legend(quote_text: str) -> str:
    response = client.responses.create(
        model=OPENAI_TEXT_MODEL,
        input=legend_prompt(quote_text),
    )
    text = (response.output_text or "").strip()
    return text or "Не смог придумать легенду."


def generate_meme_image(quote_text: str) -> bytes:
    result = client.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=meme_prompt(quote_text),
        size="1024x1024",
        quality="medium",
        output_format="png",
    )
    image_b64 = result.data[0].b64_json
    return base64.b64decode(image_b64)


def split_archive_quotes(raw_text: str) -> list[str]:
    text = raw_text.replace("\r\n", "\n").strip()
    if not text:
        return []

    # Пытаемся делить по блокам с нумерацией: 1. ... 2. ...
    blocks = re.split(r"\n\s*\n(?=\d+\.\s)", text)
    if len(blocks) == 1:
        # запасной вариант — делить по тройным/двойным пустым строкам
        blocks = re.split(r"\n{2,}", text)

    cleaned = []
    for block in blocks:
        item = block.strip()
        if not item:
            continue
        cleaned.append(item)

    return cleaned


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    await update.message.reply_text(f"Бот работает. chat_id: {chat_id}")


async def save_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update):
        return
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not has_target_hashtag(text):
        return

    quote_id, created = save_quote_to_db(
        chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
        author_id=update.effective_user.id if update.effective_user else None,
        text=text,
        source_type="telegram",
    )

    if created:
        await update.message.reply_text(
            f"📌 Цитата сохранена в фонд. ID: {quote_id}",
            reply_markup=build_vote_keyboard(quote_id),
        )


async def addquote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update):
        return
    if not update.message:
        return

    source_message = update.message.reply_to_message
    if not source_message or not source_message.text:
        await update.message.reply_text("Ответь командой /addquote на сообщение с текстом.")
        return

    text = source_message.text.strip()
    if not has_target_hashtag(text):
        text = f"{text}\n{TARGET_HASHTAG}"

    quote_id, created = save_quote_to_db(
        chat_id=update.effective_chat.id,
        message_id=source_message.message_id,
        author_id=source_message.from_user.id if source_message.from_user else None,
        text=text,
        source_type="telegram",
    )

    if created:
        await update.message.reply_text(
            f"📌 Добавил в фонд. ID: {quote_id}",
            reply_markup=build_vote_keyboard(quote_id),
        )
    else:
        await update.message.reply_text(
            f"Эта цитата уже есть в фонде. ID: {quote_id}",
            reply_markup=build_vote_keyboard(quote_id),
        )


async def importquotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update) or not update.message:
        return

    if not os.path.exists(ARCHIVE_PATH):
        await update.message.reply_text("Файл quotes_archive.txt не найден.")
        return

    try:
        with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception as e:
        await update.message.reply_text(f"Не смог прочитать архив: {e}")
        return

    blocks = split_archive_quotes(raw_text)

    added = 0
    skipped = 0

    for block in blocks:
        text = block.strip()
        if not text:
            skipped += 1
            continue

        if not has_target_hashtag(text):
            skipped += 1
            continue

        _, created = save_quote_to_db(
            chat_id=ALLOWED_CHAT_ID,
            message_id=None,
            author_id=None,
            text=text,
            source_type="archive",
        )

        if created:
            added += 1
        else:
            skipped += 1

    await update.message.reply_text(
        f"📚 В фондецитат появилось {added} новых кулстори 😂"
    )


async def zenstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update) or not update.message:
        return
    await update.message.reply_text(f"Цитат в базе: {get_quotes_count()}")


async def topquotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update) or not update.message:
        return

    rows = get_ranked_quotes(limit=10, reverse_bad=False)
    if not rows:
        await update.message.reply_text("Пока нет оценённых цитат.")
        return

    lines = ["🏆 Топ цитат фонда\n"]
    for idx, row in enumerate(rows, start=1):
        lines.append(
            f"{idx}. #{row['id']} · {int(row['total_score'])} очк. · {int(row['voters'])} голос.\n"
            f"{trim_text(row['text'], 130)}\n"
        )

    await update.message.reply_text("\n".join(lines))


async def worstquotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update) or not update.message:
        return

    rows = get_ranked_quotes(limit=10, reverse_bad=True)
    if not rows:
        await update.message.reply_text("Пока нет оценённых цитат.")
        return

    lines = ["💩 Антитоп цитат фонда\n"]
    for idx, row in enumerate(rows, start=1):
        lines.append(
            f"{idx}. #{row['id']} · {int(row['total_score'])} очк. · {int(row['voters'])} голос.\n"
            f"{trim_text(row['text'], 130)}\n"
        )

    await update.message.reply_text("\n".join(lines))


async def zenstory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update) or not update.message:
        return

    preferred_quote_id = None
    if update.message.reply_to_message:
        q = get_quote_by_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        if q:
            preferred_quote_id = int(q["id"])

    quote = pick_random_quote("story", preferred_quote_id=preferred_quote_id)
    if not quote:
        await update.message.reply_text("Нет цитат.")
        return

    await update.message.reply_text("🪦 Достаю цитату из подвала...")

    story = generate_story(quote["text"])
    mark_quote_used(int(quote["id"]), "story")

    text = (
        f"📚 Фонд цитат Зенни\n"
        f"Источник: #{quote['id']}\n\n"
        f"{trim_text(quote['text'], 500)}\n\n"
        f"История:\n{story}"
    )

    if len(text) > 4000:
        text = text[:3990] + "…"

    await update.message.reply_text(
        text,
        reply_markup=build_vote_keyboard(int(quote["id"])),
    )


async def legend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update) or not update.message:
        return

    preferred_quote_id = None
    if update.message.reply_to_message:
        q = get_quote_by_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        if q:
            preferred_quote_id = int(q["id"])

    quote = pick_random_quote("legend", preferred_quote_id=preferred_quote_id)
    if not quote:
        await update.message.reply_text("Нет цитат.")
        return

    await update.message.reply_text("📜 Призываю древнюю кулстори...")

    legend_text = generate_legend(quote["text"])
    mark_quote_used(int(quote["id"]), "legend")

    text = (
        f"📜 Легенда фонда\n"
        f"Источник: #{quote['id']}\n\n"
        f"{trim_text(quote['text'], 500)}\n\n"
        f"{legend_text}"
    )

    if len(text) > 4000:
        text = text[:3990] + "…"

    await update.message.reply_text(
        text,
        reply_markup=build_vote_keyboard(int(quote["id"])),
    )


async def zenmeme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update) or not update.message:
        return

    preferred_quote_id = None
    if update.message.reply_to_message:
        q = get_quote_by_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        if q:
            preferred_quote_id = int(q["id"])

    quote = pick_random_quote("meme", preferred_quote_id=preferred_quote_id)
    if not quote:
        await update.message.reply_text("Нет цитат.")
        return

    await update.message.reply_text("🎨 Рисую карикатуру...")

    image_bytes = generate_meme_image(quote["text"])
    mark_quote_used(int(quote["id"]), "meme")

    bio = io.BytesIO(image_bytes)
    bio.name = f"zenmeme_{quote['id']}.png"

    caption = (
        f"🖼 Мем-карикатура по цитате #{quote['id']}\n\n"
        f"{trim_text(quote['text'], 700)}"
    )

    await update.message.reply_photo(
        photo=bio,
        caption=caption,
        reply_markup=build_vote_keyboard(int(quote["id"])),
    )


async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return

    parts = query.data.split("|")
    if len(parts) != 3:
        await query.answer()
        return

    _, quote_id_str, vote_value_str = parts
    quote_id = int(quote_id_str)
    vote_value = int(vote_value_str)

    labels = {
        1: "Ор",
        2: "Умер",
        3: "Легенда",
        -2: "Хуйня",
    }
    vote_label = labels.get(vote_value, "Голос")

    save_vote(
        quote_id=quote_id,
        user_id=query.from_user.id,
        vote_value=vote_value,
        vote_label=vote_label,
    )

    try:
        await query.message.edit_reply_markup(reply_markup=build_vote_keyboard(quote_id))
    except Exception:
        pass

    await query.answer(f"Твой голос: {vote_label}")


async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return

    _, quote_id_str = query.data.split("|")
    quote_id = int(quote_id_str)
    s = get_vote_summary(quote_id)

    await query.answer(
        f"Цитата #{quote_id}: {s['total_score']} очков, {s['voters']} голосов",
        show_alert=False
    )


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addquote", addquote))
    app.add_handler(CommandHandler("importquotes", importquotes))
    app.add_handler(CommandHandler("zenstats", zenstats))
    app.add_handler(CommandHandler("topquotes", topquotes))
    app.add_handler(CommandHandler("worstquotes", worstquotes))
    app.add_handler(CommandHandler("zenstory", zenstory))
    app.add_handler(CommandHandler("legend", legend))
    app.add_handler(CommandHandler("zenmeme", zenmeme))

    app.add_handler(CallbackQueryHandler(vote_callback, pattern=r"^vote\|"))
    app.add_handler(CallbackQueryHandler(stats_callback, pattern=r"^stats\|"))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_quote
        )
    )

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
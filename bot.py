import os
import re
import io
import html
import base64
import random
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone, time
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

HASHTAG = "#фондцитатзенни"
DB_PATH = "quotes.db"
ARCHIVE_PATH = "quotes_archive.txt"

DAILY_JOB_NAME = "daily_summary_job"
SHELUHA_JOB_NAME = "daily_sheluha_job"

QUOTE_REACTIONS = [
    "😂 мне в копилочку, а Золдена в дробилочку",
    "Шутки закончились? Или еще будут? 🤭",
    "О, ну это я забираю без шелухи 🌍",
    "Так... звучит как новая кулстори 🍷",
    "Это уже не сообщение, это диагноз чату 😌",
]

RAP_STYLES = [
    {
        "name": "Guf",
        "vibe": "уставший городской исповедальный рэп",
        "themes": ["двор", "дым", "бывшая", "телефон", "подъезд", "вина"],
        "tone": "усталый, бытовой, немного виноватый",
        "imagery": ["ночной район", "старый дом", "кухня", "пепельница", "молчание"],
    },
    {
        "name": "Pharaoh",
        "vibe": "мрачный гламурный психодел",
        "themes": ["ночь", "туман", "холод", "люкс", "пустота", "эго"],
        "tone": "отрешённый, мрачный, самовлюблённый",
        "imagery": ["неон", "дым", "черные очки", "лед", "медленный свет"],
    },
    {
        "name": "Boulevard Depo",
        "vibe": "ломаный модный сюр с бравадой",
        "themes": ["шмот", "ирония", "абсурд", "сцена", "сленг", "стиль"],
        "tone": "насмешливый, кривой, уверенный",
        "imagery": ["кроссовки", "подвал", "вспышка", "кривое зеркало", "тёмный клуб"],
    },
    {
        "name": "Скриптонит",
        "vibe": "хриплый уличный нуар",
        "themes": ["район", "деньги", "грязь", "дым", "жизнь", "братва"],
        "tone": "жёсткий, низкий, тяжёлый",
        "imagery": ["бетон", "серая ночь", "машина", "сырой воздух", "сигаретный дым"],
    },
    {
        "name": "Oxxxymiron",
        "vibe": "интеллектуальный напор и словесная истерика",
        "themes": ["эрудиция", "конфликт", "эго", "литература", "битва", "невроз"],
        "tone": "агрессивный, умный, нервный",
        "imagery": ["кафедра", "арена", "бумаги", "крики", "гул"],
    },
    {
        "name": "ATL",
        "vibe": "триповый постапокалиптический рэп",
        "themes": ["кислота", "сны", "ирония", "грязь", "галлюцинации", "конец света"],
        "tone": "туманный, язвительный, триповый",
        "imagery": ["радиация", "болото", "ржавчина", "синие огни", "сонный ад"],
    },
    {
        "name": "Хаски",
        "vibe": "грязная поэзия двора и истерики",
        "themes": ["бедность", "страх", "религия", "двор", "грязь", "голод"],
        "tone": "истеричный, образный, больной",
        "imagery": ["грязный снег", "панелька", "икона", "подвал", "голод"],
    },
    {
        "name": "Noize MC",
        "vibe": "сатирический речитатив с протестной подачей",
        "themes": ["общество", "лицемерие", "хаос", "система", "быт", "ирония"],
        "tone": "быстрый, колкий, сатирический",
        "imagery": ["митинг", "кухня", "толпа", "микрофон", "пыль"],
    },
    {
        "name": "Slimus",
        "vibe": "угрюмый московский быт",
        "themes": ["двор", "холод", "быт", "старость", "дым", "разочарование"],
        "tone": "приземлённый, мрачный, хмурый",
        "imagery": ["серый двор", "холодная кухня", "пустой парк", "асфальт", "сумка"],
    },
    {
        "name": "Баста",
        "vibe": "душевный уличный монолог",
        "themes": ["семья", "район", "жизнь", "ошибки", "любовь", "путь"],
        "tone": "тёплый, серьёзный, исповедальный",
        "imagery": ["двор детства", "поздний вечер", "лавка", "дорога", "окна"],
    },
    {
        "name": "Каста",
        "vibe": "умный бытовой рэп с социальной иронией",
        "themes": ["город", "люди", "быт", "нравы", "общество", "юмор"],
        "tone": "умный, спокойный, наблюдательный",
        "imagery": ["рынок", "улица", "троллейбус", "подъезд", "толпа"],
    },
    {
        "name": "LSP",
        "vibe": "сладкий декаданс и поп-тьма",
        "themes": ["вечеринка", "алкоголь", "одиночество", "драма", "гламур", "неон"],
        "tone": "томный, развратный, грустный",
        "imagery": ["бархат", "клуб", "бокал", "яркий свет", "пустой взгляд"],
    },
    {
        "name": "Miyagi",
        "vibe": "мягкий дымный мелодичный поток",
        "themes": ["мир", "путь", "дым", "свет", "дорога", "дух"],
        "tone": "спокойный, тёплый, мечтательный",
        "imagery": ["туман", "рассвет", "дорога", "облака", "океан воздуха"],
    },
    {
        "name": "Markul",
        "vibe": "мрачный кинематографичный внутренний монолог",
        "themes": ["город", "одиночество", "мечта", "прошлое", "дорога", "неуверенность"],
        "tone": "кинематографичный, напряжённый, грустный",
        "imagery": ["улица ночью", "дождь", "подземка", "эхо", "мокрый асфальт"],
    },
    {
        "name": "Big Baby Tape",
        "vibe": "игровой трэп с жвачкой и иронией",
        "themes": ["деньги", "угар", "флоу", "мемность", "статус", "суета"],
        "tone": "игривый, хвастливый, мультяшный",
        "imagery": ["пластик", "лед", "яркие цвета", "мультяшная роскошь", "хаос"],
    },
    {
        "name": "OG Buda",
        "vibe": "ленивый уверенный трэп-поток",
        "themes": ["деньги", "суета", "братва", "угар", "шмот", "лень"],
        "tone": "вальяжный, расслабленный, насмешливый",
        "imagery": ["диван", "дым", "лед", "лампа", "деньги"],
    },
    {
        "name": "Платина",
        "vibe": "отмороженный минималистичный трэп",
        "themes": ["холод", "отчуждение", "деньги", "стиль", "прострация", "флекс"],
        "tone": "вялый, ироничный, ледяной",
        "imagery": ["пустая комната", "лед", "капюшон", "серебро", "приглушенный свет"],
    },
    {
        "name": "Jeembo",
        "vibe": "истеричный техно-трэп",
        "themes": ["хаос", "шум", "ярость", "боль", "клуб", "вспышки"],
        "tone": "рваный, агрессивный, электрический",
        "imagery": ["стробоскоп", "красный шум", "техно-подвал", "крики", "пот"],
    },
    {
        "name": "Gone.Fludd",
        "vibe": "кислотный мультяшный угар",
        "themes": ["цвет", "бред", "игра", "хаос", "фантазия", "смех"],
        "tone": "шальной, детский, кислотный",
        "imagery": ["ядовитые цвета", "слизь", "игрушки", "космос", "смех"],
    },
    {
        "name": "Слава КПСС",
        "vibe": "ядовитая словесная клоунада",
        "themes": ["ирония", "баттл", "театр", "хаос", "мем", "кривой пафос"],
        "tone": "токсичный, смешной, злой",
        "imagery": ["цирк", "сцена", "грим", "кривой смех", "яркий свет"],
    },
]

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


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    defaults = {
        "day_hour": "12",
        "day_minute": "00",
        "day_mode": "summary",
        "day_length": "medium",
        "day_emoji": "on",
        "day_limit": "200",
        "sheluha_hour": "21",
        "sheluha_minute": "30",
        "sheluha_enabled": "off",
    }

    for key, value in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
            (key, value),
        )

    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO settings(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (key, value),
    )
    conn.commit()
    conn.close()


def allowed_chat(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == ALLOWED_CHAT_ID)


def has_target_hashtag(text: str) -> bool:
    return HASHTAG in text.lower()


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


def append_quote_to_archive(text: str):
    try:
        index = 1

        if os.path.exists(ARCHIVE_PATH):
            with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
                content = f.read()
                matches = re.findall(r"(?m)^\d+\.", content)
                index = len(matches) + 1

        with open(ARCHIVE_PATH, "a", encoding="utf-8") as f:
            prefix = "\n\n" if os.path.exists(ARCHIVE_PATH) and os.path.getsize(ARCHIVE_PATH) > 0 else ""
            f.write(f"{prefix}{index}. {text}\n")

    except Exception as e:
        print("Archive write error:", e)


def save_quote(chat_id: int, message_id: int, text: str) -> tuple[bool, Optional[int]]:
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
        quote_id = cur.lastrowid
        conn.commit()
        conn.close()

        append_quote_to_archive(text)
        return True, int(quote_id)

    except sqlite3.IntegrityError:
        cur.execute(
            "SELECT id FROM quotes WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id),
        )
        row = cur.fetchone()
        conn.close()
        return False, int(row["id"]) if row else None


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
        lines.append(f"{author}: {row['text']}")
    return "\n".join(lines)


def trim_text(text: str, limit: int = 600) -> str:
    text = normalize_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def split_archive_quotes(raw_text: str) -> list[str]:
    text = raw_text.replace("\r\n", "\n").strip()
    if not text:
        return []

    blocks = re.split(r"\n\s*\n(?=\d+\.\s)", text)
    if len(blocks) == 1:
        blocks = re.split(r"\n{2,}", text)

    return [b.strip() for b in blocks if b.strip()]


def build_summary_prompt(messages_blob: str, mode: str, length: str, emoji: str) -> str:
    length_rules = {
        "short": "5-8 коротких абзацев или 1 компактный блок до 900 знаков",
        "medium": "900-1400 знаков",
        "long": "1400-2200 знаков",
    }

    tone = "саркастические итоги дня" if mode == "summary" else "едкая, злая, смешная прожарка дня"
    emoji_rule = "Добавь 2-5 смайликов." if emoji == "on" else "Не используй смайлики."

    return f"""
Ты анализируешь сообщения группового чата и пишешь {tone}.

Требования:
- стиль: сарказм, черный юмор, ирония;
- можно немного разговорного мата;
- читабельно, смешно, компактно;
- выдели ключевые паттерны дня;
- не делай скучную хронику по минутам;
- длина: {length_rules.get(length, length_rules["medium"])};
- {emoji_rule}
- в конце дай общий язвительный вывод.

Ограничения:
- без угроз;
- без призывов к насилию;
- без сексуального насилия;
- без унижения людей по защищённым признакам;
- не придумывай фактов, которых нет в сообщениях.

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


def build_legend_prompt(quote_text: str) -> str:
    return f"""
Напиши абсурдную, саркастическую легенду по цитате.

Стиль:
- черный юмор;
- барный эпос;
- мрачная ирония;
- можно мат;
- немного смайликов;
- высокий пафос, но грязная атмосфера;
- 900-1400 знаков.

Ограничения:
- без призывов к насилию;
- без сексуального насилия;
- без унижения по защищённым признакам.

Цитата:
{quote_text}
""".strip()


def build_visual_synopsis_prompt(quote_text: str) -> str:
    return f"""
Turn this quote into a visual scene for an absurd satirical caricature.

Need:
- describe 1 strong central scene
- focus on poses, expressions, silhouettes
- highlight absurdity and dark humor
- keep composition simple and iconic
- suitable for enso / sumi-e ink illustration
- no text in image
- 4-6 short sentences

Quote:
{quote_text}
""".strip()


def build_enso_image_prompt(scene_description: str) -> str:
    return f"""
Create a grotesque satirical caricature in enso ink style.

Scene:
{scene_description}

Visual style:
- black ink only
- Japanese enso circle composition
- sumi-e brush painting
- rough expressive brush strokes
- parchment paper texture
- minimal details, strong silhouettes
- distorted caricature faces
- dark absurd humor
- mystical but ridiculous atmosphere
- hand-painted calligraphy energy
- asymmetrical composition
- no text
- no watermark
""".strip()


def pick_rap_style() -> dict:
    return random.choice(RAP_STYLES)


def build_sheluha_prompt(style: dict) -> str:
    return f"""
Напиши оригинальный короткий куплет в вайбе русского хип-хопа.

Артистический профиль:
Имя: {style['name']}
Вайб: {style['vibe']}
Темы: {", ".join(style['themes'])}
Тон: {style['tone']}
Образы: {", ".join(style['imagery'])}

Требования:
- 4-8 строк
- новый, оригинальный текст
- узнаваемый вайб, но без копирования реальных строк
- немного абсурда
- можно лёгкий мат
- обязательно вставь строку или финальную рифму:
"открой себя миру без шелухи!"
- сделай это смешно и чуть нелепо
- в конце отдельно подпиши:
"альтернативный {style['name']} feat. Совсем реальный Soulfate"

Верни только сам текст.
""".strip()


def build_sheluha_alt_prompt(style: dict, verse: str) -> str:
    return f"""
Сделай альтернативную, ещё более абсурдную и смешную версию этого короткого рэп-куплета.

Профиль:
{style['name']} — {style['vibe']}

Исходный текст:
{verse}

Требования:
- 4-8 строк
- усилить абсурд, юмор и кривой пафос
- можно легкий мат
- обязательно сохранить или заново вставить строку:
"открой себя миру без шелухи!"
- подпись в конце:
"альтернативный {style['name']} feat. Совсем реальный Soulfate"

Верни только текст.
""".strip()


def build_sheluha_visual_prompt(style: dict, verse: str) -> str:
    return f"""
Create a short visual synopsis for a funny enso caricature.

Artist vibe:
{style['name']} — {style['vibe']}

Lyrics:
{verse}

Need:
- 4-6 short sentences
- one iconic central character
- absurd rapper energy
- funny facial expression
- exaggerated pose
- suitable for enso / sumi-e style
- no text inside image
""".strip()


def call_text_model(prompt: str) -> str:
    response = client.responses.create(
        model=OPENAI_TEXT_MODEL,
        input=prompt,
    )
    return (response.output_text or "").strip() or "Не смог ничего внятного родить."


def generate_enso_image_from_text(source_text: str) -> bytes:
    scene_description = call_text_model(build_visual_synopsis_prompt(source_text))
    result = client.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=build_enso_image_prompt(scene_description),
        size="1024x1024",
    )
    image_base64 = result.data[0].b64_json
    return base64.b64decode(image_base64)


def generate_sheluha_enso_image(style: dict, verse: str) -> bytes:
    scene_description = call_text_model(build_sheluha_visual_prompt(style, verse))
    result = client.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=build_enso_image_prompt(scene_description),
        size="1024x1024",
    )
    image_base64 = result.data[0].b64_json
    return base64.b64decode(image_base64)


def parse_period_arg(arg: Optional[str]) -> timedelta:
    if not arg:
        return timedelta(hours=24)

    arg = arg.strip().lower()
    match = re.fullmatch(r"(\d+)([hd])", arg)
    if not match:
        return timedelta(hours=24)

    value = int(match.group(1))
    unit = match.group(2)
    return timedelta(hours=value) if unit == "h" else timedelta(days=value)


def get_day_config() -> dict:
    return {
        "hour": int(get_setting("day_hour", "12")),
        "minute": int(get_setting("day_minute", "00")),
        "mode": get_setting("day_mode", "summary"),
        "length": get_setting("day_length", "medium"),
        "emoji": get_setting("day_emoji", "on"),
        "limit": int(get_setting("day_limit", "200")),
    }


def get_sheluha_config() -> dict:
    return {
        "hour": int(get_setting("sheluha_hour", "21")),
        "minute": int(get_setting("sheluha_minute", "30")),
        "enabled": get_setting("sheluha_enabled", "off"),
    }


def meme_button(quote_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Карикатура без шелухи", callback_data=f"zenpic|{quote_id}")]
    ])


def sheluha_button(style_name: str, verse: str) -> InlineKeyboardMarkup:
    payload = f"sheluhaalt|{style_name}|{base64.urlsafe_b64encode(verse.encode('utf-8')).decode('utf-8')}"
    if len(payload) > 60:
        payload = f"sheluhaalt|{style_name}|short"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("А без шелухи? 😏", callback_data=payload)]
    ])


async def reschedule_daily_summary_job(app: Application):
    if not app.job_queue:
        return
    for job in app.job_queue.get_jobs_by_name(DAILY_JOB_NAME):
        job.schedule_removal()

    cfg = get_day_config()
    app.job_queue.run_daily(
        daily_noon_summary,
        time=time(hour=cfg["hour"], minute=cfg["minute"]),
        name=DAILY_JOB_NAME,
    )


async def reschedule_sheluha_job(app: Application):
    if not app.job_queue:
        return
    for job in app.job_queue.get_jobs_by_name(SHELUHA_JOB_NAME):
        job.schedule_removal()

    cfg = get_sheluha_config()
    app.job_queue.run_daily(
        daily_sheluha_post,
        time=time(hour=cfg["hour"], minute=cfg["minute"]),
        name=SHELUHA_JOB_NAME,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(f"Бот работает.\nchat_id: {update.effective_chat.id}")


async def save_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed_chat(update):
        return
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    full_name = " ".join(
        part for part in [user.first_name if user else None, user.last_name if user else None] if part
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

    if has_target_hashtag(text):
        created, quote_id = save_quote(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
            text=text,
        )

        if created and quote_id:
            await update.message.reply_text(
                random.choice(QUOTE_REACTIONS),
                reply_markup=meme_button(quote_id),
            )


async def zenstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.effective_chat and update.effective_chat.id == ALLOWED_CHAT_ID:
        await update.message.reply_text(f"Цитат в базе: {count_quotes(update.effective_chat.id)}")


async def daysettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    cfg = get_day_config()
    await update.message.reply_text(
        "⚙️ Настройки итогов дня\n\n"
        f"Время: {cfg['hour']:02d}:{cfg['minute']:02d}\n"
        f"Режим: {cfg['mode']}\n"
        f"Длина: {cfg['length']}\n"
        f"Смайлики: {cfg['emoji']}\n"
        f"Лимит сообщений: {cfg['limit']}"
    )


async def daytime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Используй: /daytime 12:00")
        return

    value = context.args[0].strip()
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        await update.message.reply_text("Формат времени: HH:MM")
        return

    hh, mm = map(int, value.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        await update.message.reply_text("Нормальное время введи 😌")
        return

    set_setting("day_hour", f"{hh:02d}")
    set_setting("day_minute", f"{mm:02d}")
    await reschedule_daily_summary_job(context.application)
    await update.message.reply_text(f"⏰ Итоги дня теперь будут в {hh:02d}:{mm:02d}")


async def daymode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Используй: /daymode summary или /daymode roast")
        return

    value = context.args[0].strip().lower()
    if value not in ["summary", "roast"]:
        await update.message.reply_text("Доступно: summary, roast")
        return

    set_setting("day_mode", value)
    await update.message.reply_text(f"🎭 Режим итогов дня: {value}")


async def daylength(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Используй: /daylength short|medium|long")
        return

    value = context.args[0].strip().lower()
    if value not in ["short", "medium", "long"]:
        await update.message.reply_text("Доступно: short, medium, long")
        return

    set_setting("day_length", value)
    await update.message.reply_text(f"📏 Длина итогов дня: {value}")


async def dayemoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Используй: /dayemoji on|off")
        return

    value = context.args[0].strip().lower()
    if value not in ["on", "off"]:
        await update.message.reply_text("Доступно: on, off")
        return

    set_setting("day_emoji", value)
    await update.message.reply_text(f"😶‍🌫️ Смайлики в итогах дня: {value}")


async def daylimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Используй: /daylimit 200")
        return

    value = context.args[0].strip()
    if not value.isdigit():
        await update.message.reply_text("Лимит должен быть числом")
        return

    num = int(value)
    if not 20 <= num <= 1000:
        await update.message.reply_text("Поставь лимит от 20 до 1000")
        return

    set_setting("day_limit", str(num))
    await update.message.reply_text(f"🧾 Лимит сообщений для анализа: {num}")


async def day_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    cfg = get_day_config()
    rows = get_messages_since(update.effective_chat.id, utc_now() - timedelta(hours=24), cfg["limit"])

    if not rows:
        await update.message.reply_text("За последние сутки у меня пусто.")
        return

    prompt = build_summary_prompt(format_messages_for_prompt(rows), cfg["mode"], cfg["length"], cfg["emoji"])
    text = await asyncio.to_thread(call_text_model, prompt)
    await update.message.reply_text(f"📊 Итоги дня\n\n{text}")


async def roast_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    cfg = get_day_config()
    rows = get_messages_since(update.effective_chat.id, utc_now() - timedelta(hours=24), cfg["limit"])

    if not rows:
        await update.message.reply_text("За последние сутки прожаривать особо некого.")
        return

    prompt = build_summary_prompt(format_messages_for_prompt(rows), "roast", cfg["length"], cfg["emoji"])
    text = await asyncio.to_thread(call_text_model, prompt)
    await update.message.reply_text(f"🔥 Прожарка дня\n\n{text}")


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    cfg = get_day_config()
    arg = context.args[0] if context.args else None
    period = parse_period_arg(arg)
    rows = get_messages_since(update.effective_chat.id, utc_now() - period, cfg["limit"])

    if not rows:
        await update.message.reply_text("За этот период у меня пусто.")
        return

    prompt = build_summary_prompt(format_messages_for_prompt(rows), cfg["mode"], cfg["length"], cfg["emoji"])
    text = await asyncio.to_thread(call_text_model, prompt)
    await update.message.reply_text(f"📎 Сводка за {html.escape(arg or '24h')}\n\n{text}")


async def zenstory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    quotes = get_random_quotes(update.effective_chat.id, 3)
    if len(quotes) < 3:
        await update.message.reply_text("Нужно минимум 3 цитаты в фонде.")
        return

    story = await asyncio.to_thread(call_text_model, build_story_prompt(quotes))
    await update.message.reply_text(f"📚 Кулстори\n\n{story}")


async def legend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    if update.message.reply_to_message:
        quote_row = get_quote_by_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        quote_text = quote_row["text"] if quote_row else update.message.reply_to_message.text
    else:
        quotes = get_random_quotes(update.effective_chat.id, 1)
        quote_text = quotes[0] if quotes else None

    if not quote_text:
        await update.message.reply_text("Нет цитат.")
        return

    result = await asyncio.to_thread(call_text_model, build_legend_prompt(quote_text))
    await update.message.reply_text(f"📜 Легенда фонда\n\n{result}")


async def zenpic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    if update.message.reply_to_message:
        quote_row = get_quote_by_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        quote_text = quote_row["text"] if quote_row else update.message.reply_to_message.text
    else:
        quotes = get_random_quotes(update.effective_chat.id, 1)
        quote_text = quotes[0] if quotes else None

    if not quote_text:
        await update.message.reply_text("Нет цитат.")
        return

    await update.message.reply_text("🎨 Собираю образ без шелухи...")
    image_bytes = await asyncio.to_thread(generate_enso_image_from_text, quote_text)

    bio = io.BytesIO(image_bytes)
    bio.name = "zenpic.png"

    await update.message.reply_photo(
        photo=bio,
        caption=f"🎨 Карикатура без шелухи\n\n{trim_text(quote_text, 700)}"
    )


async def zenpic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer("Ща будет карикатура 😌")

    parts = query.data.split("|")
    if len(parts) != 2:
        return

    quote_id = int(parts[1])
    quote = get_quote_by_id(quote_id)

    if not quote:
        await query.message.reply_text("Не нашёл цитату для карикатуры.")
        return

    await query.message.reply_text("🎨 Собираю образ без шелухи...")
    image_bytes = await asyncio.to_thread(generate_enso_image_from_text, quote["text"])

    bio = io.BytesIO(image_bytes)
    bio.name = f"quote_{quote_id}.png"

    await query.message.reply_photo(
        photo=bio,
        caption=f"🎨 Карикатура без шелухи\n\n{trim_text(quote['text'], 700)}"
    )


async def importquotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.id != ALLOWED_CHAT_ID:
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

    conn = db()
    cur = conn.cursor()

    for block in blocks:
        text = block.strip()
        if not text or not has_target_hashtag(text):
            continue

        cur.execute(
            "SELECT id FROM quotes WHERE chat_id = ? AND text = ?",
            (ALLOWED_CHAT_ID, normalize_text(text)),
        )
        exists = cur.fetchone()
        if exists:
            continue

        cur.execute(
            """
            INSERT INTO quotes (chat_id, message_id, text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (ALLOWED_CHAT_ID, None, normalize_text(text), utc_now().isoformat()),
        )
        added += 1

    conn.commit()
    conn.close()

    await update.message.reply_text(f"📚 В фондецитат появилось {added} новых кулстори 😂")


async def daily_noon_summary(context: ContextTypes.DEFAULT_TYPE):
    cfg = get_day_config()
    rows = get_messages_since(ALLOWED_CHAT_ID, utc_now() - timedelta(hours=24), cfg["limit"])
    if not rows:
        return

    prompt = build_summary_prompt(format_messages_for_prompt(rows), cfg["mode"], cfg["length"], cfg["emoji"])
    text = await asyncio.to_thread(call_text_model, prompt)

    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=f"📊 Итоги дня\n\n{text}")


async def sheluha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    style = pick_rap_style()
    verse = await asyncio.to_thread(call_text_model, build_sheluha_prompt(style))

    await update.message.reply_text(
        f"🎤 Шелуха дня\n\n{verse}",
        reply_markup=sheluha_button(style["name"], verse),
    )

    image_bytes = await asyncio.to_thread(generate_sheluha_enso_image, style, verse)
    bio = io.BytesIO(image_bytes)
    bio.name = "sheluha_enso.png"

    await update.message.reply_photo(
        photo=bio,
        caption=f"🖌 Энсо без шелухи\n\nальтернативный {style['name']} feat. Совсем реальный Soulfate"
    )


async def sheluha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer("Ща будет без шелухи 😏")

    parts = query.data.split("|", 2)
    if len(parts) < 3:
        return

    style_name = parts[1]
    style = next((s for s in RAP_STYLES if s["name"] == style_name), None)
    if not style:
        style = pick_rap_style()

    if parts[2] == "short":
        base_verse = await asyncio.to_thread(call_text_model, build_sheluha_prompt(style))
    else:
        try:
            base_verse = base64.urlsafe_b64decode(parts[2].encode("utf-8")).decode("utf-8")
        except Exception:
            base_verse = await asyncio.to_thread(call_text_model, build_sheluha_prompt(style))

    alt_verse = await asyncio.to_thread(call_text_model, build_sheluha_alt_prompt(style, base_verse))

    await query.message.reply_text(
        f"😏 А без шелухи?\n\n{alt_verse}"
    )

    image_bytes = await asyncio.to_thread(generate_sheluha_enso_image, style, alt_verse)
    bio = io.BytesIO(image_bytes)
    bio.name = "sheluha_alt_enso.png"

    await query.message.reply_photo(
        photo=bio,
        caption=f"🖌 Совсем без шелухи\n\nальтернативный {style['name']} feat. Совсем реальный Soulfate"
    )


async def sheluhasettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    cfg = get_sheluha_config()
    await update.message.reply_text(
        "🎤 Настройки шелухи\n\n"
        f"Время: {cfg['hour']:02d}:{cfg['minute']:02d}\n"
        f"Автопост: {cfg['enabled']}"
    )


async def timesheluha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Используй: /timesheluha 21:30")
        return

    value = context.args[0].strip()
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        await update.message.reply_text("Формат времени: HH:MM")
        return

    hh, mm = map(int, value.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        await update.message.reply_text("Нормальное время введи 😌")
        return

    set_setting("sheluha_hour", f"{hh:02d}")
    set_setting("sheluha_minute", f"{mm:02d}")
    await reschedule_sheluha_job(context.application)
    await update.message.reply_text(f"🕘 Шелуха теперь будет в {hh:02d}:{mm:02d}")


async def sheluhaon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("sheluha_enabled", "on")
    await update.message.reply_text("🎤 Автошелуха включена")
    await reschedule_sheluha_job(context.application)


async def sheluhaoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("sheluha_enabled", "off")
    await update.message.reply_text("🎤 Автошелуха выключена")


async def daily_sheluha_post(context: ContextTypes.DEFAULT_TYPE):
    cfg = get_sheluha_config()
    if cfg["enabled"] != "on":
        return

    style = pick_rap_style()
    verse = await asyncio.to_thread(call_text_model, build_sheluha_prompt(style))

    await context.bot.send_message(
        chat_id=ALLOWED_CHAT_ID,
        text=f"🎤 Шелуха дня\n\n{verse}",
        reply_markup=sheluha_button(style["name"], verse),
    )

    image_bytes = await asyncio.to_thread(generate_sheluha_enso_image, style, verse)
    bio = io.BytesIO(image_bytes)
    bio.name = "daily_sheluha_enso.png"

    await context.bot.send_photo(
        chat_id=ALLOWED_CHAT_ID,
        photo=bio,
        caption=f"🖌 Энсо без шелухи\n\nальтернативный {style['name']} feat. Совсем реальный Soulfate"
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
    app.add_handler(CommandHandler("legend", legend))
    app.add_handler(CommandHandler("zenpic", zenpic))
    app.add_handler(CommandHandler("importquotes", importquotes))

    app.add_handler(CommandHandler("daysettings", daysettings))
    app.add_handler(CommandHandler("daytime", daytime))
    app.add_handler(CommandHandler("daymode", daymode))
    app.add_handler(CommandHandler("daylength", daylength))
    app.add_handler(CommandHandler("dayemoji", dayemoji))
    app.add_handler(CommandHandler("daylimit", daylimit))

    app.add_handler(CommandHandler("sheluha", sheluha))
    app.add_handler(CommandHandler("timesheluha", timesheluha))
    app.add_handler(CommandHandler("sheluhasettings", sheluhasettings))
    app.add_handler(CommandHandler("sheluhaon", sheluhaon))
    app.add_handler(CommandHandler("sheluhaoff", sheluhaoff))

    app.add_handler(CallbackQueryHandler(zenpic_callback, pattern=r"^zenpic\|"))
    app.add_handler(CallbackQueryHandler(sheluha_callback, pattern=r"^sheluhaalt\|"))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_all_messages,
        )
    )

    if app.job_queue:
        app.job_queue.run_daily(
            daily_noon_summary,
            time=time(
                hour=int(get_setting("day_hour", "12")),
                minute=int(get_setting("day_minute", "00")),
            ),
            name=DAILY_JOB_NAME,
        )

        app.job_queue.run_daily(
            daily_sheluha_post,
            time=time(
                hour=int(get_setting("sheluha_hour", "21")),
                minute=int(get_setting("sheluha_minute", "30")),
            ),
            name=SHELUHA_JOB_NAME,
        )

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
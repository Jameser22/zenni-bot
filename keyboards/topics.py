from aiogram.utils.keyboard import InlineKeyboardBuilder
from data.topics import CATEGORIES

def topics_kb(category_id: str):
    builder = InlineKeyboardBuilder()

    topics = CATEGORIES.get(category_id, {}).get("topics", [])
    for title, topic_id in topics:
        builder.button(text=title, callback_data=f"topic:{topic_id}")

    builder.button(text="⬅️ Назад", callback_data="menu:topics")
    builder.button(text="🏠 В меню", callback_data="menu:home")
    builder.adjust(2, 2, 1)
    return builder.as_markup()
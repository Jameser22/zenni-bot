from aiogram.utils.keyboard import InlineKeyboardBuilder
from data.topics import CATEGORIES

def categories_kb():
    builder = InlineKeyboardBuilder()

    for category_id, category_data in CATEGORIES.items():
        builder.button(
            text=category_data["title"],
            callback_data=f"cat:{category_id}"
        )

    builder.button(text="🏠 В меню", callback_data="menu:home")
    builder.adjust(2, 2, 1)
    return builder.as_markup()
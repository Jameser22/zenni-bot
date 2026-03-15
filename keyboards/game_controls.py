from aiogram.utils.keyboard import InlineKeyboardBuilder

def game_controls_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Ответить", callback_data="game:answer")
    builder.button(text="💡 Подсказка", callback_data="game:hint")
    builder.button(text="📜 Вопросы", callback_data="game:questions")
    builder.button(text="🔄 Обновить", callback_data="game:refresh")
    builder.button(text="🏠 В меню", callback_data="menu:home")
    builder.adjust(2, 2, 1)
    return builder.as_markup()
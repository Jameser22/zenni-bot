from aiogram.utils.keyboard import InlineKeyboardBuilder

def intro_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Не тормози, Сникресни 🔥", callback_data="intro:continue")
    return builder.as_markup()

def main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎮 Начать игру", callback_data="menu:start")
    builder.button(text="🎯 Выбрать тему", callback_data="menu:topics")
    builder.button(text="🔥 Случайный кроссворд", callback_data="menu:random")
    builder.button(text="📜 Правила", callback_data="menu:rules")
    builder.adjust(2, 2)
    return builder.as_markup()
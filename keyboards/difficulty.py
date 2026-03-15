from aiogram.utils.keyboard import InlineKeyboardBuilder

def difficulty_kb(topic_id: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="🙂 Легко", callback_data=f"diff:{topic_id}:easy")
    builder.button(text="😎 Нормально", callback_data=f"diff:{topic_id}:medium")
    builder.button(text="💀 Жёстко", callback_data=f"diff:{topic_id}:hard")
    builder.button(text="⬅️ Назад к темам", callback_data="menu:topics")
    builder.adjust(2, 1, 1)
    return builder.as_markup()
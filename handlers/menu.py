import random
from aiogram import Router
from aiogram.types import CallbackQuery

from data.topics import CATEGORIES
from keyboards.main_menu import main_menu_kb
from keyboards.categories import categories_kb
from keyboards.topics import topics_kb
from keyboards.difficulty import difficulty_kb

router = Router()

@router.callback_query(lambda c: c.data == "intro:continue")
async def intro_continue(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏠 Главное меню\nВыбирай действие:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "menu:home")
async def menu_home(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏠 Главное меню\nВыбирай действие:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "menu:start")
async def menu_start(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎯 Выбери категорию темы:",
        reply_markup=categories_kb()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "menu:topics")
async def menu_topics(callback: CallbackQuery):
    await callback.message.edit_text(
        "📚 Категории кроссвордов:",
        reply_markup=categories_kb()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "menu:rules")
async def menu_rules(callback: CallbackQuery):
    text = (
        "📜 Правила:\n\n"
        "1. Выбираешь тему.\n"
        "2. Выбираешь сложность.\n"
        "3. Получаешь кроссворд.\n"
        "4. У тебя есть 3 подсказки.\n"
        "5. Вводишь ответы и открываешь слова.\n"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()

@router.callback_query(lambda c: c.data == "menu:random")
async def menu_random(callback: CallbackQuery):
    all_topics = []
    for category in CATEGORIES.values():
        all_topics.extend(category["topics"])

    _, topic_id = random.choice(all_topics)

    await callback.message.edit_text(
        f"🎲 Случайная тема выбрана: {topic_id}\n\nВыбирай сложность:",
        reply_markup=difficulty_kb(topic_id)
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("cat:"))
async def category_selected(callback: CallbackQuery):
    category_id = callback.data.split(":")[1]
    category_title = CATEGORIES.get(category_id, {}).get("title", "Категория")

    await callback.message.edit_text(
        f"{category_title}\nВыбери тему:",
        reply_markup=topics_kb(category_id)
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("topic:"))
async def topic_selected(callback: CallbackQuery):
    topic_id = callback.data.split(":")[1]

    await callback.message.edit_text(
        f"🧩 Тема выбрана: {topic_id}\n\nТеперь выбери сложность:",
        reply_markup=difficulty_kb(topic_id)
    )
    await callback.answer()
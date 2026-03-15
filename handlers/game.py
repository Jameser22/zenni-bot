from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from services.storage import user_games
from services.crossword_service import (
    create_mock_crossword,
    render_crossword_text,
    get_hint,
    check_numbered_answer,
)
from keyboards.game_controls import game_controls_kb

router = Router()

class GameStates(StatesGroup):
    waiting_for_answer = State()

@router.callback_query(lambda c: c.data.startswith("diff:"))
async def difficulty_selected(callback: CallbackQuery, state: FSMContext):
    _, topic_id, difficulty = callback.data.split(":")
    game = create_mock_crossword(topic_id, difficulty)
    user_games[callback.from_user.id] = game

    await state.clear()

    await callback.message.edit_text(
        render_crossword_text(game),
        reply_markup=game_controls_kb()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "game:hint")
async def game_hint(callback: CallbackQuery):
    game = user_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Нет активной игры.", show_alert=True)
        return

    hint = get_hint(game)

    await callback.message.edit_text(
        f"{render_crossword_text(game)}\n\n{hint}",
        reply_markup=game_controls_kb()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "game:questions")
async def game_questions(callback: CallbackQuery):
    game = user_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Нет активной игры.", show_alert=True)
        return

    await callback.message.edit_text(
        render_crossword_text(game),
        reply_markup=game_controls_kb()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "game:refresh")
async def game_refresh(callback: CallbackQuery):
    game = user_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Нет активной игры.", show_alert=True)
        return

    await callback.message.edit_text(
        render_crossword_text(game),
        reply_markup=game_controls_kb()
    )
    await callback.answer("Обновлено")

@router.callback_query(lambda c: c.data == "game:answer")
async def game_answer(callback: CallbackQuery, state: FSMContext):
    game = user_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Нет активной игры.", show_alert=True)
        return

    await state.set_state(GameStates.waiting_for_answer)
    await callback.message.answer(
        "✍️ Введи ответ в формате:\n\nномер слово\n\nПримеры:\n1 тест\n2 бот"
    )
    await callback.answer()

@router.message(GameStates.waiting_for_answer)
async def process_answer(message: Message, state: FSMContext):
    game = user_games.get(message.from_user.id)
    if not game:
        await message.answer("Нет активной игры.")
        await state.clear()
        return

    result = check_numbered_answer(game, message.text or "")

    await message.answer(
        f"{result}\n\n{render_crossword_text(game)}",
        reply_markup=game_controls_kb()
    )

    await state.clear()
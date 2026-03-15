from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from services.storage import user_games
from services.crossword_service import (
    create_mock_crossword,
    render_crossword_text,
    get_hint,
    check_numbered_answer,
    parse_numbered_answer,
    process_multiple_answers,
)
from keyboards.game_controls import game_controls_kb

router = Router()


class GameStates(StatesGroup):
    waiting_for_answer = State()


async def safe_edit_message(message, text, reply_markup):
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(lambda c: c.data.startswith("diff:"))
async def difficulty_selected(callback: CallbackQuery, state: FSMContext):
    _, topic_id, difficulty = callback.data.split(":")
    game = create_mock_crossword(topic_id, difficulty)
    user_games[callback.from_user.id] = game

    await state.clear()

    await safe_edit_message(
        callback.message,
        render_crossword_text(game),
        game_controls_kb()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "game:hint")
async def game_hint(callback: CallbackQuery):
    game = user_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Нет активной игры.", show_alert=True)
        return

    hint = get_hint(game)

    await safe_edit_message(
        callback.message,
        f"{render_crossword_text(game)}\n\n{hint}",
        game_controls_kb()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "game:questions")
async def game_questions(callback: CallbackQuery):
    game = user_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Нет активной игры.", show_alert=True)
        return

    await safe_edit_message(
        callback.message,
        render_crossword_text(game),
        game_controls_kb()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "game:refresh")
async def game_refresh(callback: CallbackQuery):
    game = user_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Нет активной игры.", show_alert=True)
        return

    await safe_edit_message(
        callback.message,
        render_crossword_text(game),
        game_controls_kb()
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
        "✍️ Введи ответ в формате:\n\nномер слово\n\nМожно сразу несколько строк:\n1 рокки\n2 терминатор"
    )
    await callback.answer()


@router.message(GameStates.waiting_for_answer)
async def process_answer_in_state(message: Message, state: FSMContext):
    game = user_games.get(message.from_user.id)
    if not game:
        await message.answer("Нет активной игры.")
        await state.clear()
        return

    results = process_multiple_answers(game, message.text or "")

    if not results:
        single_result = check_numbered_answer(game, message.text or "")
        results = [single_result]

    await message.answer(
        "\n".join(results) + "\n\n" + render_crossword_text(game),
        reply_markup=game_controls_kb()
    )

    await state.clear()


@router.message()
async def process_answer_without_button(message: Message, state: FSMContext):
    game = user_games.get(message.from_user.id)
    if not game:
        return

    text = (message.text or "").strip()
    if not text:
        return

    has_any_numbered_line = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if parse_numbered_answer(line):
            has_any_numbered_line = True
            break

    if not has_any_numbered_line:
        return

    results = process_multiple_answers(game, text)

    if not results:
        return

    await message.answer(
        "\n".join(results) + "\n\n" + render_crossword_text(game),
        reply_markup=game_controls_kb()
    )

    await state.clear()
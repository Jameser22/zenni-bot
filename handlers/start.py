from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from keyboards.main_menu import intro_kb

router = Router()

@router.message(Command("start"))
@router.message(Command("krossmeup"))
async def cmd_krossmeup(message: Message):
    await message.answer(
        "«Логика — это анатомия мышления.»\n— Джон Локк",
        reply_markup=intro_kb()
    )
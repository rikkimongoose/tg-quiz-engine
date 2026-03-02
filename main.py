import json
import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN в .env или переменных окружения")

bot = Bot(TOKEN)
dp = Dispatcher()

with open("tests.json", "r", encoding="utf-8") as f:
    DATA = json.load(f)["tests"]

users = {}  # user_id -> state


def get_test_by_id(test_id):
    for t in DATA:
        if t["id"] == test_id:
            return t
    return None


async def send_text_or_photo(message: types.Message, text: str, image_path: str | None = None, reply_markup=None):
    if image_path and os.path.exists(image_path):
        await message.answer_photo(
            photo=FSInputFile(image_path),
            caption=text,
            reply_markup=reply_markup
        )
    else:
        await message.answer(text, reply_markup=reply_markup)


@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardBuilder()
    for test in DATA:
        kb.button(text=test["title"], callback_data=f"test:{test['id']}")
    kb.adjust(1)
    await message.answer("Выбери тест:", reply_markup=kb.as_markup())


@dp.callback_query(lambda c: c.data.startswith("test:"))
async def choose_test(callback: types.CallbackQuery):
    test_id = callback.data.split(":", 1)[1]
    test = get_test_by_id(test_id)

    users[callback.from_user.id] = {
        "test_id": test_id,
        "q_index": 0,
        "scores": {}
    }

    kb = InlineKeyboardBuilder()
    kb.button(text="Начать тест ▶️", callback_data="start_test")
    kb.adjust(1)

    await send_text_or_photo(
        callback.message,
        f"{test['title']}\n\n{test['description']}",
        test.get("image"),
        kb.as_markup()
    )


@dp.callback_query(lambda c: c.data == "start_test")
async def start_test(callback: types.CallbackQuery):
    await send_question(callback.message, callback.from_user.id)


async def send_question(message: types.Message, user_id: int):
    state = users.get(user_id)
    if not state:
        await start(message)
        return

    test = get_test_by_id(state["test_id"])
    q = test["questions"][state["q_index"]]

    kb = InlineKeyboardBuilder()
    for i, ans in enumerate(q["answers"]):
        kb.button(text=ans["text"], callback_data=f"ans:{i}")
    kb.adjust(1)

    await send_text_or_photo(
        message,
        q["text"],
        q.get("image"),
        kb.as_markup()
    )


@dp.callback_query(lambda c: c.data.startswith("ans:"))
async def answer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    state = users.get(user_id)
    if not state:
        await start(callback.message)
        return

    test = get_test_by_id(state["test_id"])
    q = test["questions"][state["q_index"]]

    ans_index = int(callback.data.split(":", 1)[1])
    ans = q["answers"][ans_index]

    for key, value in ans.get("scores", {}).items():
        state["scores"][key] = state["scores"].get(key, 0) + value

    state["q_index"] += 1

    if state["q_index"] >= len(test["questions"]):
        await show_result(callback.message, user_id)
    else:
        await send_question(callback.message, user_id)


async def show_result(message: types.Message, user_id: int):
    state = users.get(user_id)
    if not state:
        await start(message)
        return

    test = get_test_by_id(state["test_id"])
    scores = state["scores"]

    best_key = None
    best_score = -1

    for res in test["results"]:
        score = scores.get(res["key"], 0)
        if score > best_score:
            best_score = score
            best_key = res["key"]

    result = next(r for r in test["results"] if r["key"] == best_key)

    kb = InlineKeyboardBuilder()
    kb.button(text="Пройти ещё раз 🔁", callback_data=f"test:{test['id']}")
    kb.button(text="В меню тестов 📋", callback_data="menu")
    kb.adjust(1)

    await send_text_or_photo(
        message,
        f"Результат:\n\n{result['text']}",
        result.get("image"),
        kb.as_markup()
    )


@dp.callback_query(lambda c: c.data == "menu")
async def back_to_menu(callback: types.CallbackQuery):
    await start(callback.message)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
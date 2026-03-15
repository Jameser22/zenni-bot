import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from data.topics import get_topic_title

BASE_DIR = Path(__file__).resolve().parent.parent
WORDS_DIR = BASE_DIR / "data" / "words"


def load_words(topic_id: str) -> List[Dict]:
    file_path = WORDS_DIR / f"{topic_id}.json"
    if not file_path.exists():
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    normalized = []
    for item in data:
        answer = str(item.get("answer", "")).strip().upper()
        question = str(item.get("question", "")).strip()

        if answer and question:
            normalized.append({
                "answer": answer,
                "question": question
            })

    return normalized


def create_mock_crossword(topic_id: str, difficulty: str) -> Dict:
    words = load_words(topic_id)

    if not words:
        words = [
            {"answer": "ТЕСТ", "question": f"Тестовый вопрос по теме {topic_id}"},
            {"answer": "БОТ", "question": f"Ещё один вопрос по теме {topic_id}"},
        ]

    amount_map = {
        "easy": 5,
        "medium": 6,
        "hard": 8,
    }
    amount = amount_map.get(difficulty, 5)

    selected = random.sample(words, min(amount, len(words)))

    questions = []
    for i, item in enumerate(selected, start=1):
        direction = "По горизонтали" if i % 2 else "По вертикали"
        questions.append({
            "number": i,
            "direction": direction,
            "question": item["question"],
            "answer": item["answer"],
        })

    return {
        "topic_id": topic_id,
        "topic_title": get_topic_title(topic_id),
        "difficulty": difficulty,
        "questions": questions,
        "hints_left": 3,
        "opened_answers": [],
        "used_hint_steps": {},
    }


def difficulty_title(difficulty: str) -> str:
    return {
        "easy": "Легко",
        "medium": "Нормально",
        "hard": "Жёстко",
    }.get(difficulty, difficulty)


def build_text_grid(game: Dict) -> str:
    """
    Упрощённая текстовая сетка:
    - каждое слово отдельной строкой
    - закрытые буквы показываются как □
    - открытые слова видны полностью
    """
    lines: List[str] = []
    lines.append("🧩 Сетка:")
    for item in game["questions"]:
        opened = item["answer"] in game["opened_answers"]
        if opened:
            word_view = " ".join(item["answer"])
            status = "✅"
        else:
            word_view = " ".join("□" for _ in item["answer"])
            status = "❓"

        arrow = "➡️" if item["direction"] == "По горизонтали" else "⬇️"
        lines.append(f"{status} {item['number']}{arrow} {word_view}")
    return "\n".join(lines)


def render_crossword_text(game: Dict) -> str:
    lines: List[str] = []
    lines.append("🧩 Кроссворд начат")
    lines.append("")
    lines.append(f"🎯 Тема: {game['topic_title']}")
    lines.append(f"⚔️ Сложность: {difficulty_title(game['difficulty'])}")
    lines.append(f"💡 Подсказок осталось: {game['hints_left']}")
    lines.append("")
    lines.append(build_text_grid(game))
    lines.append("")

    horizontals = [q for q in game["questions"] if q["direction"] == "По горизонтали"]
    verticals = [q for q in game["questions"] if q["direction"] == "По вертикали"]

    if horizontals:
        lines.append("По горизонтали:")
        for item in horizontals:
            status = "✅" if item["answer"] in game["opened_answers"] else "❓"
            lines.append(f"{status} {item['number']}. {item['question']}")
        lines.append("")

    if verticals:
        lines.append("По вертикали:")
        for item in verticals:
            status = "✅" if item["answer"] in game["opened_answers"] else "❓"
            lines.append(f"{status} {item['number']}. {item['question']}")
        lines.append("")

    lines.append("✍️ Вводи ответ так:")
    lines.append("номер слово")
    lines.append("")
    lines.append("Можно несколько строк сразу:")
    lines.append("1 рокки")
    lines.append("2 терминатор")

    return "\n".join(lines)


def find_question_by_number(game: Dict, number: int) -> Optional[Dict]:
    for item in game["questions"]:
        if item["number"] == number:
            return item
    return None


def parse_numbered_answer(text: str) -> Optional[Tuple[int, str]]:
    raw = (text or "").strip()
    if not raw:
        return None

    parts = raw.split(maxsplit=1)
    if len(parts) != 2:
        return None

    number_part, answer_part = parts

    if not number_part.isdigit():
        return None

    number = int(number_part)
    answer = answer_part.strip().upper()

    if not answer:
        return None

    return number, answer


def check_numbered_answer(game: Dict, user_text: str) -> str:
    parsed = parse_numbered_answer(user_text)
    if not parsed:
        return (
            "⚠️ Неправильный формат.\n\n"
            "Вводи так:\n"
            "номер слово\n\n"
            "Примеры:\n"
            "1 рокки\n"
            "2 терминатор"
        )

    number, user_answer = parsed
    question = find_question_by_number(game, number)

    if not question:
        return f"⚠️ В этом кроссворде нет вопроса №{number}."

    correct_answer = question["answer"]

    if correct_answer in game["opened_answers"]:
        return f"⚠️ Слово №{number} уже открыто."

    if user_answer != correct_answer:
        return f"❌ Неверно для №{number}. Попробуй ещё."

    game["opened_answers"].append(correct_answer)

    if len(game["opened_answers"]) == len(game["questions"]):
        return f"🎉 Верно! №{number} = {correct_answer}\n\n🏆 Кроссворд решён полностью!"

    return f"✅ Верно! №{number} = {correct_answer}"


def process_multiple_answers(game: Dict, text: str) -> List[str]:
    results: List[str] = []

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parsed = parse_numbered_answer(line)
        if not parsed:
            continue

        results.append(check_numbered_answer(game, line))

    return results


def get_hint(game: Dict) -> str:
    if game["hints_left"] <= 0:
        return "🚫 Подсказки закончились."

    unsolved = [q for q in game["questions"] if q["answer"] not in game["opened_answers"]]
    if not unsolved:
        return "🎉 Всё уже решено."

    target = unsolved[0]
    number = target["number"]
    answer = target["answer"]

    step = game["used_hint_steps"].get(number, 0) + 1
    game["used_hint_steps"][number] = step
    game["hints_left"] -= 1

    if step == 1:
        return f"💡 Подсказка для №{number}: слово начинается на «{answer[0]}»"
    if step == 2:
        return f"💡 Подсказка для №{number}: длина ответа — {len(answer)}"
    return f"💡 Подсказка для №{number}: ответ — {answer}"
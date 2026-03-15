from typing import Dict, List, Optional, Tuple
from data.topics import get_topic_title

def create_mock_crossword(topic_id: str, difficulty: str) -> Dict:
    questions = [
        {
            "number": 1,
            "direction": "По горизонтали",
            "question": f"Тестовый вопрос по теме {topic_id}",
            "answer": "ТЕСТ",
        },
        {
            "number": 2,
            "direction": "По вертикали",
            "question": f"Ещё один вопрос по теме {topic_id}",
            "answer": "БОТ",
        },
    ]

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

def render_crossword_text(game: Dict) -> str:
    lines: List[str] = []
    lines.append("🧩 Кроссворд начат")
    lines.append("")
    lines.append(f"🎯 Тема: {game['topic_title']}")
    lines.append(f"⚔️ Сложность: {difficulty_title(game['difficulty'])}")
    lines.append(f"💡 Подсказок осталось: {game['hints_left']}")
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
    lines.append("Примеры:")
    lines.append("1 тест")
    lines.append("2 бот")

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
            "1 тест\n"
            "2 бот"
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
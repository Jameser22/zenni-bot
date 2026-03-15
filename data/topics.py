CATEGORIES = {
    "classic": {
        "title": "📘 Классика",
        "topics": [
            ("📚 Литература", "literature"),
            ("🏛 История", "history"),
            ("🌍 География", "geography"),
            ("🎨 Искусство", "art"),
            ("👑 Мифология", "mythology"),
        ],
    },
    "fun": {
        "title": "🎉 Развлечения",
        "topics": [
            ("🎬 Фильмы", "movies"),
            ("📺 Сериалы", "series"),
            ("🎵 Музыка", "music"),
            ("🎮 Игры", "games"),
            ("😂 Мемы", "memes"),
        ],
    },
}


def get_topic_title(topic_id: str) -> str:
    for category in CATEGORIES.values():
        for title, current_topic_id in category["topics"]:
            if current_topic_id == topic_id:
                return title
    return topic_id
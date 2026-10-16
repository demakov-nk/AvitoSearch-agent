"""Загрузка AGENTS.md и скиллов из skills/*.md — для системного промпта.

AGENTS.md — память проекта: подкладывается один раз в начале сессии.
Скиллы — markdown-инструкции с frontmatter: модель читает их как процедуры.
Сейчас подкладываются все сразу при старте сессии.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def load_agents_md() -> str:
    """Текст AGENTS.md из корня проекта (пустая строка, если файла нет)."""
    path = PROJECT_ROOT / "AGENTS.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_skills() -> str:
    """Тексты всех skills/*.md, склеенные через пустую строку."""
    skills_dir = PROJECT_ROOT / "skills"
    if not skills_dir.is_dir():
        return ""
    texts = []
    for path in sorted(skills_dir.glob("*.md")):
        texts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(texts)

"""Один вызов модели через OpenAI-совместимый API (DeepSeek и аналоги).

Зависимостей нет: только стандартная библиотека.
Провайдера меняем в .env (BASE_URL, MODEL, API_KEY) — этот файл не трогаем.
"""

import json
import os
import urllib.request
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"


def load_env(path: str = ".env") -> None:
    """Читает KEY=VALUE из файла в переменные окружения (существующие не перезаписывает)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


@dataclass
class ToolCall:
    """Просьба модели вызвать инструмент: имя функции и её аргументы."""
    id: str
    name: str
    arguments: dict


@dataclass
class Answer:
    """Ответ модели: текст и/или вызовы инструментов (пустые, если их нет)."""
    text: str = ""
    tool_calls: list = field(default_factory=list)


def complete(messages: list, tools: list | None = None) -> Answer:
    """Один запрос к модели.

    messages — история в формате OpenAI: [{"role": "user"/"assistant"/"tool",
    "content": ...}] плюс {"role": "system", "content": ...}.
    tools — список JSON-схем инструментов; агент передаст их на каждом шаге.
    """
    api_key = os.environ.get("API_KEY")
    if not api_key or "вставь" in api_key:
        raise RuntimeError(
            "API_KEY не задан. Впиши ключ в файл .env:  API_KEY=sk-..."
        )

    base_url = os.environ.get("BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    body: dict = {
        "model": os.environ.get("MODEL", "deepseek-chat"),
        "messages": messages,
    }
    if tools:
        body["tools"] = tools

    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read())

    message = data["choices"][0]["message"]
    answer = Answer(text=message.get("content") or "")
    for call in message.get("tool_calls", []):
        function = call["function"]
        answer.tool_calls.append(
            ToolCall(
                id=call["id"],
                name=function["name"],
                arguments=json.loads(function["arguments"] or "{}"),
            )
        )
    return answer

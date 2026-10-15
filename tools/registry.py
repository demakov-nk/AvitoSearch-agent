"""Реестр инструментов: схемы для модели и вызов функций по имени."""

import json
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str          # имя с глагола (правило лекции)
    description: str   # что делает и откуда данные — модель читает ТОЛЬКО это
    schema: dict       # JSON-схема параметров — её видит модель
    func: Callable     # тело функции — модель его НЕ видит


class Registry:
    def __init__(self, tools: list[Tool]):
        self._by_name = {tool.name: tool for tool in tools}

    def schemas(self) -> list[dict]:
        """Описания инструментов для поля tools запроса — едут модели каждый шаг."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.schema,
                },
            }
            for tool in self._by_name.values()
        ]

    def run(self, name: str, arguments: dict) -> str:
        """Выполняет инструмент и возвращает результат строкой — для сообщения role=tool.

        Ошибки не роняют цикл: они доезжают до модели текстом, чтобы она
        не повторяла тот же вызов.
        """
        tool = self._by_name.get(name)
        if tool is None:
            return f"ОШИБКА: инструмента '{name}' нет. Доступно: {', '.join(self._by_name)}"
        try:
            result = tool.func(**arguments)
        except Exception as error:
            return f"ОШИБКА при вызове {name}: {error}"
        # dict/список сериализуем, а готовую строку (например, ответ MCP) отдаём как есть
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

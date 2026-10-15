"""Запуск агента: python3 main.py "вопрос".

Лог каждого шага печатается в консоль, финальный ответ — строкой ОТВЕТ: ...
"""

import sys
import urllib.error

from agent import Agent, StepLimit
from llm import load_env
from mcp_client import McpClient
from tools.basic import TOOLS
from tools.registry import Registry


def main() -> None:
    load_env()

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print("Вопрос не задан. Пример: python3 main.py 'сколько будет 2+2*2?'")
        sys.exit(1)

    # Свои инструменты + инструменты Авито из MCP-сервера — в одном реестре
    mcp = McpClient()
    try:
        mcp.start()
    except RuntimeError as error:
        print(f"Ошибка MCP: {error}")
        sys.exit(1)

    agent = Agent(Registry(TOOLS + mcp.tools()))
    try:
        answer = agent.run(question)
    except RuntimeError as error:
        print(f"Ошибка настройки: {error}")
        sys.exit(1)
    except urllib.error.HTTPError as error:
        print(f"Ошибка API ({error.code}): {error.reason}. Проверь ключ и модель в .env.")
        sys.exit(1)
    except StepLimit as error:
        print(f"{error}.")
        sys.exit(1)
    finally:
        mcp.close()

    print(f"ОТВЕТ: {answer}")


if __name__ == "__main__":
    main()

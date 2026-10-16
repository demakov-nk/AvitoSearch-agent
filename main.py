"""Чат с агентом: python3 main.py — диалог до /exit (или Ctrl+D).

Лог каждого шага пишется в logs/run-<дата>-<pid>.log (один файл на сессию);
в консоль выводится только нужная пользователю информация.
"""

import os
import sys
import time
import urllib.error
from pathlib import Path
from typing import TextIO

from agent import Agent, StepLimit
from llm import load_env
from mcp_client import McpClient
from tools.registry import Registry

LOG_DIR = Path(__file__).resolve().parent / "logs"


def open_log() -> tuple[TextIO, Path]:
    """Создаёт файл лога на сессию программы."""
    LOG_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    path = LOG_DIR / f"run-{stamp}-pid{os.getpid()}.log"
    return open(path, "w", encoding="utf-8"), path


def main() -> None:
    load_env()

    log_file, log_path = open_log()
    try:
        chat(log_file, log_path)
    finally:
        log_file.close()


def chat(log_file: TextIO, log_path: Path) -> None:
    log_file.write(f"ЗАПУСК {time.strftime('%Y-%m-%d %H:%M:%S')} | файл лога: {log_path}\n")

    mcp = McpClient()
    try:
        mcp.start()
    except RuntimeError as error:
        log_file.write(f"ИТОГ: ошибка MCP. {error}\n")
        print(f"Ошибка MCP: {error}")
        sys.exit(1)

    agent = Agent(Registry(mcp.tools()), log=log_file)
    print("Агент поиска одежды на Авито. Введите запрос (или /exit для выхода).")

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question == "/exit":
            break

        try:
            answer = agent.run(question)
        except RuntimeError as error:
            log_file.write(f"ИТОГ: ошибка. {error}\n")
            print(f"Ошибка: {error}")
            continue
        except urllib.error.HTTPError as error:
            log_file.write(f"ИТОГ: ошибка API ({error.code}). {error.reason}\n")
            print(f"Ошибка API ({error.code}): {error.reason}. Проверь ключ и модель в .env.")
            continue
        except StepLimit as error:
            log_file.write(f"ИТОГ: превышен лимит шагов. {error}\n")
            print("Не смог ответить: превышен лимит шагов. Подробности в логе.")
            continue

        print(answer)
        print()

    mcp.close()
    log_file.write(f"КОНЕЦ {time.strftime('%H:%M:%S')}\n")


if __name__ == "__main__":
    main()

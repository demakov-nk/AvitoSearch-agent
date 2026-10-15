"""Память агента на один прогон — обычный список сообщений.

Из лекции: «вся память агента на этом прогоне это обычный список».
Никаких файлов: живёт в памяти процесса, целиком уезжает модели на каждом шаге.
"""


class Memory:
    def __init__(self, system_prompt: str, user_query: str):
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

    def add_message(self, message: dict) -> None:
        self.messages.append(message)

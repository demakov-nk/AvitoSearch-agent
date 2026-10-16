"""Цикл агента: 14 строк логики из лекции + построчный лог каждого шага.

Формат лога — одна строка на событие (требование ЛР2 «лог построчно»):
    [ЧЧ:ММ:СС] ШАГ n | событие | детали
"""

import json
import sys
import time

from llm import complete
from memory import Memory
from skills import load_agents_md, load_skills
from tools.registry import Registry

MAX_STEPS = 10  # лимит шагов в коде — гарантия остановки (требование ЛР2)

SYSTEM_PROMPT = (
    "Ты — консольный агент. У тебя есть инструменты. "
    "Если для ответа нужен инструмент — вызови его, дождись результата и ответь. "
    "Не выдумывай данные, которых нет в результатах инструментов. Отвечай коротко."
)


class StepLimit(RuntimeError):
    """Агент не закончил за MAX_STEPS шагов — поднимаем как ошибку, а не молча."""


class Agent:
    def __init__(self, registry: Registry, max_steps: int = MAX_STEPS, log=sys.stdout):
        self.registry = registry
        self.max_steps = max_steps
        self.log = log
        self.memory: Memory | None = None
        self.system_prompt = self._build_system_prompt()

    @staticmethod
    def _build_system_prompt() -> str:
        """База + память проекта (AGENTS.md) + все скиллы — один раз на сессию."""
        parts = [SYSTEM_PROMPT]
        agents_md = load_agents_md()
        if agents_md:
            parts.append("Память проекта (AGENTS.md):\n" + agents_md)
        skills_text = load_skills()
        if skills_text:
            parts.append("Навыки (следуй им, когда задача им соответствует):\n" + skills_text)
        return "\n\n".join(parts)

    def run(self, user_query: str) -> str:
        # память живёт всю сессию: первый вопрос создаёт её, следующие дописываются
        if self.memory is None:
            self.memory = Memory(self.system_prompt, user_query)
        else:
            self.memory.add_message({"role": "user", "content": user_query})
        memory = self.memory
        self._log(0, f"задача: {user_query!r} | инструментов: {len(self.registry.schemas())}")

        for step in range(1, self.max_steps + 1):
            self._log(step, f"→ модель | сообщений в истории: {len(memory.messages)}")
            reply = complete(memory.messages, tools=self.registry.schemas())
            memory.add_message(reply.to_message())

            if not reply.tool_calls:
                self._log(step, "модель ответила без вызовов — конец цикла")
                return reply.text or "(пустой ответ)"

            for call in reply.tool_calls:
                args = json.dumps(call.arguments, ensure_ascii=False)
                self._log(step, f"вызов: {call.name}({args})")
                result = self.registry.run(call.name, call.arguments)
                self._log(step, f"результат: {result[:300]}")
                memory.add_message(
                    {"role": "tool", "tool_call_id": call.id, "content": result}
                )

        raise StepLimit(f"агент не сошёлся за {self.max_steps} шагов — смотри лог выше")

    def _log(self, step: int, event: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        print(f"[{stamp}] ШАГ {step:>2} | {event}", file=self.log, flush=True)

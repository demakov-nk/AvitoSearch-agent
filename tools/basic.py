"""Демо-инструменты, чтобы увидеть цикл агента вживую.

На этапе 2 плана их дополнят настоящие инструменты Авито (через MCP).
Имена — глаголы, описание — что делает и откуда данные (правила лекции).
"""

import ast
import datetime
import operator

from tools.registry import Tool

_ALLOWED = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval(node: ast.AST) -> float:
    """Безопасный подсчёт выражения: только числа и разрешённые операции."""
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.BinOp):
        return _ALLOWED[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _ALLOWED[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    raise ValueError(f"не поддерживается: {ast.dump(node)[:60]}")


def get_current_time() -> dict:
    """Возвращает текущие дату, время и день недели. Данные сервера, точны на момент вызова."""
    now = datetime.datetime.now()
    return {
        "datetime": now.isoformat(timespec="seconds"),
        "weekday": now.strftime("%A"),
    }


def calculate(expression: str) -> dict:
    """Считает арифметическое выражение с числами: + - * / // % ** и скобки. Пример: '2+2*2'."""
    try:
        result = _eval(ast.parse(expression, mode="eval"))
    except Exception as error:
        return {"expression": expression, "error": str(error)}
    return {"expression": expression, "result": result}


TOOLS = [
    Tool(
        name="get_current_time",
        description="Возвращает текущие дату и время. Вызывать, когда вопрос про дату, время или день недели.",
        schema={"type": "object", "properties": {}, "required": []},
        func=get_current_time,
    ),
    Tool(
        name="calculate",
        description="Считает арифметическое выражение с числами. Вызывать для любых вычислений вместо счёта в уме.",
        schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Арифметическое выражение, например '2+2*2'",
                },
            },
            "required": ["expression"],
        },
        func=calculate,
    ),
]

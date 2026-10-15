import sys
import urllib.error

from llm import complete, load_env


def main() -> None:
    load_env()

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print("Вопрос не задан. Пример: python3 main.py 'привет, что ты умеешь?'")
        sys.exit(1)

    try:
        answer = complete([
            {"role": "system", "content": "Ты консольный помощник. Отвечай коротко."},
            {"role": "user", "content": question},
        ])
    except RuntimeError as error:
        print(f"Ошибка настройки: {error}")
        sys.exit(1)
    except urllib.error.HTTPError as error:
        print(f"Ошибка API ({error.code}): {error.reason}. Проверь ключ и модель в .env.")
        sys.exit(1)

    print(answer.text or "(модель вернула пустой ответ)")


if __name__ == "__main__":
    main()

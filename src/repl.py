"""Интерактивные команды модели и RPC-клиента."""

import argparse
import shlex

from . import model

HOST = "127.0.0.1"
PORT = 8765
HELP = """Команды:
  create_individual created ip locale
  delete_individual identifier
  get_individuals
  update_individual identifier created ip locale
  create_query created argument individual handled
  delete_query identifier
  get_queries
  update_query identifier created argument individual handled
  create_completion created output status error query cache_hit
  delete_completion identifier
  get_completions
  update_completion identifier created output status error query cache_hit
  select_recent_completions [moment]
  help, exit
Число в кавычках: строка; без кавычек: int. null означает None."""

NAMES = tuple(line.strip().split()[0] for line in HELP.splitlines()[1:-2])
QUOTES = ("'", '"')
QUOTED_LENGTH = 2


def convert(token):
    """Преобразует токен REPL в значение поля."""
    if len(token) >= QUOTED_LENGTH and token[0] in QUOTES:
        return token[1:-1]
    if token == "null":
        return None
    try:
        return int(token)
    except ValueError:
        return token


def evaluate(target, line):
    """Выполняет команду, возвращая результат либо описание ошибки."""
    try:
        parts = shlex.split(line, posix=False)
    except ValueError as error:
        return f"не разобрал строку: {error}"
    if not parts or parts[0] == "help":
        return HELP if parts else ""
    if parts[0] not in NAMES:
        return f"нет такой команды: {parts[0]}"
    try:
        return repr(getattr(target, parts[0])(
            *[convert(token) for token in parts[1:]]))
    except (model.ModelError, ValueError, OSError) as error:
        return f"{type(error).__name__}: {error}"
    except TypeError as error:
        return f"не тот набор аргументов: {error}"


def loop(target):
    """Читает команды до exit или конца ввода."""
    print(HELP)
    while True:
        try:
            line = input(">>> ")
        except (EOFError, KeyboardInterrupt):
            return
        if line.strip() == "exit":
            return
        answer = evaluate(target, line)
        if answer:
            print(answer)


def main():
    """Запускает REPL модели или удалённого клиента."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", action="store_true")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    options = parser.parse_args()
    if not options.rpc:
        loop(model)
        return
    from .client import Client
    with Client(options.host, options.port) as client:
        loop(client)


if __name__ == "__main__":
    main()

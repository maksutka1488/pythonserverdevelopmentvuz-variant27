"""Провести демонстрацию HTTP API и сохранить готовый PNG."""

import argparse
import tomllib
from pathlib import Path
from time import monotonic, sleep, time

from .client import ApiClient

EXAMPLE = "400638133393"
POLL_SECONDS = 0.2
WAIT_SECONDS = 35


def wait_for_result(client, identifier):
    """Подождать результат до истечения разумного срока демонстрации."""
    expires = monotonic() + WAIT_SECONDS
    while monotonic() < expires:
        rows = client.list_completion(identifier)
        if rows:
            return rows[0]
        sleep(POLL_SECONDS)
    raise TimeoutError("Результат не появился вовремя")


def main():
    """Прогнать создание, опрос, скачивание и построение отчёта."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("data/demo.png"))
    parser.add_argument("--identifier", type=int, default=1)
    args = parser.parse_args()
    with Path(args.config).open("rb") as stream:
        auth = tomllib.load(stream)["auth"]
    client = ApiClient(args.url, **auth)
    now, key = int(time()), args.identifier
    print("Пользователь:", client.submit_individual(
        key, now, "127.0.0.1", "ru-RU",
    ))
    print("Задание:", client.submit_query(key, now, EXAMPLE, key))
    result = wait_for_result(client, key)
    print("Результат:", result)
    if not result["output"]:
        parser.exit(1, "PNG недоступен: проверьте статус и test_mode.\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(client.download_completion(result["identifier"]))
    print("PNG:", args.output)
    print("Отчёт:", client.list_report())


if __name__ == "__main__":
    main()

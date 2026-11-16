"""Запуск HTTP-сервера Flask для локальной демонстрации."""

import argparse

from .app import create_app


def main():
    """Прочитать параметры запуска и закрыть очередь при остановке."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    app = create_app(args.config)
    try:
        app.run(host=args.host, port=args.port, use_reloader=False)
    finally:
        app.extensions["jobs"].close()


if __name__ == "__main__":
    main()

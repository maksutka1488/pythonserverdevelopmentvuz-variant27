"""Утилиты тестов: настоящий HTTP-сервер на свободном порту."""

from pathlib import Path
from threading import Thread

from werkzeug.serving import WSGIRequestHandler, make_server

from src.app import create_app
from src.client import ApiClient


class QuietHandler(WSGIRequestHandler):
    """Не засоряет вывод при тысячах запросов модели."""

    def log_request(self, code="-", size="-"):
        """Пропустить обычную строку журнала HTTP."""


class RunningServer:
    """Создаёт локальное приложение с временной конфигурацией."""

    def __init__(self, directory, test_mode=True, clock=lambda: 10_000):
        self.directory = Path(directory)
        options = self.directory / "config.toml"
        options.write_text(test_config(self.directory, test_mode),
                           encoding="utf-8")
        self.app = create_app(options)
        self.jobs = self.app.extensions["jobs"]
        self.jobs.clock = clock
        self.server = make_server(
            "127.0.0.1", 0, self.app, request_handler=QuietHandler,
        )
        self.thread = Thread(target=self.server.serve_forever, args=(0.01,))
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.client = ApiClient(self.url, "tester", "secret")

    def drain(self):
        """Маркер в однопоточной очереди дожидается предыдущих заданий."""
        self.jobs.executor.submit(int).result(timeout=10)

    def close(self):
        """Остановить HTTP и дождаться фоновой очереди."""
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.jobs.close()


def test_config(directory, test_mode):
    """Сформировать настройки для независимого тестового экземпляра."""
    boolean = str(test_mode).lower()
    return (
        '[auth]\nusername = "tester"\npassword = "secret"\n'
        f'[service]\noutput_dir = "{directory / "png"}"\n'
        f'database = "{directory / "records.json"}"\n'
        f'workers = 1\ntimeout = 10\ntest_mode = {boolean}\n'
        'max_xml_bytes = 8192\n'
    )

"""Проверка настоящего subprocess, асинхронности и загрузки PNG."""

from io import BytesIO
from threading import Event

from PIL import Image

from tests.support import RunningServer

STAMP = 10_000


def test_background_png(tmp_path):
    """Ответ о постановке приходит до запуска генератора."""
    server = RunningServer(tmp_path, test_mode=False)
    let_run = Event()
    render = server.jobs.render

    def gated(argument, path):
        if not let_run.wait(5):
            raise TimeoutError("Тест не разрешил запуск генератора")
        return render(argument, path)

    server.jobs.render = gated
    client = server.client
    try:
        client.submit_individual(1, STAMP, "127.0.0.1", "ru-RU")
        row = client.submit_query(1, STAMP, "400638133393", 1)
        assert row["handled"] == 0
        assert client.list_report() == [{
            "error": None, "ip": "127.0.0.1", "argument": "400638133393",
        }]
        assert client.list_completion(1) == []
        let_run.set()
        server.drain()
        result, = client.list_completion(1)
        assert result["status"] == "done"
        png = client.download_completion(result["identifier"])
        with Image.open(BytesIO(png)) as picture:
            assert picture.format == "PNG"
            picture.verify()
        assert client.list_query(1)[0]["handled"] == STAMP
        client.adjust_query(1, argument="4006381333932")
        server.drain()
        result, = client.list_completion(1)
        assert result["status"] == "failed"
        assert result["error"]
        assert not list((tmp_path / "png").glob("*.png"))
    finally:
        let_run.set()
        server.close()

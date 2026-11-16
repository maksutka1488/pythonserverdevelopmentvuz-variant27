"""Проверка восстановления TinyDB через перезапуск приложения."""

import json

from src.store import INDIVIDUAL, QUERY, TinyStore

from tests.support import RunningServer

STAMP = 10_000


def test_reopen_database(tmp_path):
    """Ранее созданные записи и PNG доступны после перезапуска."""
    first = RunningServer(tmp_path, test_mode=False)
    try:
        first.client.submit_individual(1, STAMP, "::1", "ru-RU")
        first.client.submit_query(2, STAMP, "400638133393", 1)
        first.drain()
        result, = first.client.list_completion(2)
        png = first.client.download_completion(result["identifier"])
    finally:
        first.close()
    state = json.loads((tmp_path / "records.json").read_text())
    assert set(state) == {"individual", "query", "completion"}
    second = RunningServer(tmp_path, test_mode=False)
    try:
        assert second.client.list_individual()[0]["ip"] == "::1"
        assert second.client.list_query(1)[0]["handled"] == STAMP
        assert second.client.list_completion(2) == [result]
        assert second.client.download_completion(result["identifier"]) == png
        second.client.submit_query(3, STAMP, "5901234123457", 1)
        second.drain()
        updated, = second.client.list_completion(3)
        assert updated["identifier"] > result["identifier"]
    finally:
        second.close()


def test_resume_pending(tmp_path):
    """Сохранённое незавершённое задание снова попадает в очередь."""
    store = TinyStore(tmp_path / "records.json")
    try:
        store.put(INDIVIDUAL, dict(
            identifier=0, created=STAMP, ip="::1", locale="ru-RU",
        ))
        store.put(QUERY, dict(
            identifier=0, created=STAMP, argument="012345678901",
            individual=0, handled=0,
        ))
    finally:
        store.close()
    server = RunningServer(tmp_path, test_mode=False)
    try:
        server.drain()
        row, = server.client.list_completion(0)
        assert row["status"] == "done"
        assert server.client.download_completion(row["identifier"])
    finally:
        server.close()

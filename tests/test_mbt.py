"""Генерируемые сценарии HTTP API с независимой моделью записей."""

from tempfile import TemporaryDirectory

import pytest
from hypothesis import settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine, initialize, invariant, precondition, rule,
    run_state_machine_as_test,
)

from src.client import ApiClient, ApiError

from tests.support import RunningServer

NOW = 10_000
REPORT_WINDOW_SECONDS = 8 * 60
REPORT_BORDER = NOW - REPORT_WINDOW_SECONDS
TIMES = st.sampled_from((REPORT_BORDER - 1, REPORT_BORDER,
                         REPORT_BORDER + 1, NOW))
IPS = st.sampled_from(("127.0.0.1", "192.0.2.5", "::1", "a&b<c"))
LOCALES = st.sampled_from(("ru-RU", "en-US", "日本語"))
NUMBERS = st.text("0123456789", min_size=12, max_size=12)
IDS = st.integers(min_value=1, max_value=6)
MISSING = 999


class Machine(RuleBasedStateMachine):
    """Сверяет чтение, поиск, изменение и удаление с тремя словарями."""

    def __init__(self):
        super().__init__()
        self.temp = TemporaryDirectory()
        self.server = RunningServer(self.temp.name)
        self.api = self.server.client
        self.users = {}
        self.queries = {}
        self.results = {}

    @initialize(ip=IPS, locale=LOCALES, number=NUMBERS)
    def seed(self, ip, locale, number):
        """Показать все маршруты для сгенерированных начальных данных."""
        self.add_user(1, REPORT_BORDER, ip, locale)
        self.add_user(2, REPORT_BORDER - 1, ip, locale)
        self.add_query(1, 1, NOW, number)
        self.add_query(2, 2, NOW, number)
        assert report_set(self.api.list_report()) == self.expected_report()
        assert self.api.list_query(1, individual=2) == []
        self.edit_user(1, NOW, locale)
        self.edit_query(1, number)
        self.remove_query(2)
        self.remove_user(2)

    @rule(identifier=IDS, created=TIMES, ip=IPS, locale=LOCALES)
    def add_user(self, identifier, created, ip, locale):
        """Создать пользователя или отклонить конфликт ID."""
        if identifier in self.users:
            expect_error(409, self.api.submit_individual,
                         identifier, created, ip, locale)
            return
        row = dict(identifier=identifier, created=created,
                   ip=ip, locale=locale)
        assert self.api.submit_individual(**row) == row
        self.users[identifier] = row

    @rule(identifier=IDS, created=TIMES, locale=LOCALES)
    def edit_user(self, identifier, created, locale):
        """Проверить частичное обновление записи."""
        if identifier not in self.users:
            expect_error(404, self.api.adjust_individual,
                         identifier, created=created)
            return
        row = self.users[identifier]
        row.update(created=created, locale=locale)
        assert self.api.adjust_individual(
            identifier, created=created, locale=locale,
        ) == row

    @rule(identifier=IDS)
    def remove_user(self, identifier):
        """Проверить запрет удаления пользователя со связанным запросом."""
        if identifier not in self.users:
            expect_error(404, self.api.clear_individual, identifier)
        elif any(row["individual"] == identifier
                 for row in self.queries.values()):
            expect_error(409, self.api.clear_individual, identifier)
        else:
            assert self.api.clear_individual(identifier) == self.users.pop(
                identifier,
            )

    @rule(identifier=IDS, user=IDS, created=TIMES, number=NUMBERS)
    def add_query(self, identifier, user, created, number):
        """Принять запрос в очередь либо вернуть 404 или 409."""
        args = (identifier, created, number, user)
        if identifier in self.queries:
            expect_error(409, self.api.submit_query, *args)
        elif user not in self.users:
            expect_error(404, self.api.submit_query, *args)
        else:
            row = dict(identifier=identifier, created=created, argument=number,
                       individual=user, handled=0)
            assert self.api.submit_query(*args) == row
            self.queries[identifier] = row
            self.finished(identifier)

    @rule(identifier=IDS, number=NUMBERS)
    def edit_query(self, identifier, number):
        """Редактирование кладёт задачу в очередь повторно."""
        if identifier not in self.queries:
            expect_error(404, self.api.adjust_query, identifier,
                         argument=number)
            return
        row = self.queries[identifier]
        row.update(argument=number, handled=0)
        assert self.api.adjust_query(identifier, argument=number) == row
        self.finished(identifier)

    @rule(identifier=IDS)
    def remove_query(self, identifier):
        """Удаление задачи удаляет и её результат."""
        if identifier not in self.queries:
            expect_error(404, self.api.clear_query, identifier)
            return
        assert self.api.clear_query(identifier) == self.queries.pop(identifier)
        del self.results[identifier]
        assert self.api.list_completion(identifier) == []

    @precondition(lambda self: bool(self.queries))
    @rule(data=st.data())
    def search(self, data):
        """Проверить точное совпадение и несовпадение XML-фильтров."""
        query = data.draw(st.sampled_from(sorted(self.queries)))
        row = self.queries[query]
        user = row["individual"]
        assert self.api.list_query(user, identifier=query) == [row]
        assert self.api.list_query(user, identifier=MISSING) == []
        assert self.api.list_completion(query, status="done") == [
            self.results[query],
        ]
        assert self.api.list_completion(query, query=MISSING) == []
        assert self.api.list_individual(identifier=user) == [self.users[user]]
        assert self.api.list_individual(identifier=MISSING) == []

    @rule()
    def wrong_credentials(self):
        """Запрос без корректных credentials не получает записи."""
        denied = ApiClient(self.server.url, "tester", "wrong")
        expect_error(401, denied.list_individual)

    @rule()
    def invalid_adjust(self):
        """При отсутствии изменяемых полей должна быть ошибка 400."""
        expect_error(400, self.api.adjust_individual, MISSING)

    @invariant()
    def state_matches(self):
        """Списки и отчёт совпадают с независимой моделью после шага."""
        api = self.api
        assert keyed(api.list_individual()) == self.users
        for user in self.users:
            expected = {key: row for key, row in self.queries.items()
                        if row["individual"] == user}
            assert keyed(api.list_query(user)) == expected
        assert report_set(api.list_report()) == self.expected_report()

    def finished(self, identifier):
        """Дождаться фонового тестового задания и проверить его поля."""
        self.server.drain()
        self.queries[identifier]["handled"] = NOW
        result, = self.api.list_completion(identifier)
        expected = dict(
            identifier=result["identifier"], created=NOW, status="done",
            output="", error="", query=identifier, cache_hit=0,
        )
        assert result == expected
        self.results[identifier] = expected

    def expected_report(self):
        """Проверить Recent и unmatched для готовых результатов."""
        triples = set()
        for query in self.queries.values():
            user = self.users[query["individual"]]
            if user["created"] >= REPORT_BORDER:
                fields = ("", user["ip"], query["argument"])
            else:
                fields = ("", None, None)
            triples.add(fields)
        return triples

    def teardown(self):
        """Закрыть HTTP-сервер и удалить временные данные."""
        self.server.close()
        self.temp.cleanup()


def report_set(rows):
    """Сравнить тройки отчёта независимо от порядка строк."""
    return {(row["error"], row["ip"], row["argument"]) for row in rows}


def keyed(rows):
    """Сравнивать записи по ID независимо от порядка выдачи."""
    return {row["identifier"]: row for row in rows}


def expect_error(status, action, *args, **kwargs):
    """Проверить ожидаемый HTTP-статус."""
    with pytest.raises(ApiError) as raised:
        action(*args, **kwargs)
    assert raised.value.status == status


def test_model():
    """Сгенерировать последовательности для всех обработчиков таблицы 27."""
    run_state_machine_as_test(Machine, settings=settings(
        max_examples=30, stateful_step_count=24, deadline=None,
        derandomize=True,
    ))

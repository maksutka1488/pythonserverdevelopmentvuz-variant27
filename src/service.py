"""Управление записями и фоновыми задачами независимо от HTTP."""

from concurrent.futures import ThreadPoolExecutor
from subprocess import SubprocessError
from pathlib import Path
from threading import Lock
from time import time
from uuid import uuid4

from .store import COMPLETION, INDIVIDUAL, QUERY

REPORT_WINDOW = 8 * 60
PENDING = 0


class ServiceError(Exception):
    """Ошибка запроса, которую можно безопасно вернуть через HTTP."""

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


class Service:
    """Сериализует операции с хранилищем, выполняет PNG вне блокировки."""

    def __init__(self, store, renderer, output_dir, workers, clock=time):
        self.store = store
        self.render = renderer
        self.output_dir = Path(output_dir)
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self.clock = clock
        self.lock = Lock()
        self.active = {}
        self.next_completion = 1

    def close(self):
        """Дождаться обработчиков перед закрытием хранилища."""
        self.executor.shutdown(wait=True)
        self.store.close()

    def _find(self, table, identifier):
        row = self.store.get(table, identifier)
        if row is None:
            raise ServiceError("Запись не найдена", 404)
        return row

    def save_individual(self, identifier, fields, replace):
        """Создать запись либо изменить переданные поля."""
        with self.lock:
            if replace:
                row = self._find(INDIVIDUAL, identifier)
            elif self.store.get(INDIVIDUAL, identifier) is None:
                row = {"identifier": identifier}
            else:
                raise ServiceError("Идентификатор уже существует", 409)
            row.update(fields)
            self.store.put(INDIVIDUAL, row)
            return row

    def save_query(self, identifier, fields, replace):
        """Сохранить запрос и передать вычисление фоновому обработчику."""
        with self.lock:
            if replace:
                row = self._find(QUERY, identifier)
            elif self.store.get(QUERY, identifier) is None:
                row = {"identifier": identifier}
            else:
                raise ServiceError("Идентификатор уже существует", 409)
            row.update(fields)
            self._find(INDIVIDUAL, row["individual"])
            row["handled"] = PENDING
            self.store.put(QUERY, row)
            self._drop_completions(identifier)
            self._schedule(row)
            return row

    def _schedule(self, row):
        identifier = row["identifier"]
        token = uuid4().hex
        self.active[identifier] = token
        target = self.output_dir / f"{token}.png"
        self.executor.submit(self._work, identifier, row["argument"], target)

    def _work(self, identifier, argument, target):
        with self.lock:
            if self.active.get(identifier) != target.stem:
                return
        try:
            output = self.render(argument, target)
            status, error = "done", ""
        except (OSError, SubprocessError):
            target.unlink(missing_ok=True)
            output, status, error = "", "failed", "Ошибка генерации PNG"
        with self.lock:
            if self.active.get(identifier) != target.stem:
                target.unlink(missing_ok=True)
                return
            self._finish(identifier, output, status, error)

    def _finish(self, identifier, output, status, error):
        moment = int(self.clock())
        self.store.put(COMPLETION, {
            "identifier": self.next_completion, "created": moment,
            "output": output, "status": status, "error": error,
            "query": identifier, "cache_hit": 0,
        })
        self.next_completion += 1
        row = self.store.get(QUERY, identifier)
        row["handled"] = moment
        self.store.put(QUERY, row)
        del self.active[identifier]

    def _drop_completions(self, identifier):
        for row in self.store.all(COMPLETION):
            if row["query"] == identifier:
                self.store.delete(COMPLETION, row["identifier"])
                if row["output"]:
                    (self.output_dir / row["output"]).unlink(missing_ok=True)

    def clear(self, table, identifier):
        """Удалить запись; запрос удаляет свой результат и отменяет запись."""
        with self.lock:
            row = self._find(table, identifier)
            if table == INDIVIDUAL and self._has_queries(identifier):
                raise ServiceError("У пользователя есть запросы", 409)
            if table == QUERY:
                self.active.pop(identifier, None)
                self._drop_completions(identifier)
            self.store.delete(table, identifier)
            return row

    def _has_queries(self, identifier):
        return any(row["individual"] == identifier
                   for row in self.store.all(QUERY))

    def list(self, table, filters):
        """Найти записи, в точности совпадающие по заданным полям."""
        with self.lock:
            return [row for row in self.store.all(table)
                    if row_matches(row, filters)]

    def report(self):
        """Вернуть проекцию полного внешнего соединения из формулы 27."""
        with self.lock:
            border = int(self.clock()) - REPORT_WINDOW
            users = {row["identifier"]: row["ip"]
                     for row in self.store.all(INDIVIDUAL)
                     if row["created"] >= border}
            queries = self.store.all(QUERY)
            completions = self.store.all(COMPLETION)
        return report_rows(users, queries, completions)

    def png(self, identifier):
        """Открыть PNG под блокировкой от параллельного удаления."""
        with self.lock:
            row = self._find(COMPLETION, identifier)
            if not row["output"]:
                raise ServiceError("PNG недоступен", 404)
            try:
                return (self.output_dir / row["output"]).open("rb")
            except FileNotFoundError as error:
                raise ServiceError("PNG недоступен", 404) from error


def row_matches(row, filters):
    """Проверить равенство по всем полям фильтра."""
    return all(row.get(key) == value for key, value in filters.items())


def report_rows(users, queries, completions):
    """Сохранить также подходящие запросы без результата и наоборот."""
    selected = {q["identifier"]: (users[q["individual"]], q["argument"])
                for q in queries if q["individual"] in users}
    matched = {c["query"] for c in completions}
    rows = [(c["error"], *selected.get(c["query"], (None, None)))
            for c in completions]
    rows.extend((None, *pair) for key, pair in selected.items()
                if key not in matched)
    return [dict(zip(("error", "ip", "argument"), values))
            for values in dict.fromkeys(rows)]

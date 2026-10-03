"""Модель варианта 27: словари в памяти и реляционная выборка."""

import time
from functools import wraps
from threading import RLock

SELECTION_WINDOW = 480
INDIVIDUAL = "Individual"
QUERY = "Query"
COMPLETION = "Completion"

_tables = {INDIVIDUAL: {}, QUERY: {}, COMPLETION: {}}
_counters = dict.fromkeys(_tables, 0)
_lock = RLock()


class ModelError(Exception):
    """Ошибка модели."""


class ValidationError(ModelError):
    """Неверный тип поля или отсутствующий внешний ключ."""


class RecordNotFoundError(ModelError):
    """Запись для изменения или удаления не найдена."""


class ReferentialIntegrityError(ModelError):
    """Удаляемая запись используется другой таблицей."""


def synchronized(function):
    """Выполняет одну операцию атомарно для всех клиентов."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        with _lock:
            return function(*args, **kwargs)
    return wrapped


@synchronized
def reset():
    """Очищает модель между тестами; не является операцией RPC."""
    for table in _tables:
        _tables[table].clear()
        _counters[table] = 0


@synchronized
def create_individual(created, ip, locale):
    """Создаёт Individual и возвращает копию записи."""
    return _insert(INDIVIDUAL, _individual_fields(created, ip, locale))


@synchronized
def delete_individual(identifier):
    """Удаляет Individual, если на него не ссылается Query."""
    return _delete(INDIVIDUAL, identifier, QUERY, "individual")


@synchronized
def get_individuals():
    """Возвращает копии всех Individual в порядке создания."""
    return _all(INDIVIDUAL)


@synchronized
def update_individual(identifier, created, ip, locale):
    """Заменяет все поля Individual, сохраняя идентификатор."""
    _one(INDIVIDUAL, identifier)
    return _update(INDIVIDUAL, identifier,
                   _individual_fields(created, ip, locale))


@synchronized
def create_query(created, argument, individual, handled):
    """Создаёт Query с существующим Individual."""
    return _insert(QUERY,
                   _query_fields(created, argument, individual, handled))


@synchronized
def delete_query(identifier):
    """Удаляет Query, если на него не ссылается Completion."""
    return _delete(QUERY, identifier, COMPLETION, "query")


@synchronized
def get_queries():
    """Возвращает копии всех Query в порядке создания."""
    return _all(QUERY)


@synchronized
def update_query(identifier, created, argument, individual, handled):
    """Заменяет поля Query с проверкой внешнего ключа."""
    _one(QUERY, identifier)
    return _update(QUERY, identifier,
                   _query_fields(created, argument, individual, handled))


@synchronized
def create_completion(created, output, status, error, query, cache_hit):
    """Создаёт Completion с существующим Query."""
    return _insert(COMPLETION, _completion_fields(
        created, output, status, error, query, cache_hit))


@synchronized
def delete_completion(identifier):
    """Удаляет Completion и возвращает удалённую запись."""
    return _delete(COMPLETION, identifier)


@synchronized
def get_completions():
    """Возвращает копии всех Completion в порядке создания."""
    return _all(COMPLETION)


@synchronized
def update_completion(identifier, created, output, status, error, query,
                      cache_hit):
    """Заменяет поля Completion с проверкой внешнего ключа."""
    _one(COMPLETION, identifier)
    return _update(COMPLETION, identifier, _completion_fields(
        created, output, status, error, query, cache_hit))


@synchronized
def select_recent_completions(moment=None):
    """Проекция полного соединения отфильтрованных I JOIN Q с C."""
    if moment is None:
        moment = int(time.time())
    border = _as_int("moment", moment) - SELECTION_WINDOW
    rows = []
    matched = set()
    for query in _tables[QUERY].values():
        individual = _tables[INDIVIDUAL][query["individual"]]
        if individual["created"] < border:
            continue
        completions = [c for c in _tables[COMPLETION].values()
                       if c["query"] == query["identifier"]]
        for completion in completions:
            matched.add(completion["identifier"])
        errors = [c["error"] for c in completions] or [None]
        rows.extend((error, individual["ip"], query["argument"])
                    for error in errors)
    rows.extend((c["error"], None, None)
                for c in _tables[COMPLETION].values()
                if c["identifier"] not in matched)
    return [dict(zip(("error", "ip", "argument"), row))
            for row in dict.fromkeys(rows)]


def _individual_fields(created, ip, locale):
    return {"created": _as_int("created", created),
            "ip": _as_str("ip", ip), "locale": _as_str("locale", locale)}


def _query_fields(created, argument, individual, handled):
    return {"created": _as_int("created", created),
            "argument": _as_str("argument", argument),
            "individual": _as_key(INDIVIDUAL, "individual", individual),
            "handled": _as_int("handled", handled)}


def _completion_fields(created, output, status, error, query, cache_hit):
    return {"created": _as_int("created", created),
            "output": _as_str("output", output),
            "status": _as_str("status", status),
            "error": _as_str("error", error),
            "query": _as_key(QUERY, "query", query),
            "cache_hit": _as_int("cache_hit", cache_hit)}


def _insert(table, fields):
    _counters[table] += 1
    return _update(table, _counters[table], fields)


def _update(table, identifier, fields):
    record = {"identifier": identifier, **fields}
    _tables[table][identifier] = record
    return dict(record)


def _delete(table, identifier, child=None, foreign_key=None):
    record = _one(table, identifier)
    if child is not None:
        if any(row[foreign_key] == identifier
               for row in _tables[child].values()):
            raise ReferentialIntegrityError(
                f"{table}: запись {identifier} используется в {child}")
    del _tables[table][identifier]
    return record


def _one(table, identifier):
    key = _as_int("identifier", identifier)
    if key not in _tables[table]:
        raise RecordNotFoundError(f"{table}: записи {key} нет")
    return dict(_tables[table][key])


def _all(table):
    return [dict(record) for record in _tables[table].values()]


def _as_int(field, value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field}: ожидается int")
    return value


def _as_str(field, value):
    if not isinstance(value, str):
        raise ValidationError(f"{field}: ожидается str")
    return value


def _as_key(table, field, value):
    key = _as_int(field, value)
    if key not in _tables[table]:
        raise ValidationError(f"{field}: в {table} нет записи {key}")
    return key

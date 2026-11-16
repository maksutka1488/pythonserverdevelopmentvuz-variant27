"""Десять обработчиков из таблицы 27 и скачивание готового PNG."""

from flask import Blueprint, current_app, send_file

from .service import ServiceError
from .store import COMPLETION, INDIVIDUAL, QUERY
from .xml_api import filters, query_params, result_xml

PREFIX = "/service/api/v3"
api = Blueprint("api", __name__, url_prefix=PREFIX)
INDIVIDUAL_INPUT = {"created", "ip", "locale"}
QUERY_INPUT = {"created", "argument", "individual"}
IDENTIFIER = {"identifier"}


def _service():
    return current_app.extensions["jobs"]


def _adjust(fields):
    values = query_params(IDENTIFIER, fields | IDENTIFIER)
    identifier = values.pop("identifier")
    if not values:
        raise ServiceError("Нужно указать изменяемое поле", 400)
    return identifier, values


@api.put("/submit/individual/<int:identifier>")
def submit_individual(identifier):
    """Создать Individual с ID из пути и полями из строки запроса."""
    fields = query_params(INDIVIDUAL_INPUT, INDIVIDUAL_INPUT)
    row = _service().save_individual(identifier, fields, replace=False)
    return result_xml(INDIVIDUAL, [row])


@api.delete("/clear/individual/<int:identifier>")
def clear_individual(identifier):
    """Удалить Individual без связанных Query."""
    return result_xml(INDIVIDUAL, [_service().clear(INDIVIDUAL, identifier)])


@api.post("/list/individual")
def list_individual():
    """Выполнить поиск Individual по XML-фильтру."""
    return result_xml(INDIVIDUAL, _service().list(
        INDIVIDUAL, filters(INDIVIDUAL),
    ))


@api.post("/adjust/individual")
def adjust_individual():
    """Обновить перечисленные в URL поля Individual."""
    identifier, fields = _adjust(INDIVIDUAL_INPUT)
    row = _service().save_individual(identifier, fields, replace=True)
    return result_xml(INDIVIDUAL, [row])


@api.put("/submit/query/<int:identifier>")
def submit_query(identifier):
    """Сохранить Query и поставить его в фоновую очередь."""
    fields = query_params(QUERY_INPUT, QUERY_INPUT)
    row = _service().save_query(identifier, fields, replace=False)
    return result_xml(QUERY, [row])


@api.delete("/clear/query/<int:identifier>")
def clear_query(identifier):
    """Удалить Query и связанный результат."""
    return result_xml(QUERY, [_service().clear(QUERY, identifier)])


@api.post("/list/query/<int:individual>")
def list_query(individual):
    """Выполнить поиск Query в пределах заданного Individual."""
    return _list_children(QUERY, "individual", individual)


@api.post("/adjust/query")
def adjust_query():
    """Обновить поля Query и заново запустить вычисление."""
    identifier, fields = _adjust(QUERY_INPUT)
    row = _service().save_query(identifier, fields, replace=True)
    return result_xml(QUERY, [row])


@api.post("/list/completion/<int:query>")
def list_completion(query):
    """Выполнить поиск Completion в пределах заданного Query."""
    return _list_children(COMPLETION, "query", query)


@api.post("/list/report")
def list_report():
    """Получить отчёт по формуле 27 в XML."""
    return result_xml("report", _service().report())


def _list_children(table, field, identifier):
    values = filters(table)
    if field in values and values[field] != identifier:
        return result_xml(table, [])
    values[field] = identifier
    return result_xml(table, _service().list(table, values))


@api.get("/download/completion/<int:identifier>")
def download_completion(identifier):
    """Отдать PNG готового результата по ID Completion."""
    stream = _service().png(identifier)
    return send_file(
        stream, mimetype="image/png", as_attachment=True,
        download_name=f"ean13-{identifier}.png",
    )

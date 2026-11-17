"""Кодирование ответов и чтение точных XML-фильтров."""

import re
from xml.etree.ElementTree import Element, ParseError, SubElement, tostring

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from flask import Response, request

from .service import ServiceError
from .store import COMPLETION, INDIVIDUAL, QUERY

INT_FIELDS = {
    "identifier", "created", "individual", "handled", "query", "cache_hit",
}
FIELDS = {
    INDIVIDUAL: {"identifier", "created", "ip", "locale"},
    QUERY: {"identifier", "created", "argument", "individual", "handled"},
    COMPLETION: {
        "identifier", "created", "output", "status", "error", "query",
        "cache_hit",
    },
}
NON_XML = re.compile(
    r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]"
)


def value_as(field, value):
    """Привести числовые поля к int, остальные оставить строками."""
    if field in INT_FIELDS:
        try:
            return int(value)
        except ValueError as error:
            message = f"{field}: ожидается целое число"
            raise ServiceError(message, 400) from error
    if NON_XML.search(value):
        raise ServiceError(f"{field}: недопустимый символ XML", 400)
    return value


def query_params(required, allowed):
    """Прочитать параметры URL и проверить их имена и кратность."""
    args = request.args
    if (not required <= args.keys() or args.keys() - allowed
            or any(len(values) != 1 for _, values in args.lists())):
        raise ServiceError("Неверный набор параметров URL", 400)
    return {key: value_as(key, value) for key, value in args.items()}


def filters(table):
    """Разобрать обязательный XML-элемент filter (пустой значит все)."""
    root = _filter_root(request.get_data())
    result = {}
    for node in root:
        _check_filter_field(node, FIELDS[table], result)
        result[node.tag] = value_as(node.tag, node.text or "")
    return result


def _filter_root(data):
    """Прочитать XML и проверить корневой элемент фильтра."""
    try:
        root = ElementTree.fromstring(data)
    except (ParseError, DefusedXmlException) as error:
        raise ServiceError("Некорректный XML", 400) from error
    if root.tag != "filter" or root.attrib or (root.text or "").strip():
        raise ServiceError("Ожидается элемент <filter>", 400)
    return root


def _check_filter_field(node, allowed, used):
    """Проверить имя, уникальность и структуру одного поля."""
    if (node.tag not in allowed or node.tag in used
            or len(node) or node.attrib or (node.tail or "").strip()):
        raise ServiceError("Некорректное поле XML-фильтра", 400)


def result_xml(table, rows):
    """Сформировать XML со списком результатов."""
    root = Element("response")
    for row in rows:
        item = SubElement(root, table)
        for field, value in row.items():
            node = SubElement(item, field)
            if value is None:
                node.set("null", "true")
            else:
                node.text = str(value)
    return xml_response(root)


def error_xml(message, status):
    """Сформировать XML с читаемым описанием ошибки."""
    root = Element("response")
    SubElement(root, "error").text = message
    return xml_response(root, status)


def xml_response(root, status=200):
    """Вернуть UTF-8 XML с правильным типом содержимого."""
    body = tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(body, status, mimetype="application/xml")

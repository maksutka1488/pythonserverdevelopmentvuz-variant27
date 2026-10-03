"""JSON и бинарные кадры RPC по таблице 27, little endian."""

import json
import struct
from enum import IntEnum

from . import model

REQUEST_FORMAT = struct.Struct("<IH")
RESPONSE_FORMAT = struct.Struct("<BI")
REQUEST_HEADER = REQUEST_FORMAT.size
RESPONSE_HEADER = RESPONSE_FORMAT.size
MAX_BODY = 1048576
NO_CODE = 0
HOST = "127.0.0.1"
PORT = 8765
TIMEOUT = 10
JOURNAL = "journal.log"


class ProtocolError(ValueError):
    """Неверный заголовок, JSON или неожиданное закрытие соединения."""


ERRORS = {cls.__name__: cls for cls in (
    model.ValidationError, model.RecordNotFoundError,
    model.ReferentialIntegrityError, ProtocolError)}


class Operation(IntEnum):
    """Все 13 функций модели и соответствующие коды RPC."""

    create_individual = 1
    delete_individual = 2
    get_individuals = 3
    update_individual = 4
    create_query = 5
    delete_query = 6
    get_queries = 7
    update_query = 8
    create_completion = 9
    delete_completion = 10
    get_completions = 11
    update_completion = 12
    select_recent_completions = 13


def _serialize(value):
    body = json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")
    _check_size(len(body))
    return body


def _parse(body):
    try:
        return json.loads(body.decode("utf-8"), parse_constant=_invalid,
                          object_pairs_hook=_unique_object)
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        raise ProtocolError("тело не является корректным JSON") from error


def _invalid(value):
    raise ValueError(f"неверная константа JSON: {value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"повтор ключа: {key}")
        result[key] = value
    return result


def _check_size(size):
    if size > MAX_BODY:
        raise ProtocolError("слишком большое тело сообщения")


def encode_request(operation, arguments):
    """Размер JSON (4), код (2), JSON без версии протокола."""
    body = _serialize(arguments)
    return REQUEST_FORMAT.pack(len(body), int(operation)) + body


def decode_request_header(header):
    """Читает размер и проверяет один из 13 кодов операции."""
    if len(header) != REQUEST_HEADER:
        raise ProtocolError("короткий заголовок запроса")
    size, code = REQUEST_FORMAT.unpack(header)
    _check_size(size)
    try:
        return Operation(code), size
    except ValueError as error:
        raise ProtocolError(f"неизвестный код операции {code}") from error


def encode_response(code, body):
    """Код (1), размер JSON (4), JSON."""
    _check_size(len(body))
    return RESPONSE_FORMAT.pack(int(code), len(body)) + body


def decode_response_header(header):
    """Возвращает размер и код ответа."""
    if len(header) != RESPONSE_HEADER:
        raise ProtocolError("короткий заголовок ответа")
    code, size = RESPONSE_FORMAT.unpack(header)
    _check_size(size)
    return size, code


def parse_request(body):
    """Аргументы RPC должны быть JSON-объектом."""
    arguments = _parse(body)
    if not isinstance(arguments, dict):
        raise ProtocolError("аргументы должны быть объектом JSON")
    return arguments


def result_body(value):
    """Возвращает JSON успешного ответа."""
    return _serialize({"status": "ok", "result": value})


def error_body(error):
    """Передаёт класс и текст ошибки клиенту."""
    return _serialize({"status": "error", "type": type(error).__name__,
                       "message": str(error)})


def parse_response(body):
    """Восстанавливает результат или исключение того же класса."""
    response = _parse(body)
    if not isinstance(response, dict):
        raise ProtocolError("ответ должен быть объектом JSON")
    if response.get("status") == "ok" and "result" in response:
        return response["result"]
    kind = response.get("type")
    message = response.get("message")
    if (response.get("status") != "error" or kind not in ERRORS
            or not isinstance(message, str)):
        raise ProtocolError("неверная структура ответа")
    raise ERRORS[kind](message)

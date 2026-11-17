"""HTTP-клиент с методами вида действие_таблица."""

from base64 import b64encode
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring

from .routes import PREFIX
from .xml_api import INT_FIELDS


class ApiError(Exception):
    """Ошибка HTTP со статусом и сообщением из XML."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class ApiClient:
    """Использует urllib и HTTP Basic для запросов к Flask."""

    def __init__(self, base_url, username, password, timeout=10):
        self.url = base_url.rstrip("/") + PREFIX
        self.timeout = timeout
        credentials = ":".join((username, password)).encode("utf-8")
        token = b64encode(credentials).decode("ascii")
        self.headers = {"Authorization": f"Basic {token}"}

    def _request(self, method, path, params=None, body=None):
        url = self.url + path
        if params:
            url += "?" + urlencode(params)
        headers = dict(self.headers)
        if body is not None:
            headers["Content-Type"] = "application/xml"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as error:
            with error:
                message = fromstring(error.read()).findtext("error")
            raise ApiError(error.code, message) from error

    def _rows(self, method, path, params=None, body=None):
        data = self._request(method, path, params, body)
        return [decode_row(row) for row in fromstring(data)]

    def submit_individual(self, identifier, created, ip, locale):
        """Создать пользователя."""
        return self._rows("PUT", f"/submit/individual/{identifier}", {
            "created": created, "ip": ip, "locale": locale,
        })[0]

    def clear_individual(self, identifier):
        """Удалить пользователя."""
        return self._rows("DELETE", f"/clear/individual/{identifier}")[0]

    def list_individual(self, **fields):
        """Найти пользователей по точному совпадению полей."""
        return self._rows("POST", "/list/individual",
                          body=encode_filter(fields))

    def adjust_individual(self, identifier, **fields):
        """Изменить указанные поля пользователя."""
        return self._rows("POST", "/adjust/individual", {
            "identifier": identifier, **fields,
        })[0]

    def submit_query(self, identifier, created, argument, individual):
        """Поставить задачу на генерацию в очередь."""
        return self._rows("PUT", f"/submit/query/{identifier}", {
            "created": created, "argument": argument, "individual": individual,
        })[0]

    def clear_query(self, identifier):
        """Удалить запрос и его результат."""
        return self._rows("DELETE", f"/clear/query/{identifier}")[0]

    def list_query(self, individual, /, **fields):
        """Найти запросы заданного пользователя."""
        return self._rows("POST", f"/list/query/{individual}",
                          body=encode_filter(fields))

    def adjust_query(self, identifier, **fields):
        """Изменить запрос и снова запустить его."""
        return self._rows("POST", "/adjust/query", {
            "identifier": identifier, **fields,
        })[0]

    def list_completion(self, query, /, **fields):
        """Найти результаты заданного запроса."""
        return self._rows("POST", f"/list/completion/{query}",
                          body=encode_filter(fields))

    def list_report(self):
        """Получить отчёт по формуле 27."""
        return self._rows("POST", "/list/report")

    def download_completion(self, identifier):
        """Скачать байты PNG по идентификатору результата."""
        return self._request("GET", f"/download/completion/{identifier}")


def encode_filter(fields):
    """Закодировать словарь полей как XML-фильтр."""
    root = Element("filter")
    for field, value in fields.items():
        SubElement(root, field).text = str(value)
    return tostring(root, encoding="utf-8")


def decode_row(row):
    """Восстановить целые числа, строки и отсутствующие значения."""
    values = {}
    for node in row:
        if node.get("null") == "true":
            values[node.tag] = None
        elif node.tag in INT_FIELDS:
            values[node.tag] = int(node.text)
        else:
            values[node.tag] = node.text or ""
    return values

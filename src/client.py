"""Клиент всех 13 операций RPC с именами функций модели."""

import socket

from . import protocol


class Client:
    """Последовательные вызовы по одному TCP-соединению."""

    def __init__(self, host=protocol.HOST, port=protocol.PORT):
        self.address = (host, port)
        self.socket = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, kind, value, traceback):
        self.close()

    def connect(self):
        if self.socket is None:
            self.socket = socket.create_connection(
                self.address, timeout=protocol.TIMEOUT)

    def close(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def create_individual(self, created, ip, locale):
        return self.call(protocol.Operation.create_individual,
                         created=created, ip=ip, locale=locale)

    def delete_individual(self, identifier):
        return self.call(protocol.Operation.delete_individual,
                         identifier=identifier)

    def get_individuals(self):
        return self.call(protocol.Operation.get_individuals)

    def update_individual(self, identifier, created, ip, locale):
        return self.call(protocol.Operation.update_individual,
                         identifier=identifier, created=created,
                         ip=ip, locale=locale)

    def create_query(self, created, argument, individual, handled):
        return self.call(protocol.Operation.create_query,
                         created=created, argument=argument,
                         individual=individual, handled=handled)

    def delete_query(self, identifier):
        return self.call(protocol.Operation.delete_query,
                         identifier=identifier)

    def get_queries(self):
        return self.call(protocol.Operation.get_queries)

    def update_query(self, identifier, created, argument, individual,
                     handled):
        return self.call(protocol.Operation.update_query,
                         identifier=identifier, created=created,
                         argument=argument, individual=individual,
                         handled=handled)

    def create_completion(self, created, output, status, error, query,
                          cache_hit):
        return self.call(protocol.Operation.create_completion,
                         created=created, output=output, status=status,
                         error=error, query=query, cache_hit=cache_hit)

    def delete_completion(self, identifier):
        return self.call(protocol.Operation.delete_completion,
                         identifier=identifier)

    def get_completions(self):
        return self.call(protocol.Operation.get_completions)

    def update_completion(self, identifier, created, output, status, error,
                          query, cache_hit):
        return self.call(protocol.Operation.update_completion,
                         identifier=identifier, created=created,
                         output=output, status=status, error=error,
                         query=query, cache_hit=cache_hit)

    def select_recent_completions(self, moment=None):
        return self.call(protocol.Operation.select_recent_completions,
                         moment=moment)

    def call(self, operation, **arguments):
        """Отправляет кадр и проверяет, что ответ относится к запросу."""
        self.connect()
        try:
            self.socket.sendall(
                protocol.encode_request(operation, arguments))
            size, code = protocol.decode_response_header(
                self.receive(protocol.RESPONSE_HEADER))
            if code not in (int(operation), protocol.NO_CODE):
                raise protocol.ProtocolError("код ответа не совпадает")
            return protocol.parse_response(self.receive(size))
        except (OSError, protocol.ProtocolError):
            self.close()
            raise

    def receive(self, size):
        """Читает заданное количество байтов, учитывая дробление TCP."""
        data = bytearray()
        while len(data) < size:
            part = self.socket.recv(size - len(data))
            if not part:
                raise protocol.ProtocolError("сервер закрыл соединение")
            data += part
        return bytes(data)

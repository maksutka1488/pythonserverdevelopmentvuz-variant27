"""Многопоточный TCP-сервер и журнал запросов journal.log."""

import argparse
import logging
import socketserver

from . import model, protocol

log = logging.getLogger("rpc.requests")
FUNCTIONS = {op: getattr(model, op.name) for op in protocol.Operation}


def configure_logging():
    """Направляет запросы в UTF-8-файл journal.log."""
    handler = logging.FileHandler(protocol.JOURNAL, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    return handler


def call(operation, arguments):
    """Вызывает функцию модели с проверкой набора аргументов."""
    try:
        return FUNCTIONS[operation](**arguments)
    except TypeError as error:
        raise model.ValidationError(f"неверные аргументы: {error}") from error


class Handler(socketserver.StreamRequestHandler):
    """Обслуживает несколько последовательных запросов соединения."""

    def setup(self):
        self.request.settimeout(protocol.TIMEOUT)
        super().setup()

    def handle(self):
        try:
            while True:
                header = self.rfile.read(protocol.REQUEST_HEADER)
                if not header:
                    return
                if not self.serve(header):
                    return
        except OSError:
            return

    def serve(self, header):
        code = protocol.NO_CODE
        body_read = False
        log.info("request peer=%s header=%s", self.client_address,
                 header.hex())
        try:
            operation, size = protocol.decode_request_header(header)
            code = int(operation)
            raw = self.rfile.read(size)
            log.info("request code=%s body=%r", operation.name, raw)
            if len(raw) != size:
                raise protocol.ProtocolError("неполное тело запроса")
            body_read = True
            arguments = protocol.parse_request(raw)
            body = protocol.result_body(call(operation, arguments))
        except (model.ModelError, protocol.ProtocolError) as error:
            body = protocol.error_body(error)
        self.wfile.write(protocol.encode_response(code, body))
        return body_read


class Server(socketserver.ThreadingTCPServer):
    """TCP-сервер со свободным завершением потоков клиентов."""

    allow_reuse_address = True
    daemon_threads = True


def create(host=protocol.HOST, port=protocol.PORT):
    """Создаёт сервер; port=0 выбирает свободный порт для тестов."""
    return Server((host, port), Handler)


def main():
    """Запускает сервер с обязательным журналом запросов."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=protocol.HOST)
    parser.add_argument("--port", type=int, default=protocol.PORT)
    options = parser.parse_args()
    handler = configure_logging()
    try:
        with create(options.host, options.port) as instance:
            print(f"RPC: {instance.server_address}; журнал: journal.log")
            try:
                instance.serve_forever()
            except KeyboardInterrupt:
                pass
    finally:
        log.removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    main()

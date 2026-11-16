# Практическая работа №2 · Вариант 27

Асинхронная генерация штрихкодов EAN-13 в PNG. Этап 1: консольный
генератор на Python 3.11+.

```sh
python3 -m venv .venv
source .venv/bin/activate
make install PYTHON=python
```

Утилита принимает одну строку через stdin, путь к PNG — аргументом.
Для 12 цифр вычисляет контрольную цифру; для 13 проверяет её.
Печатает полный EAN-13. При ошибке выводит причину в stderr и завершает
работу с кодом 2. Папка назначения создаётся автоматически.

| Пример | Ввод | Ожидаемый EAN-13 |
| --- | --- | --- |
| 1 | `400638133393` | `4006381333931` |
| 2 | `5901234123457` | `5901234123457` |
| 3 | `012345678901` | `0123456789012` |

```sh
printf '%s\n' 400638133393 | python -m src.barcode data/example1.png
printf '%s\n' 5901234123457 | python -m src.barcode data/example2.png
printf '%s\n' 012345678901 | python -m src.barcode data/example3.png
```

`normalize_ean13` проверяет вход; `write_png` сохраняет изображение;
`main` связывает функции со stdin и аргументом командной строки.
Сгенерированные PNG находятся в `data/` и в Git не входят.

Проверка: `python -m pip install -r requirements-dev.txt`, затем
`python -m pytest -q`.

## Этап 2. Flask HTTP API

Сервер принимает запрос, возвращает XML с `handled=0` и отправляет
вычисление в очередь. Поток запускает CLI через `subprocess`; после
завершения появляется запись Completion. Авторизация — HTTP Basic
([RFC 7617](https://www.rfc-editor.org/rfc/rfc7617)). Запуск по
умолчанию доступен только на своём компьютере.

```sh
cp config.example.toml config.toml
make install PYTHON=python
make run PYTHON=python
```

Во втором терминале, в той же папке и с активированной `.venv`:

```sh
python -m src.demo
```

Утилита проводит полный сценарий и скачивает `data/demo.png`. Для
повторного запуска на той же базе задай новый ID: `--identifier 2`.

### Маршруты и клиент

Префикс всех путей: `/service/api/v3`. В таблице `{id}` — целое
неотрицательное число в пути. При успехе обязательные маршруты
возвращают `200 OK` и XML.

| Метод и путь | Вход | Метод класса `ApiClient` |
| --- | --- | --- |
| PUT `/submit/individual/{id}` | URL: `created, ip, locale` | `submit_individual` |
| DELETE `/clear/individual/{id}` | Только путь | `clear_individual` |
| POST `/list/individual` | XML-фильтр | `list_individual` |
| POST `/adjust/individual` | URL: `identifier` и изменяемые поля Individual | `adjust_individual` |
| PUT `/submit/query/{id}` | URL: `created, argument, individual` | `submit_query` |
| DELETE `/clear/query/{id}` | Только путь | `clear_query` |
| POST `/list/query/{individual}` | ID пользователя в пути, XML-фильтр | `list_query` |
| POST `/adjust/query` | URL: `identifier` и изменяемые поля Query | `adjust_query` |
| POST `/list/completion/{query}` | ID запроса в пути, XML-фильтр | `list_completion` |
| POST `/list/report` | Без параметров | `list_report` |
| GET `/download/completion/{id}` | ID результата; ответ `image/png` | `download_completion` |

Все методы клиента принимают базовый адрес через конструктор
`ApiClient(base_url, username, password, timeout=10)`. Ошибка HTTP
доступна через `ApiError.status`. Поиск принимает именованные
фильтры. `<filter/>` означает отсутствие фильтра, а
`<filter><locale>ru-RU</locale></filter>` выбирает точные совпадения.
Ответ содержит корневой элемент `<response>` и элементы записей.

```sh
API=http://127.0.0.1:8000/service/api/v3
NOW=$(date +%s)
curl -i -u demo:demo -X PUT "$API/submit/individual/42?created=$NOW&ip=127.0.0.1&locale=ru-RU"
curl -i -u demo:demo -X PUT "$API/submit/query/42?created=$NOW&argument=400638133393&individual=42"
curl -i -u demo:demo -H 'Content-Type: application/xml' -d '<filter/>' "$API/list/completion/42"
curl -i -u demo:demo -X POST "$API/list/report"
```

Если запрос к Completion вернул пустой список, повтори его после
завершения задачи. Успешный результат содержит `status=done` и
`output` — имя PNG. При неверной контрольной цифре задача
завершается с `status=failed` и непустым `error`.

Схема из рисунка 27: Individual (`identifier, created, ip, locale`),
Query (`identifier, created, argument, individual, handled`) и
Completion (`identifier, created, output, status, error, query,
cache_hit`). Время — Unix-секунды. `argument` — цифры штрихкода.
`handled=0` означает ожидание, иначе это время завершения.
`cache_hit=0`: кеш не используется. При изменении Query создаётся
новый результат; при удалении Query удаляется и результат. Нельзя
удалить Individual с запросами. При ошибке авторизации возвращается
`401` с `WWW-Authenticate`, при неверном вводе — `400`, при отсутствии
записи — `404`, при конфликте — `409`.

Отчёт выбирает пользователей, созданных не раньше 8 минут назад,
соединяет их с запросами, затем выполняет полное внешнее соединение
с результатами. Остаются три поля: `error, ip, argument`. Запрос
без результата содержит `error null="true"`, результат без
подходящего пользователя — отсутствующие `ip` и `argument`.
Дубликаты проекции убираются. Порядок строк не задан.

### Настройки, файлы и проверки

- `auth.username`, `auth.password` — имя и пароль HTTP Basic. Локальный
  `config.toml` игнорируется Git. Значения `demo` только для примеров.
- `service.output_dir` — папка PNG.
- `service.workers` — число фоновых потоков; `service.timeout` —
  предел работы дочернего процесса в секундах.
- `service.test_mode` — запускает обработчик без вызова CLI и файла.
- `service.max_xml_bytes` — предел размера тела запроса.
- `python -m src.server --help`: `--config`, `--host`, `--port`.
- `python -m src.demo --help`: `--config`, `--url`, `--output`,
  `--identifier`.
- `src/app.py` собирает Flask, `routes.py` описывает HTTP, `xml_api.py`
  оформляет XML, `service.py` управляет связями и задачами, `jobs.py`
  вызывает генератор, `store.py` хранит и выдаёт записи.
- `make test` запускает весь набор тестов; `make coverage` запускает
  только MBT по ветвям. Результаты — в [COVERAGE.md](COVERAGE.md).
  `make lint` проверяет Python на PEP 8.

## Этап 3. TinyDB

В итоговой версии `TinyStore` хранит три таблицы в JSON-файле TinyDB.
Настройка `service.database` задаёт путь (`data/records.json` по
умолчанию в примере). Файл и папка PNG создаются автоматически.
Записи и PNG сохраняются после перезапуска; задачи с `handled=0`
снова ставятся в очередь. Для одного файла базы запускай один
процесс сервера: потоки внутри него синхронизирует общий объект
`Service`. Пути к базе и PNG в примере считаются от корня проекта.

Если `config.toml` остался от этапа 2, добавь строку
`database = "data/records.json"` в секцию `[service]`.
Для тестового режима используй отдельные пути к базе и PNG.

## Как защищать по коммитам

Открой историю `main`. Три коммита ПР №2 образуют последовательность:

| Этап | Коммит | Что показать |
| --- | --- | --- |
| 1. CLI | `280f5e9` · `feat(cli)` | Три команды из примеров; открыть три PNG; объяснить контрольную цифру |
| 2. HTTP | `27e168a` · `feat(api)` | Сервер и `python -m src.demo`; XML, 401 без авторизации, фоновой результат и `make coverage` |
| 3. TinyDB | `feat(storage)` — итоговый коммит ПР №2 | Файл TinyDB, перезапуск с сохранением данных, тот же MBT и отчёт по ветвям |

Чтобы действительно запустить ранний этап, в отдельной копии Git
выполни `git switch --detach 280f5e9` или
`git switch --detach 27e168a`, затем следуй README именно этой версии.
Сервер перед переключением останавливай. Для этапа 2 можно передать
`--config config.example.toml` серверу и демонстрации, чтобы не менять
локальные настройки. Для возврата к этапу 3 выполни `git switch main`.

Короткий сценарий: на этапе 1 показать, **как получается PNG**.
На этапе 2 показать, **как API запускает ту же утилиту в фоне**.
На этапе 3 показать, **почему после перезапуска задачи и результаты
остаются доступными**, и повторно запустить тот же тест модели.

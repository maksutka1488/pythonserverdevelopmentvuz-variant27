# Практическая работа №1, вариант 27

Прототип RPC поверх TCP. Таблицы Individual, Query и Completion хранятся
в памяти в виде словарей. Python 3.10+, стандартная библиотека.

## Этап 1. Модель и REPL

`src/model.py` реализует 13 операций: создание, удаление, чтение всех
записей и полное редактирование каждой таблицы, а также выборку.
`src/repl.py` предоставляет интерактивный режим.

```bash
python3 -m src.repl
python3 -m src.repl < examples.repl
```

Идентификаторы выдаются с 1 независимо для каждой таблицы, после удаления
не переиспользуются. Изменять identifier нельзя. Внешние ключи проверяются;
удаление родителя с дочерними записями запрещено. Все операции атомарны.
Полученные записи являются копиями.

Пример команд с демонстрацией всех операций и ошибок: `examples.repl`.

Структура проекта и способ запуска следуют примеру:
[Beskaryk/pythonserverdevelopmentvuz](https://github.com/Beskaryk/pythonserverdevelopmentvuz).
Реализация адаптирована к варианту 27.


## Этап 2. RPC поверх TCP

`src/protocol.py` кодирует JSON и кадры по таблице 27.
`src/server.py` принимает запросы, `src/client.py` предоставляет класс
`Client` с теми же именами и аргументами 13 методов модели.

```bash
python3 -m src.server --host 127.0.0.1 --port 8765
```

В другом терминале:

```bash
python3 -m src.repl --rpc --host 127.0.0.1 --port 8765
python3 -m src.repl --rpc < examples.repl
```

Каждый запрос журналируется в `journal.log` в текущей папке сервера.
Файл содержит время, адрес клиента, заголовок, код операции и JSON.
Таблицы на диск не сохраняются. Перезапуск сервера очищает данные.

Запрос: размер тела (4 байта), код операции (2 байта), JSON UTF-8.
Ответ: код операции (1 байт), размер тела (4 байта), JSON UTF-8.
Все числовые поля заголовков передаются little endian. Поля версии нет.
Размер означает количество байтов JSON, а не символов.

Тело запроса - объект именованных аргументов. Успех:
`{"status":"ok","result":...}`. Ошибка:
`{"status":"error","type":"ValidationError","message":"..."}`.
Код ответа совпадает с кодом запроса; ошибка заголовка имеет код 0,
после неё сервер закрывает соединение. Ошибка модели не закрывает его.

Настройки: `--host`, `--port` сервера и RPC REPL;
`protocol.MAX_BODY` (1 МиБ), `protocol.TIMEOUT` (10 секунд),
`model.SELECTION_WINDOW` (480 секунд). Имя журнала: `journal.log`.


## Схема данных

| Таблица | Поля, кроме identifier: int |
| --- | --- |
| Individual | created: int, ip: str, locale: str |
| Query | created: int, argument: str, individual: int, handled: int |
| Completion | created: int, output: str, status: str, error: str, query: int, cache_hit: int |

Query.individual ссылается на Individual.identifier;
Completion.query ссылается на Query.identifier. bool не принимается как int.
Ограничений на содержимое строк и значения целых чисел в задании нет.
Редактирование заменяет все поля записи, удаление возвращает удалённую
запись. Ошибка оставляет состояние и счётчики без изменений.

## Все функции и коды RPC

| Код | Функция модели и метод Client |
| --- | --- |
| 1 | create_individual(created, ip, locale) |
| 2 | delete_individual(identifier) |
| 3 | get_individuals() |
| 4 | update_individual(identifier, created, ip, locale) |
| 5 | create_query(created, argument, individual, handled) |
| 6 | delete_query(identifier) |
| 7 | get_queries() |
| 8 | update_query(identifier, created, argument, individual, handled) |
| 9 | create_completion(created, output, status, error, query, cache_hit) |
| 10 | delete_completion(identifier) |
| 11 | get_completions() |
| 12 | update_completion(identifier, created, output, status, error, query, cache_hit) |
| 13 | select_recent_completions(moment=None) |

reset() - служебная очистка модели для тестов; через RPC не доступна.

## Выборка по формуле варианта 27

```text
PROJECT[C.error, I.ip, Q.argument](
    SELECT[I.created >= now - 8 min](
        I INNER JOIN[I.identifier = Q.individual] Q)
    FULL OUTER JOIN[Q.identifier = C.query] C)
```

Сначала соединяются Individual и Query. Фильтр применяется к
Individual.created, граница включительна. Затем выполняется полное внешнее
соединение с Completion. Поэтому:

- у подходящего Query без Completion error = None;
- Completion старого Individual остаётся с ip = None, argument = None;
- Individual без Query отсутствует, так как первое соединение внутреннее.

moment задаёт now в секундах Unix; по умолчанию берётся текущее время.
created у Query и Completion не влияет на фильтр. Проекция удаляет
дубликаты по правилам реляционной алгебры. Порядок строк выборки не является
частью контракта.

Ошибки: ValidationError (тип, набор аргументов, внешний ключ),
RecordNotFoundError (нет записи), ReferentialIntegrityError (запись
используется дочерней таблицей), ProtocolError (кадр, JSON, соединение).
Клиент восстанавливает тот же класс исключения, что и сервер.

## Подготовка, сборка и запуск

Отдельной сборки нет. Зависимости нужны только для тестирования.
Выполняйте команды из корня репозитория.

```bash
git clone https://github.com/maksutka1488/pythonserverdevelopmentvuz-variant27.git
cd pythonserverdevelopmentvuz-variant27
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
make server
```

Windows: окружение активируется `.venv\Scripts\activate`;
команды без make приведены ниже.

| Команда | Действие |
| --- | --- |
| make install | Установка зависимостей тестов |
| make server | TCP-сервер |
| make repl | Интерактивная модель |
| make client | Интерактивный RPC-клиент |
| make demo | Все команды examples.repl на модели |
| make demo-rpc | Те же команды через запущенный RPC-сервер |
| make test | Весь набор тестов |
| make coverage | Только MBT и отчёт с учётом ветвей |

## Пример клиента из Python

```python
from src.client import Client

with Client("127.0.0.1", 8765) as client:
    individual = client.create_individual(1000000, "192.0.2.1", "ru-RU")
    query = client.create_query(1000000, "SELECT 1",
                                individual["identifier"], 0)
    client.create_completion(1000000, "1", "done", "",
                             query["identifier"], 0)
    print(client.select_recent_completions(1000000))
```

Результат: `[{'error': '', 'ip': '192.0.2.1', 'argument': 'SELECT 1'}]`.
Полная демонстрация всех операций и ошибок: [DEMONSTRATION.md](DEMONSTRATION.md).
Демонстрацию лучше запускать на свежем сервере, так как её идентификаторы
рассчитаны на пустые таблицы.

## Этап 3. Hypothesis MBT

`tests/test_mbt.py` использует RuleBasedStateMachine. Независимый эталон
Expected хранит записи в списках и выполняет соединение отдельно от модели.
Все вызовы 13 методов RPC выполняются в генерируемой Hypothesis машине:
initialize, rule, invariant. После каждого действия сверяются три таблицы
и выборка. Настройки: 100 последовательностей, до 40 шагов, без deadline,
с воспроизводимой генерацией derandomize=True.

Начальные данные тоже генерируются: они обеспечивают вызов всех методов,
проверку границы 8 минут, полного соединения и устранения дубликатов.
В teardown проверяется, что множество вызванных методов равно всем 13
операциям. Генерируются изменения внешних ключей, ошибки типов,
отсутствующие записи, запрещённое удаление родителя, удаление детей и
повторное создание. Сервер работает на свободном локальном порту.

`tests/test_protocol.py` дополнительно генерирует проверки JSON, Unicode,
точных смещений заголовка, ошибок протокола и ограничения размера.

```bash
python -m pytest tests
python -m coverage run --branch --source=src -m pytest tests/test_mbt.py
python -m coverage report -m
python -m coverage html
```

Проверено 03.10.2026: 9 тестов прошли. Модель получила 100% покрытия строк
и ветвей при запуске только MBT. Все 13 методов Client покрыты целиком.
Общее покрытие src в MBT составляет 73%: в него входят также REPL,
командный запуск сервера и защитные ветви транспорта.
Отчёт с пояснением границ измерения: [COVERAGE.md](COVERAGE.md).

## Соответствие этапам

| Этап | Результат |
| --- | --- |
| 1 | Словари, 12 операций таблиц, выборка, REPL и примеры ошибок |
| 2 | TCP RPC для 13 функций, кадры JSON таблицы 27, Client, journal.log |
| 3 | Hypothesis RuleBasedStateMachine и отдельный отчёт coverage --branch |

Структура и оформление следуют примеру одногруппника. Код, сущности,
операции, протокол и тесты реализованы для варианта 27 по страницам 84-86
сборника ИКБО-71-24. Этапы отражены коммитами Conventional/Scoped Commits.

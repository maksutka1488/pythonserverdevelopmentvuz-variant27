# Отчёт покрытия только Hypothesis MBT

Измерение 03.10.2026, Python 3.14.7, Hypothesis 6.168.3, pytest 9.1.1, coverage 7.16.2.

Команда (дополнительные тесты протокола не включены):

```bash
python -m coverage run --branch --source=src -m pytest tests/test_mbt.py
python -m coverage report -m
```

```text
1 passed
Name              Stmts   Miss Branch BrPart  Cover   Missing
-------------------------------------------------------------
src/__init__.py       0      0      0      0   100%
src/client.py        63      7     10      3    86%   16-17, 20, 28->exit, 100, 103-104, 112
src/model.py        122      0     22      0   100%
src/protocol.py      92     12     18      7    83%   59-60, 64, 71, 78, 90, 95-96, 108, 118, 137, 144
src/repl.py          59     59     16      0     0%   3-94
src/server.py        72     25      8      3    65%   15-20, 45-47, 60, 84-98, 102
-------------------------------------------------------------
TOTAL               408    103     74     13    73%
```

## Покрытие всех методов Client

| Метод RPC | Исполнено / строк | Покрытие |
| --- | --- | --- |
| create_individual | 1 / 1 | 100% |
| delete_individual | 1 / 1 | 100% |
| get_individuals | 1 / 1 | 100% |
| update_individual | 1 / 1 | 100% |
| create_query | 1 / 1 | 100% |
| delete_query | 1 / 1 | 100% |
| get_queries | 1 / 1 | 100% |
| update_query | 1 / 1 | 100% |
| create_completion | 1 / 1 | 100% |
| delete_completion | 1 / 1 | 100% |
| get_completions | 1 / 1 | 100% |
| update_completion | 1 / 1 | 100% |
| select_recent_completions | 1 / 1 | 100% |

Модель: 122/122 исполняемые строки и 22/22 направления ветвлений (100%).
У 13 методов клиента нет ветвлений: таблица подтверждает покрытие их тел.
Общие функции подключения и чтения TCP имеют отдельные защитные ветви;
поэтому весь файл client.py получил 86%, а весь src - 73%.
REPL и CLI сервера в этом прогоне не запускаются.

Все методы вызываются только из генерируемой RuleBasedStateMachine,
включая initialize с генерируемыми строками. В каждом примере проверяется
множество из 13 вызванных методов. Детерминированные демонстрации не входят
в измерение. Дополнительный отдельный прогон всего набора: 9 passed.

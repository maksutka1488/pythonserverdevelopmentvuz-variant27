# Демонстрация всех 13 операций

Проверено 03.10.2026: результаты REPL модели и RPC совпадают.
Сервер запущен отдельным процессом; journal.log содержит все 13 кодов. Данные примеров вымышленные.

## Команды

```text
create_individual 1000000 127.0.0.1 ru-RU
get_individuals
update_individual 1 1000000 192.0.2.1 ru-RU
create_individual 999519 192.0.2.2 en-US
create_query 1000000 "SELECT 1" 1 0
get_queries
update_query 1 1000000 "SELECT 2" 1 1
create_query 1000000 "old individual" 2 0
create_query 1000000 "without completion" 1 0
create_completion 1000000 "2" done "" 1 0
get_completions
update_completion 1 1000000 "2" failed "test error" 1 1
create_completion 1000000 "" failed "old error" 2 0
select_recent_completions 1000000
delete_individual 1
delete_query 1
create_individual abc 127.0.0.1 ru-RU
create_query 1000000 test 999 0
update_completion 999 1000000 "" done "" 1 0
delete_completion 999
delete_completion 1
delete_completion 2
delete_query 1
delete_query 2
delete_query 3
delete_individual 1
delete_individual 2
get_individuals
get_queries
get_completions
exit
```

## Вывод модели и RPC

```text
Команды:
  create_individual created ip locale
  delete_individual identifier
  get_individuals
  update_individual identifier created ip locale
  create_query created argument individual handled
  delete_query identifier
  get_queries
  update_query identifier created argument individual handled
  create_completion created output status error query cache_hit
  delete_completion identifier
  get_completions
  update_completion identifier created output status error query cache_hit
  select_recent_completions [moment]
  help, exit
Число в кавычках: строка; без кавычек: int. null означает None.
>>> {'identifier': 1, 'created': 1000000, 'ip': '127.0.0.1', 'locale': 'ru-RU'}
>>> [{'identifier': 1, 'created': 1000000, 'ip': '127.0.0.1', 'locale': 'ru-RU'}]
>>> {'identifier': 1, 'created': 1000000, 'ip': '192.0.2.1', 'locale': 'ru-RU'}
>>> {'identifier': 2, 'created': 999519, 'ip': '192.0.2.2', 'locale': 'en-US'}
>>> {'identifier': 1, 'created': 1000000, 'argument': 'SELECT 1', 'individual': 1, 'handled': 0}
>>> [{'identifier': 1, 'created': 1000000, 'argument': 'SELECT 1', 'individual': 1, 'handled': 0}]
>>> {'identifier': 1, 'created': 1000000, 'argument': 'SELECT 2', 'individual': 1, 'handled': 1}
>>> {'identifier': 2, 'created': 1000000, 'argument': 'old individual', 'individual': 2, 'handled': 0}
>>> {'identifier': 3, 'created': 1000000, 'argument': 'without completion', 'individual': 1, 'handled': 0}
>>> {'identifier': 1, 'created': 1000000, 'output': '2', 'status': 'done', 'error': '', 'query': 1, 'cache_hit': 0}
>>> [{'identifier': 1, 'created': 1000000, 'output': '2', 'status': 'done', 'error': '', 'query': 1, 'cache_hit': 0}]
>>> {'identifier': 1, 'created': 1000000, 'output': '2', 'status': 'failed', 'error': 'test error', 'query': 1, 'cache_hit': 1}
>>> {'identifier': 2, 'created': 1000000, 'output': '', 'status': 'failed', 'error': 'old error', 'query': 2, 'cache_hit': 0}
>>> [{'error': 'test error', 'ip': '192.0.2.1', 'argument': 'SELECT 2'}, {'error': None, 'ip': '192.0.2.1', 'argument': 'without completion'}, {'error': 'old error', 'ip': None, 'argument': None}]
>>> ReferentialIntegrityError: Individual: запись 1 используется в Query
>>> ReferentialIntegrityError: Query: запись 1 используется в Completion
>>> ValidationError: created: ожидается int
>>> ValidationError: individual: в Individual нет записи 999
>>> RecordNotFoundError: Completion: записи 999 нет
>>> RecordNotFoundError: Completion: записи 999 нет
>>> {'identifier': 1, 'created': 1000000, 'output': '2', 'status': 'failed', 'error': 'test error', 'query': 1, 'cache_hit': 1}
>>> {'identifier': 2, 'created': 1000000, 'output': '', 'status': 'failed', 'error': 'old error', 'query': 2, 'cache_hit': 0}
>>> {'identifier': 1, 'created': 1000000, 'argument': 'SELECT 2', 'individual': 1, 'handled': 1}
>>> {'identifier': 2, 'created': 1000000, 'argument': 'old individual', 'individual': 2, 'handled': 0}
>>> {'identifier': 3, 'created': 1000000, 'argument': 'without completion', 'individual': 1, 'handled': 0}
>>> {'identifier': 1, 'created': 1000000, 'ip': '192.0.2.1', 'locale': 'ru-RU'}
>>> {'identifier': 2, 'created': 999519, 'ip': '192.0.2.2', 'locale': 'en-US'}
>>> []
>>> []
>>> []
>>> 
```

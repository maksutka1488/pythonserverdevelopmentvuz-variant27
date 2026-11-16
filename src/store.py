"""Интерфейс хранения записей и реализация в памяти."""

INDIVIDUAL = "individual"
QUERY = "query"
COMPLETION = "completion"
TABLES = (INDIVIDUAL, QUERY, COMPLETION)


class MemoryStore:
    """Хранит записи по идентификатору; возвращает отдельные копии."""

    def __init__(self):
        self.tables = {name: {} for name in TABLES}

    def get(self, table, identifier):
        """Вернуть запись или None."""
        row = self.tables[table].get(identifier)
        return dict(row) if row is not None else None

    def all(self, table):
        """Вернуть копии всех записей."""
        return [dict(row) for row in self.tables[table].values()]

    def put(self, table, row):
        """Добавить или заменить запись по её identifier."""
        self.tables[table][row["identifier"]] = dict(row)

    def delete(self, table, identifier):
        """Удалить существующую запись."""
        del self.tables[table][identifier]

    def close(self):
        """Реализация в памяти не держит открытые файлы."""

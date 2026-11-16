"""Слой доступа к файловой базе TinyDB."""

from pathlib import Path

from tinydb import TinyDB
from tinydb.table import Document

INDIVIDUAL = "individual"
QUERY = "query"
COMPLETION = "completion"


class TinyStore:
    """Открывает таблицы TinyDB и адаптирует их к операциям Service."""

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(path, ensure_ascii=False, indent=2)

    def get(self, table, identifier):
        """Вернуть копию документа по ID или None."""
        row = self.db.table(table).get(doc_id=identifier + 1)
        return dict(row) if row is not None else None

    def all(self, table):
        """Вернуть копии документов таблицы."""
        return [dict(row) for row in self.db.table(table).all()]

    def put(self, table, row):
        """Сохранить документ; смещение даёт ID TinyDB от единицы."""
        document = Document(row, doc_id=row["identifier"] + 1)
        self.db.table(table).upsert(document)

    def delete(self, table, identifier):
        """Удалить документ по ID."""
        self.db.table(table).remove(doc_ids=[identifier + 1])

    def close(self):
        """Закрыть файл TinyDB."""
        self.db.close()

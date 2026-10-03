"""Hypothesis MBT: независимый эталон на списках против TCP RPC."""

import threading
import time

import pytest
from hypothesis import settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine, initialize, invariant, rule,
)

from src import model, protocol, server
from src.client import Client

TABLES = ("individual", "query", "completion")
FIELDS = {
    "individual": ("created", "ip", "locale"),
    "query": ("created", "argument", "individual", "handled"),
    "completion": ("created", "output", "status", "error", "query",
                   "cache_hit"),
}
PLURALS = {"individual": "individuals", "query": "queries",
           "completion": "completions"}
TEXT = st.text(max_size=16)
TIME = st.integers(min_value=0, max_value=2000000000)
MISSING = st.integers(min_value=-100, max_value=0)
BAD_INT = st.one_of(st.none(), st.booleans(), TEXT)
BAD_STR = st.one_of(st.none(), st.booleans(), TIME)
EXAMPLES = 100
STEPS = 40
ANCHOR = 1000000
WINDOW = 8 * 60


class Expected:
    """Эталон на списках, не использующий функции рабочей модели."""

    def __init__(self):
        self.rows = {table: [] for table in TABLES}
        self.counters = dict.fromkeys(TABLES, 0)

    def add(self, table, fields):
        self.counters[table] += 1
        record = {"identifier": self.counters[table], **fields}
        self.rows[table].append(record)
        return dict(record)

    def update(self, table, identifier, fields):
        record = {"identifier": identifier, **fields}
        index = next(i for i, row in enumerate(self.rows[table])
                     if row["identifier"] == identifier)
        self.rows[table][index] = record
        return dict(record)

    def referenced(self, table, identifier):
        children = {"individual": "query", "query": "completion"}
        if table not in children:
            return False
        return any(row[table] == identifier
                   for row in self.rows[children[table]])

    def delete(self, table, record):
        self.rows[table].remove(record)
        return dict(record)

    def select(self, moment):
        joined = [(i, q) for i in self.rows["individual"]
                  for q in self.rows["query"]
                  if i["identifier"] == q["individual"]
                  and i["created"] >= moment - WINDOW]
        rows = self._left_rows(joined)
        for c in self.rows["completion"]:
            if not any(q["identifier"] == c["query"] for _, q in joined):
                rows.append({"error": c["error"], "ip": None,
                             "argument": None})
        unique = []
        for row in rows:
            if row not in unique:
                unique.append(row)
        return unique

    def _left_rows(self, joined):
        rows = []
        for individual, query in joined:
            completions = [c for c in self.rows["completion"]
                           if c["query"] == query["identifier"]]
            for completion in completions or [None]:
                rows.append({
                    "error": None if completion is None
                    else completion["error"],
                    "ip": individual["ip"],
                    "argument": query["argument"],
                })
        return rows


@pytest.fixture(scope="module")
def rpc_address():
    """Один сервер на свободном порту с гарантированным завершением."""
    with server.create("127.0.0.1", 0) as instance:
        worker = threading.Thread(target=instance.serve_forever, daemon=True)
        worker.start()
        yield instance.server_address
        instance.shutdown()
        worker.join()


class RpcMachine(RuleBasedStateMachine):
    """Генерирует действия над таблицами и сверяет состояние с эталоном."""

    address = None

    def __init__(self):
        super().__init__()
        model.reset()
        self.expected = Expected()
        self.client = Client(*self.address)
        self.called = set()

    def invoke(self, name, **fields):
        self.called.add(name)
        return getattr(self.client, name)(**fields)

    def add(self, table, **fields):
        expected = self.expected.add(table, fields)
        assert self.invoke(f"create_{table}", **fields) == expected
        return expected

    @initialize(ip=TEXT, argument=TEXT, error=TEXT)
    def prepare(self, ip, argument, error):
        boundary = self.add("individual", created=ANCHOR - WINDOW,
                            ip=ip, locale="ru-RU")
        old = self.add("individual", created=ANCHOR - WINDOW - 1,
                       ip=ip, locale="en-US")
        self.add("individual", created=ANCHOR, ip=ip, locale="ru")
        first = self.add("query", created=0, argument=argument,
                         individual=boundary["identifier"], handled=0)
        self.add("query", created=0, argument="without completion",
                 individual=boundary["identifier"], handled=0)
        second = self.add("query", created=ANCHOR, argument=argument,
                          individual=old["identifier"], handled=0)
        for query in (first, first, second):
            self.add("completion", created=0, output="", status="failed",
                     error=error, query=query["identifier"], cache_hit=0)
        self.check_selection(ANCHOR)
        self.check_selection(ANCHOR + 1)
        self.exercise_edit_delete(ip, argument, error)

    def exercise_edit_delete(self, ip, argument, error):
        individual = self.add("individual", created=ANCHOR,
                              ip=ip, locale="ru")
        query = self.add("query", created=ANCHOR, argument=argument,
                         individual=individual["identifier"], handled=0)
        completion = self.add("completion", created=ANCHOR, output="",
                              status="ok", error=error,
                              query=query["identifier"], cache_hit=0)
        for table, record in zip(TABLES, (individual, query, completion)):
            fields = {key: record[key] for key in FIELDS[table]}
            fields["created"] += 1
            self.edit(table, record["identifier"], fields)
        for table in reversed(TABLES):
            self.remove(table, self.expected.rows[table][-1])

    def edit(self, table, identifier, fields):
        expected = self.expected.update(table, identifier, fields)
        assert self.invoke(f"update_{table}", identifier=identifier,
                           **fields) == expected

    def remove(self, table, record):
        name = f"delete_{table}"
        identifier = record["identifier"]
        if self.expected.referenced(table, identifier):
            with pytest.raises(model.ReferentialIntegrityError):
                self.invoke(name, identifier=identifier)
        else:
            assert self.invoke(name, identifier=identifier) == \
                self.expected.delete(table, record)

    def generated_fields(self, table, data):
        fields = {}
        for name in FIELDS[table]:
            if name in ("individual", "query"):
                if not self.expected.rows[name]:
                    return None
                parent = data.draw(st.sampled_from(self.expected.rows[name]))
                fields[name] = parent["identifier"]
            elif name in ("created", "handled", "cache_hit"):
                fields[name] = data.draw(TIME)
            else:
                fields[name] = data.draw(TEXT)
        return fields

    @rule(table=st.sampled_from(TABLES), data=st.data())
    def create_record(self, table, data):
        fields = self.generated_fields(table, data)
        if fields is not None:
            self.add(table, **fields)

    @rule(table=st.sampled_from(TABLES), data=st.data())
    def update_record(self, table, data):
        if not self.expected.rows[table]:
            return
        record = data.draw(st.sampled_from(self.expected.rows[table]))
        fields = self.generated_fields(table, data)
        self.edit(table, record["identifier"], fields)

    @rule(table=st.sampled_from(TABLES), data=st.data())
    def delete_record(self, table, data):
        if self.expected.rows[table]:
            record = data.draw(st.sampled_from(self.expected.rows[table]))
            self.remove(table, record)

    @rule(table=st.sampled_from(TABLES), identifier=MISSING, data=st.data())
    def missing_record(self, table, identifier, data):
        with pytest.raises(model.RecordNotFoundError):
            self.invoke(f"delete_{table}", identifier=identifier)
        fields = self.generated_fields(table, data)
        if fields is not None:
            with pytest.raises(model.RecordNotFoundError):
                self.invoke(f"update_{table}", identifier=identifier,
                            **fields)

    @rule(table=st.sampled_from(TABLES), data=st.data(), edit=st.booleans())
    def invalid_field(self, table, data, edit):
        fields = self.generated_fields(table, data)
        if fields is None or not self.expected.rows[table]:
            return
        name = data.draw(st.sampled_from(FIELDS[table]))
        numeric = name in ("created", "handled", "cache_hit",
                           "individual", "query")
        fields[name] = data.draw(BAD_INT if numeric else BAD_STR)
        action = "update" if edit else "create"
        if edit:
            fields["identifier"] = self.expected.rows[table][0]["identifier"]
        with pytest.raises(model.ValidationError):
            self.invoke(f"{action}_{table}", **fields)

    @rule(table=st.sampled_from(("query", "completion")),
          identifier=MISSING, data=st.data())
    def broken_foreign_key(self, table, identifier, data):
        fields = self.generated_fields(table, data)
        if fields is None:
            return
        key = "individual" if table == "query" else "query"
        fields[key] = identifier
        with pytest.raises(model.ValidationError):
            self.invoke(f"create_{table}", **fields)
        if self.expected.rows[table]:
            with pytest.raises(model.ValidationError):
                self.invoke(f"update_{table}",
                            identifier=self.expected.rows[table][0][
                                "identifier"], **fields)

    @rule(table=st.sampled_from(TABLES), identifier=BAD_INT)
    def invalid_identifier(self, table, identifier):
        with pytest.raises(model.ValidationError):
            self.invoke(f"delete_{table}", identifier=identifier)

    @rule(moment=TIME)
    def selection(self, moment):
        self.check_selection(moment)

    @rule(moment=BAD_INT)
    def invalid_moment(self, moment):
        if moment is not None:
            with pytest.raises(model.ValidationError):
                self.invoke("select_recent_completions", moment=moment)

    @rule()
    def missing_arguments(self):
        with pytest.raises(model.ValidationError):
            self.client.call(protocol.Operation.create_completion)

    @rule()
    def current_time(self):
        before = int(time.time())
        result = self.invoke("select_recent_completions")
        after = int(time.time())
        assert sorted(result, key=repr) in (
            sorted(self.expected.select(before), key=repr),
            sorted(self.expected.select(after), key=repr))

    def check_selection(self, moment):
        actual = self.invoke("select_recent_completions", moment=moment)
        assert sorted(actual, key=repr) == \
            sorted(self.expected.select(moment), key=repr)

    @invariant()
    def same_state(self):
        for table in TABLES:
            assert self.invoke(f"get_{PLURALS[table]}") == \
                self.expected.rows[table]
        self.check_selection(ANCHOR)

    def teardown(self):
        self.client.close()
        assert self.called == {op.name for op in protocol.Operation}


def test_rpc_state_machine(rpc_address):
    """Все вызовы модели происходят в сгенерированной машине состояний."""
    from hypothesis.stateful import run_state_machine_as_test
    RpcMachine.address = rpc_address
    run_state_machine_as_test(RpcMachine, settings=settings(
        max_examples=EXAMPLES, stateful_step_count=STEPS, deadline=None,
        derandomize=True))

PYTHON ?= python3

.PHONY: install server repl client demo demo-rpc test coverage

install:
	$(PYTHON) -m pip install -r requirements.txt

server:
	$(PYTHON) -m src.server

repl:
	$(PYTHON) -m src.repl

client:
	$(PYTHON) -m src.repl --rpc

demo:
	$(PYTHON) -m src.repl < examples.repl

demo-rpc:
	$(PYTHON) -m src.repl --rpc < examples.repl

test:
	$(PYTHON) -m pytest tests

coverage:
	$(PYTHON) -m coverage run --branch --source=src -m pytest tests/test_mbt.py
	$(PYTHON) -m coverage report -m

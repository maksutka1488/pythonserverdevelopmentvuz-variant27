PYTHON ?= python3

.PHONY: install barcode run test coverage lint

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

barcode:
	$(PYTHON) -m src.barcode data/barcode.png

run:
	$(PYTHON) -m src.server

test:
	$(PYTHON) -m pytest -q

coverage:
	$(PYTHON) -m coverage run --branch --source=src -m pytest -q tests/test_mbt.py
	$(PYTHON) -m coverage report -m

lint:
	$(PYTHON) -m pycodestyle --ignore= src tests

PYTHON ?= python3

.PHONY: install barcode

install:
	$(PYTHON) -m pip install -r requirements.txt

barcode:
	$(PYTHON) -m src.barcode data/barcode.png

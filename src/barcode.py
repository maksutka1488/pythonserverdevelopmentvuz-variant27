"""Генерирует PNG со штрихкодом EAN-13 из одной строки stdin."""

import argparse
import sys
from pathlib import Path

from barcode import EAN13
from barcode.writer import ImageWriter

PAYLOAD_LENGTH = 12
EAN_LENGTH = 13


def normalize_ean13(value):
    """Проверить цифры и дополнить 12-значный номер контрольной цифрой."""
    if (len(value) not in (PAYLOAD_LENGTH, EAN_LENGTH)
            or not value.isascii() or not value.isdecimal()):
        raise ValueError("EAN-13 должен содержать 12 или 13 цифр ASCII")
    payload = value[:PAYLOAD_LENGTH]
    checksum = -sum(
        int(digit) * (1, 3)[index % 2]
        for index, digit in enumerate(payload)
    ) % 10
    normalized = payload + str(checksum)
    if len(value) == EAN_LENGTH and value != normalized:
        raise ValueError("Неверная контрольная цифра EAN-13")
    return normalized


def write_png(value, target):
    """Сохранить штрихкод в указанный PNG и вернуть полный номер."""
    number = normalize_ean13(value)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as stream:
        EAN13(number[:PAYLOAD_LENGTH], writer=ImageWriter()).write(stream)
    return number


def main():
    """Разобрать путь, прочитать stdin и вернуть код завершения."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="путь к выходному PNG")
    options = parser.parse_args()
    try:
        print(write_png(sys.stdin.read().strip(), options.output))
    except (ValueError, OSError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()

"""Проверки генератора EAN-13."""

import subprocess
import sys

import pytest
from PIL import Image

from src.barcode import normalize_ean13

EXAMPLES = (
    ("400638133393", "4006381333931"),
    ("5901234123457", "5901234123457"),
    ("012345678901", "0123456789012"),
)


@pytest.mark.parametrize(("value", "expected"), EXAMPLES)
def test_generate_png(value, expected, tmp_path):
    """CLI принимает stdin и записывает PNG на диск."""
    target = tmp_path / "barcode.png"
    run = subprocess.run(
        [sys.executable, "-m", "src.barcode", str(target)],
        input=value + "\n", text=True, capture_output=True, check=True,
    )
    assert run.stdout.strip() == expected
    with Image.open(target) as picture:
        assert picture.format == "PNG"
        picture.verify()


@pytest.mark.parametrize("value", ["123", "4006381333932", "４" * 12])
def test_invalid_ean(value):
    """Неверная длина, контрольная цифра и не ASCII отклоняются."""
    with pytest.raises(ValueError):
        normalize_ean13(value)

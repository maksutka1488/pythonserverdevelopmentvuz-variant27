"""Фоновый запуск консольного генератора через subprocess."""

import subprocess
import sys


class Renderer:
    """В обычном режиме запускает CLI, в тестовом имитирует успех."""

    def __init__(self, test_mode, timeout):
        self.test_mode = test_mode
        self.timeout = timeout

    def __call__(self, argument, target):
        """Записать PNG и вернуть имя выходного файла."""
        if self.test_mode:
            return ""
        subprocess.run(
            [sys.executable, "-m", "src.barcode", str(target)],
            input=argument + "\n", text=True, capture_output=True,
            timeout=self.timeout, check=True,
        )
        return target.name

# Практическая работа №2 · Вариант 27

Асинхронная генерация штрихкодов EAN-13 в PNG. Этап 1: консольный
генератор на Python 3.11+.

```sh
python3 -m venv .venv
source .venv/bin/activate
make install PYTHON=python
```

Утилита принимает одну строку через stdin, путь к PNG — аргументом.
Для 12 цифр вычисляет контрольную цифру; для 13 проверяет её.
Печатает полный EAN-13. При ошибке выводит причину в stderr и завершает
работу с кодом 2. Папка назначения создаётся автоматически.

| Пример | Ввод | Ожидаемый EAN-13 |
| --- | --- | --- |
| 1 | `400638133393` | `4006381333931` |
| 2 | `5901234123457` | `5901234123457` |
| 3 | `012345678901` | `0123456789012` |

```sh
printf '%s\n' 400638133393 | python -m src.barcode data/example1.png
printf '%s\n' 5901234123457 | python -m src.barcode data/example2.png
printf '%s\n' 012345678901 | python -m src.barcode data/example3.png
```

`normalize_ean13` проверяет вход; `write_png` сохраняет изображение;
`main` связывает функции со stdin и аргументом командной строки.
Сгенерированные PNG находятся в `data/` и в Git не входят.

Проверка: `python -m pip install -r requirements-dev.txt`, затем
`python -m pytest -q`.

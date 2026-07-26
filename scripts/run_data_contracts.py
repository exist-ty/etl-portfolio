"""Fail-fast декларативные контракты над staging-слоем (Soda Core), см.
soda/checks.yml. Вызывается ДО построения витрин (Airflow: между
etl_pipeline и refresh_marts/load_to_clickhouse/build_features/generate_messages).

Exit-код 0 только при отсутствии FAIL и ошибок сканирования. WARN
(известное, принятое свойство синтетических данных — заказы раньше
регистрации, см. soda/checks.yml) печатается в лог, но не блокирует
пайплайн: если бы WARN был fail-fast, задача падала бы при каждом прогоне,
а это не то же самое, что "данные сломаны".
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

# cp1252 (дефолтный stdout на Windows) не кодирует кириллицу в сообщениях
# ниже — та же категория бага, что уже ловилась в compare_models.py.
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    # Полный путь к soda рядом с текущим интерпретатором, а не голое "soda":
    # cwd ниже — PROJECT_ROOT, где есть каталог soda/ (configuration.yml,
    # checks.yml) — os.execvpe находит его раньше PATH и падает с
    # "Permission denied: 'soda'" (нельзя исполнить каталог).
    soda_bin = Path(sys.executable).parent / (
        "soda.exe" if sys.platform == "win32" else "soda"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        results_path = Path(tmp_dir) / "soda_scan_results.json"
        result = subprocess.run(
            [
                str(soda_bin),
                "scan",
                "-d",
                "etl_portfolio",
                "-c",
                str(PROJECT_ROOT / "soda" / "configuration.yml"),
                "-srf",
                str(results_path),
                str(PROJECT_ROOT / "soda" / "checks.yml"),
            ],
            cwd=PROJECT_ROOT,
        )
        # Soda CLI сам возвращает ненулевой exit-код при WARN, не только при
        # FAIL — поэтому решение о fail-fast принимается по самому JSON, а не
        # по коду возврата процесса.
        results = json.loads(results_path.read_text(encoding="utf-8"))

    has_failures = results.get("hasFailures", False)
    has_errors = results.get("hasErrors", False)
    has_warnings = results.get("hasWarnings", False)

    if has_warnings and not (has_failures or has_errors):
        print(
            "\nКонтракты: есть WARN, но пайплайн не блокируется "
            "(известное свойство данных, см. soda/checks.yml)."
        )

    if has_failures or has_errors:
        print("\nКонтракты данных провалены — витрины строиться не будут.")
        return 1

    print("\nКонтракты данных пройдены.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

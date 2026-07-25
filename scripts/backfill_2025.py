"""Настоящий backfill: прогоняет run_incremental() по дням за весь 2025 год —
демонстрация catchup, а не абстрактное обещание в роадмапе. Датасет заморожен
(order_date строго в границах 2025 года, см. README) — это исторический
backfill против статичного источника, а не живой поток, и это не выдаётся
за что-то другое."""
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.pipeline import bootstrap_dimensions, run_incremental

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

START = date(2025, 1, 1)
END = date(2026, 1, 1)  # исключительная граница — последнее окно [2025-12-31, 2026-01-01)


def run() -> None:
    logger.info("Bootstrapping dimensions (один раз, полная перезаливка)...")
    bootstrap_dimensions()

    total_days = (END - START).days
    day = START
    total_loaded = 0
    days_done = 0

    while day < END:
        next_day = day + timedelta(days=1)
        result = run_incremental(day, next_day)
        total_loaded += result["rows_loaded"]
        days_done += 1
        if days_done % 30 == 0 or days_done == total_days:
            logger.info("  %d/%d дней, %d заказов загружено", days_done, total_days, total_loaded)
        day = next_day

    logger.info("Backfill завершён: %d дней, %d заказов (upsert)", days_done, total_loaded)


if __name__ == "__main__":
    run()

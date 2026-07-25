"""Проверяет то самое свойство, ради которого затевался watermark-инкремент
(см. README, "Инкрементальная загрузка и backfill"): повторный прогон одного
и того же окна не создаёт дублей и не трогает соседние окна — а не просто
заявляется в docstring. Требует живую БД (etl_portfolio) — CI её пока не
поднимает ("CI с живой БД" в роадмапе хаба — отдельный, ещё не сделанный
пункт), поэтому тест пропускается, если подключиться не удалось, а не падает
непонятной сетевой ошибкой."""
from datetime import date

import pytest
from sqlalchemy import text

from src.etl.db import get_engine
from src.etl.pipeline import bootstrap_dimensions, run_incremental


@pytest.fixture(scope="module")
def engine():
    try:
        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"нет живого Postgres для теста инкремента: {exc}")
    return eng


def _order_count(engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM stg_orders")).scalar()


def test_rerun_same_window_is_idempotent(engine):
    bootstrap_dimensions()
    window = (date(2025, 1, 1), date(2025, 1, 2))

    first = run_incremental(*window)
    count_after_first = _order_count(engine)

    second = run_incremental(*window)
    count_after_second = _order_count(engine)

    assert first["rows_loaded"] == second["rows_loaded"]
    assert count_after_first == count_after_second


def test_backfilling_a_second_window_keeps_the_first(engine):
    bootstrap_dimensions()

    run_incremental(date(2025, 1, 1), date(2025, 1, 2))
    count_after_day_1 = _order_count(engine)

    run_incremental(date(2025, 1, 2), date(2025, 1, 3))
    count_after_day_2 = _order_count(engine)

    # День 2 не должен стирать/перезаписывать день 1 — только upsert поверх.
    assert count_after_day_2 >= count_after_day_1


def test_load_log_records_one_row_per_window_not_per_attempt(engine):
    bootstrap_dimensions()
    window = (date(2025, 3, 1), date(2025, 3, 2))

    run_incremental(*window)
    run_incremental(*window)  # тот же интервал, второй раз

    with engine.connect() as conn:
        n = conn.execute(
            text(
                "SELECT count(*) FROM etl_load_log "
                "WHERE data_interval_start = :start AND data_interval_end = :end"
            ),
            {"start": window[0], "end": window[1]},
        ).scalar()
    assert n == 1

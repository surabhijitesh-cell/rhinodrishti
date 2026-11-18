"""Brief periods follow IST days. Pure logic: no database, no AI calls."""
import asyncio

from brief_periods import fortnight_range, month_range, period_dates
from utils.pdf_render import render_pdf_off_loop


def test_month_starts_and_ends_at_ist_midnight():
    assert month_range(2026, 11) == ("2026-10-31T18:30:00+00:00", "2026-11-30T18:30:00+00:00")
    assert month_range(2026, 12)[1] == "2026-12-31T18:30:00+00:00"


def test_fortnights_split_on_the_16th_ist():
    assert fortnight_range(2026, 11, 1) == (
        "2026-10-31T18:30:00+00:00", "2026-11-15T18:30:00+00:00", "1-15 November 2026")
    assert fortnight_range(2026, 2, 2) == (
        "2026-02-15T18:30:00+00:00", "2026-02-28T18:30:00+00:00", "16-28 February 2026")


def test_period_dates_have_no_extra_day():
    assert period_dates(*month_range(2026, 11)) == ("2026-11-01", "2026-11-30")
    assert period_dates(*fortnight_range(2026, 12, 2)[:2]) == ("2026-12-16", "2026-12-31")


def test_a_midnight_ist_item_falls_in_the_new_period():
    start, _ = month_range(2026, 11)
    assert "2026-10-31T19:00:00Z" >= start
    assert "2026-10-31T18:00:00+00:00" < start


def test_pdf_render_helper_returns_the_result():
    assert asyncio.run(render_pdf_off_loop(lambda a, b=0: a + b, 2, b=3)) == 5


def test_pdf_text_prints_rupee_as_rs_and_other_unknowns_as_question_marks():
    assert "₹14,327 Cr → x".encode("latin-1", "pdf_safe").decode("latin-1") == "Rs 14,327 Cr ? x"

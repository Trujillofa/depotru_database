"""Synthetic executable specification of the D4 SELECT, not an ERP adapter."""

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
QUERY = ROOT / "docs/drafts/wcx-sales-metrics.sql.template"


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE case_facts (
            source TEXT, case_id INTEGER, customer_key TEXT, link_state TEXT,
            opened_epoch INTEGER, window_end_epoch INTEGER,
            first_response_seconds INTEGER, declared_outcome TEXT,
            loss_reason TEXT, PRIMARY KEY (source, case_id)
        );
        CREATE TABLE invoice_facts (
            invoice_key TEXT PRIMARY KEY, customer_key TEXT,
            sold_epoch INTEGER, net_cop NUMERIC, sale_eligible INTEGER
        );
        """
    )
    yield conn
    conn.close()


def case(
    db,
    case_id=1,
    source="synthetic",
    customer="A",
    link="approved",
    opened=100,
    end=200,
    response=60,
    outcome=None,
    reason=None,
):
    db.execute(
        "INSERT INTO case_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (source, case_id, customer, link, opened, end, response, outcome, reason),
    )


def invoice(db, key="I1", customer="A", sold=150, net=100, eligible=1):
    db.execute(
        "INSERT INTO invoice_facts VALUES (?, ?, ?, ?, ?)",
        (key, customer, sold, net, eligible),
    )


def report(db, observed=300, cohort_start=0, cohort_end=1000):
    sql = (
        QUERY.read_text()
        .replace("%(observed_until_epoch)s", ":observed")
        .replace("%(cohort_start_epoch)s", ":cohort_start")
        .replace("%(cohort_end_epoch)s", ":cohort_end")
    )
    params = dict(observed=observed, cohort_start=cohort_start, cohort_end=cohort_end)
    return [dict(row) for row in db.execute(sql, params)]


def totals(rows):
    columns = ("cases", "eligible_cases", "converted_cases", "net_cop")
    return {key: sum(row[key] for row in rows) for key in columns}


def test_one_case_multiple_invoices_counts_case_once(db):
    case(db)
    invoice(db)
    invoice(db, key="I2", net=50)
    assert totals(report(db)) == dict(
        cases=1, eligible_cases=1, converted_cases=1, net_cop=150
    )


def test_invoice_shared_between_cases_is_ambiguous_not_allocated(db):
    case(db)
    case(db, case_id=2)
    invoice(db)
    rows = report(db)
    assert totals(rows)["converted_cases"] == 0
    assert totals(rows)["eligible_cases"] == 0
    assert {row["outcome"] for row in rows} == {"ambiguous_attribution"}


def test_case_source_is_part_of_identity(db):
    case(db)
    case(db, source="other", customer="B")
    invoice(db)
    invoice(db, key="I2", customer="B")
    assert totals(report(db))["converted_cases"] == 2


@pytest.mark.parametrize("link", ["unreviewed", "ambiguous", "rejected"])
def test_unapproved_links_never_convert(db, link):
    case(db, link=link)
    invoice(db)
    assert totals(report(db))["eligible_cases"] == 0
    assert totals(report(db))["converted_cases"] == 0


def test_null_customer_never_matches(db):
    case(db, customer=None)
    invoice(db, customer=None)
    assert totals(report(db))["eligible_cases"] == 0


def test_half_open_window_excludes_before_and_upper_boundary(db):
    case(db)
    invoice(db, sold=99)
    invoice(db, key="I2", sold=200)
    assert totals(report(db))["converted_cases"] == 0
    invoice(db, key="I3", sold=100)
    assert totals(report(db))["converted_cases"] == 1


def test_censored_case_not_in_denominator_even_with_sale(db):
    case(db)
    invoice(db)
    rows = report(db, observed=199)
    assert totals(rows)["eligible_cases"] == 0
    assert rows[0]["outcome"] == "censored"


def test_non_sale_documents_do_not_create_conversion(db):
    case(db)
    invoice(db, eligible=0)
    assert totals(report(db))["converted_cases"] == 0


def test_fully_returned_invoice_not_net_conversion(db):
    case(db)
    invoice(db, net=0)
    assert totals(report(db))["converted_cases"] == 0
    assert report(db)[0]["outcome"] == "net_nonpositive"


def test_negative_returns_are_not_discarded(db):
    case(db)
    invoice(db, net=-25)
    assert totals(report(db))["net_cop"] == -25
    assert totals(report(db))["converted_cases"] == 0


def test_no_sale_is_not_automatically_a_lost_sale(db):
    case(db)
    rows = report(db)
    assert rows[0]["outcome"] == "no_observed_sale"
    assert rows[0]["loss_reason"] == "not_applicable"


def test_declared_loss_preserves_only_approved_taxonomy_code(db):
    case(db, outcome="lost", reason="price")
    assert report(db)[0]["outcome"] == "declared_lost"
    assert report(db)[0]["loss_reason"] == "price"


def test_unknown_loss_reason_and_response_remain_unknown(db):
    case(db, outcome="lost", reason=None, response=None)
    row = report(db)[0]
    assert row["loss_reason"] == "unknown"
    assert row["response_band"] == "unknown"


def test_sale_and_declared_loss_are_conflict_not_clean_conversion(db):
    case(db, outcome="lost", reason="price")
    invoice(db)
    row = report(db)[0]
    assert row["outcome"] == "outcome_conflict"
    assert row["converted_cases"] == 0
    assert row["eligible_cases"] == 0


@pytest.mark.parametrize("observed", [220, 300])
def test_halo_competes_but_is_not_published(db, observed):
    case(db)
    case(db, case_id=2, opened=180, end=280)
    invoice(db, sold=190)
    rows = report(db, observed=observed, cohort_start=100, cohort_end=180)
    assert totals(rows)["cases"] == 1
    assert rows[0]["outcome"] == "ambiguous_attribution"


@pytest.mark.parametrize("link,end", [("unreviewed", 200), ("approved", 400)])
def test_loss_reason_survives_coverage_exclusions(db, link, end):
    case(db, link=link, end=end, outcome="lost", reason="stock")
    row = report(db)[0]
    assert row["loss_reason"] == "stock"
    assert row["declared_lost_cases"] == 1
    assert row["eligible_cases"] == 0


def test_conflict_retains_declared_loss_reason(db):
    case(db, outcome="lost", reason="price")
    invoice(db)
    row = report(db)[0]
    assert row["loss_reason"] == "price"
    assert row["declared_lost_cases"] == 1


def test_scenario_uses_case_total_not_any_positive_invoice(db):
    case(db)
    invoice(db, net=100)
    invoice(db, key="I2", net=-100)
    assert report(db)[0]["outcome"] == "net_nonpositive"


def test_empty_input_has_no_fabricated_rate(db):
    assert report(db) == []


def test_query_is_a_single_read_only_statement(db):
    sql = QUERY.read_text()

    # SQLite's read-only authorizer rejects any runtime write in the SELECT.
    def authorize(action, arg1, arg2, database, trigger):
        allowed = (
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_RECURSIVE,
        )
        return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

    db.set_authorizer(authorize)
    assert report(db) == []
    assert "%(observed_until_epoch)s" in sql

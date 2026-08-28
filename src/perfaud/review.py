"""Shared names, keys, and explanations for audit review artifacts.

This module contains presentation names that must stay aligned across the
generated XLSX workbook, HTML report, bundle README, validators, and tests.
Keeping the names here avoids drift when the review model is renamed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

import polars as pl

from perfaud import rendering
from perfaud.comparison import findings
from perfaud.specification import (
    PORTFOLIO_COMPARISON_LEVEL,
    SECURITY_COMPARISON_LEVEL,
)

HTML_REPORT_ARTIFACT: Final[str] = "html_report"
REVIEW_WORKBOOK_ARTIFACT: Final[str] = "review_workbook"
PORTFOLIO_AUDIT_FILE_STEM: Final[str] = "portfolio_audit"
SECURITY_AUDIT_FILE_STEM: Final[str] = "security_audit"

PERFORMANCE_DIFFERENCES_ARTIFACT: Final[str] = "performance_differences"
EXECUTIVE_SUMMARY_ARTIFACT: Final[str] = "executive_summary"
PERFORMANCE_DIFFERENCE_CAUSES_ARTIFACT: Final[str] = "performance_difference_causes"
CAUSE_LINEAGE_ARTIFACT: Final[str] = "cause_lineage"
DATA_ISSUES_ARTIFACT: Final[str] = "data_issues"
SOURCE_DETAIL_ARTIFACT: Final[str] = "raw_audit_trail"
TRANSACTION_MATCHING_DIAGNOSTICS_ARTIFACT: Final[str] = (
    "transaction_matching_diagnostics"
)
RECONSTRUCTION_SUMMARY_ARTIFACT: Final[str] = "reconstruction_summary"
RETURN_RECONSTRUCTION_CHECKS_ARTIFACT: Final[str] = "return_reconstruction_checks"
SECURITY_RETURN_RECONSTRUCTION_CHECKS_ARTIFACT: Final[str] = (
    "security_return_reconstruction_checks"
)

PERFORMANCE_DIFFERENCES_SHEET: Final[str] = "Performance Differences"
EXECUTIVE_SUMMARY_SHEET: Final[str] = "Executive Summary"
RECONSTRUCTION_SUMMARY_SHEET: Final[str] = "Reconstruction Summary"
RETURN_RECONSTRUCTION_CHECKS_SHEET: Final[str] = "Return Reconstruction Checks"
SECURITY_RETURN_RECONSTRUCTION_CHECKS_SHEET: Final[str] = "Security Return Checks"
PERFORMANCE_DIFFERENCE_CAUSES_SHEET: Final[str] = "Performance Difference Causes"
DATA_ISSUES_SHEET: Final[str] = "Data Issues"
TRANSACTION_MATCHING_DIAGNOSTICS_SHEET: Final[str] = (
    "Transaction Match Diagnostics"
)
SOURCE_DETAIL_SHEET: Final[str] = "Source Detail"
REVIEW_ORDER_SECTION: Final[str] = "Review Order"


def audit_file_stem(comparison_level: str) -> str:
    """Return the audit report filename stem for a comparison level.

    Args:
        comparison_level: Portfolio or security comparison level.

    Returns:
        ``portfolio_audit`` or ``security_audit``.

    Raises:
        ValueError: If the comparison level is unsupported.
    """
    if comparison_level == PORTFOLIO_COMPARISON_LEVEL:
        return PORTFOLIO_AUDIT_FILE_STEM
    if comparison_level == SECURITY_COMPARISON_LEVEL:
        return SECURITY_AUDIT_FILE_STEM
    raise ValueError(f"Unsupported comparison level: {comparison_level!r}")


def html_report_file_name(comparison_level: str) -> str:
    """Return the HTML audit filename for a comparison level."""
    return f"{audit_file_stem(comparison_level)}.html"


def review_workbook_file_name(comparison_level: str) -> str:
    """Return the XLSX audit filename for a comparison level."""
    return f"{audit_file_stem(comparison_level)}.xlsx"

PRIMARY_REVIEW_SHEETS: Final[tuple[str, ...]] = (
    EXECUTIVE_SUMMARY_SHEET,
    PERFORMANCE_DIFFERENCES_SHEET,
)
SHARED_REVIEW_SHEETS: Final[tuple[str, ...]] = (
    PERFORMANCE_DIFFERENCE_CAUSES_SHEET,
    DATA_ISSUES_SHEET,
)
EXPECTED_REVIEW_SHEETS: Final[tuple[str, ...]] = (
    *PRIMARY_REVIEW_SHEETS,
    *SHARED_REVIEW_SHEETS,
)

REVIEW_KEY: Final[str] = "review_key"

_TERM_TOOLTIPS: Final[dict[str, str]] = {
    "Total Quantity": (
        "Total portfolios or periods evaluated, including those with no reported "
        "performance difference."
    ),
    "No Performance Differences": (
        "Count with no reported performance difference beyond the configured "
        "comparison tolerance."
    ),
    "Fully Explained": (
        "The reported performance difference is accounted for by supported, "
        "quantified causes within the configured tolerance."
    ),
    "Fully Explained Differences": (
        "Count of reported performance differences accounted for by supported, "
        "quantified causes within the configured tolerance."
    ),
    "Partly Explained": (
        "Supported, quantified causes account for part, but not all, of the "
        "reported performance difference."
    ),
    "Partly Explained Differences": (
        "Count of reported performance differences for which supported, quantified "
        "causes account for part, but not all, of the difference."
    ),
    "Unexplained": (
        "perfaud did not quantify a supported cause for the reported performance "
        "difference."
    ),
    "Unexplained Differences": (
        "Count of reported performance differences for which perfaud did not "
        "quantify a supported cause."
    ),
    "Missing YAML Specifications": (
        "perfaud cannot finalize the explanation because required YAML treatment "
        "is missing."
    ),
    "Setup Incomplete": (
        "Count of reported performance differences that cannot be finalized because "
        "required YAML treatment is missing."
    ),
    "Explained Cause": (
        "A supported, quantified cause included in the Explained Difference."
    ),
    "Possible Cause": (
        "Relevant evidence that may help explain the difference but is not counted "
        "in the Explained Difference."
    ),
    "Supporting Evidence": (
        "Evidence supporting an explanation without being independently counted as "
        "another cause."
    ),
    "Review Context": (
        "Relevant changed data shown for review but not counted in the Explained "
        "Difference."
    ),
    "Issue Type": "Cross-reference consistency check reported by Audit.",
    "Quantity": "Number of Data Issues of this type.",
}
_TOOLTIP_VALUE_COLUMNS: Final[frozenset[str]] = frozenset(
    {"input_role", "review_status", "row_type"}
)


def period_key(row: Mapping[str, object]) -> tuple[object, object, object]:
    """Return the portfolio-period grouping key for a report row."""
    return (
        row[findings.PORTFOLIO_ID],
        row[findings.FROM_DATE],
        row[findings.THRU_DATE],
    )


def period_review_key(row: Mapping[str, object]) -> str:
    """Return a stable text key for joining period-level review artifacts."""
    return "::".join(
        [
            rendering.format_value(row.get(findings.PORTFOLIO_ID)),
            rendering.format_value(row.get(findings.FROM_DATE)),
            rendering.format_value(row.get(findings.THRU_DATE)),
        ]
    )


def with_period_review_key(table: pl.DataFrame) -> pl.DataFrame:
    """Add a review key when the table contains portfolio-period columns."""
    period_columns = {
        findings.PORTFOLIO_ID,
        findings.FROM_DATE,
        findings.THRU_DATE,
    }
    if REVIEW_KEY in table.columns or not period_columns.issubset(table.columns):
        return table
    table_with_key = table.with_columns(
        pl.concat_str(
            [
                pl.col(findings.PORTFOLIO_ID).cast(pl.String),
                pl.col(findings.FROM_DATE).cast(pl.String),
                pl.col(findings.THRU_DATE).cast(pl.String),
            ],
            separator="::",
        ).alias(REVIEW_KEY)
    )
    return table_with_key.select(
        [REVIEW_KEY, *[column for column in table.columns if column != REVIEW_KEY]]
    )


def with_security_review_key(table: pl.DataFrame) -> pl.DataFrame:
    """Add a review key when the table contains security-period columns."""
    security_columns = {
        findings.PORTFOLIO_ID,
        findings.FROM_DATE,
        findings.THRU_DATE,
        findings.SECURITY_ID,
    }
    if REVIEW_KEY in table.columns or not security_columns.issubset(table.columns):
        return table
    table_with_key = table.with_columns(
        pl.concat_str(
            [
                pl.col(findings.PORTFOLIO_ID).cast(pl.String),
                pl.col(findings.FROM_DATE).cast(pl.String),
                pl.col(findings.THRU_DATE).cast(pl.String),
                pl.col(findings.SECURITY_ID).cast(pl.String),
            ],
            separator="::",
        ).alias(REVIEW_KEY)
    )
    return table_with_key.select(
        [REVIEW_KEY, *[column for column in table.columns if column != REVIEW_KEY]]
    )


def row_review_key(row: Mapping[str, object]) -> str:
    """Return an existing or derived review key for one report row."""
    if _has_text(row.get(REVIEW_KEY)):
        return rendering.format_value(row.get(REVIEW_KEY))
    period_columns = {
        findings.PORTFOLIO_ID,
        findings.FROM_DATE,
        findings.THRU_DATE,
    }
    if not period_columns.issubset(row.keys()):
        return ""
    return period_review_key(row)


def audit_term_tooltip(term: object) -> str:
    """Return the concise Audit definition for a controlled review term."""
    normalized_term = " ".join(str(term).split())
    return _TERM_TOOLTIPS.get(normalized_term, "")


def explanation_status_tooltip() -> str:
    """Return the compact glossary for performance review statuses."""
    return " ".join(
        (
            f"Fully Explained: {audit_term_tooltip('Fully Explained')}",
            f"Partly Explained: {audit_term_tooltip('Partly Explained')}",
            f"Unexplained: {audit_term_tooltip('Unexplained')}",
            "Setup Incomplete: "
            f"{audit_term_tooltip('Missing YAML Specifications')}",
        )
    )


def audit_value_tooltip(column: str, value: object) -> str:
    """Return a curated tooltip for a controlled Audit table value."""
    if column not in _TOOLTIP_VALUE_COLUMNS:
        return ""
    return audit_term_tooltip(value)


def _has_text(value: object) -> bool:
    """Return whether a value has non-blank text."""
    return isinstance(value, str) and bool(value.strip())

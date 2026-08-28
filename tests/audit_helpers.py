"""Reusable helpers for focused audit tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
import zipfile

import polars as pl
import yaml

_SOURCE_COLUMNS: dict[str, dict[str, tuple[str, ...]]] = {
    "portfolio_performance": {
        "portfolio_id": ("PORTFOLIO_ID", "PORTFOLIO_CODE", "PORT"),
        "from_date": ("FROM_DATE",),
        "thru_date": ("THRU_DATE",),
        "portfolio_return": ("PORT_RETURN", "RETURN", "RET"),
        "base_currency": ("BASE_CURRENCY",),
    },
    "security_performance": {
        "portfolio_id": ("PORTFOLIO_ID", "PORTFOLIO_CODE", "PORT"),
        "security_id": ("SECURITY_ID", "SEC"),
        "from_date": ("FROM_DATE",),
        "thru_date": ("THRU_DATE",),
        "security_return": ("SEC_RETURN", "RETURN", "RET"),
    },
    "holdings": {
        "portfolio_id": ("PORTFOLIO_ID", "PORTFOLIO_CODE", "PORT"),
        "security_id": ("SECURITY_ID", "SEC"),
        "holding_date": ("HOLDING_DATE", "POSITION_DATE"),
        "quantity": ("QUANTITY", "QTY"),
        "price": ("PRICE",),
        "market_value": ("MKT_VAL", "MV"),
        "base_market_value": ("BASE_MKT_VAL", "BASE_MV"),
        "cost": ("COST",),
        "accrued": ("ACCRUED",),
        "base_accrued": ("BASE_ACCRUED_INCOME", "BASE_ACCRUED"),
        "currency": ("CURRENCY",),
        "base_currency": ("BASE_CURRENCY",),
    },
    "transactions": {
        "portfolio_id": ("PORTFOLIO_ID", "PORTFOLIO_CODE", "PORT"),
        "security_id": ("SECURITY_ID", "SEC"),
        "transaction_id": ("TRANSACTION_ID",),
        "transaction_date": ("TRANSACTION_DATE", "TRADE_DATE"),
        "settlement_date": ("SETTLEMENT_DATE", "SETTLE_DATE"),
        "transaction_code": ("TRANSACTION_CODE", "TRAN"),
        "original_cost_date": ("ORIGINAL_COST_DATE", "ORIG_COST_DATE"),
        "transaction_security_type": ("SECURITY_TYPE", "SEC_TYPE"),
        "source_destination_type": ("SOURCE_DESTINATION_TYPE", "SRC_DEST_TYPE"),
        "source_destination_symbol": (
            "SOURCE_DESTINATION_SYMBOL",
            "SRC_DEST_SYMBOL",
        ),
        "special_security_type": ("SPECIAL_SECURITY_TYPE", "SPECIAL_SEC_TYPE"),
        "special_security_symbol": (
            "SPECIAL_SECURITY_SYMBOL",
            "SPECIAL_SEC_SYMBOL",
        ),
        "transaction_category": (
            "TRANSACTION_CATEGORY",
            "TXN_CATEGORY",
            "ACTIVITY_CATEGORY",
        ),
        "cash_flow_sign": ("CASH_FLOW_SIGN",),
        "performance_flow_sign": ("PERFORMANCE_FLOW_SIGN",),
        "quantity": ("QUANTITY", "QTY"),
        "price": ("PRICE",),
        "amount": ("AMOUNT",),
        "base_amount": ("BASE_AMOUNT",),
        "commission": ("COMMISSION",),
        "currency": ("CURRENCY",),
        "base_currency": ("BASE_CURRENCY",),
        "broker": ("BROKER",),
        "original_cost": ("ORIGINAL_COST", "ORIG_COST"),
    },
    "splits": {
        "security_id": ("SECURITY_ID", "SEC"),
        "security_name": ("SECURITY_NAME",),
        "ticker": ("TICKER",),
        "split_date": ("SPLIT_DATE",),
        "split_factor": ("SPLIT_FACTOR",),
    },
    "security_master": {
        "security_id": ("SECURITY_ID", "SEC"),
        "security_name": ("SECURITY_NAME",),
        "ticker": ("TICKER",),
        "security_type": ("SECURITY_TYPE", "SEC_TYPE"),
        "asset_class_code": ("ASSET_CLASS_CODE",),
        "sector_code": ("SECTOR_CODE",),
        "sector": ("SECTOR", "SECTOR_NAME"),
        "country_code": ("COUNTRY_CODE",),
        "country": ("COUNTRY", "COUNTRY_NAME"),
        "currency": ("CURRENCY", "CURRENCY_CODE"),
    },
}


def extract_audit_support(
    paths: dict[str, Path],
    output_directory: Path,
) -> dict[str, Path]:
    """Extract an audit-support archive and expose its artifact paths."""
    with zipfile.ZipFile(paths["audit_support"]) as archive:
        archive.extractall(output_directory)
        manifest: dict[str, Any] = json.loads(
            archive.read("supporting_files/manifest.json").decode("utf-8")
        )
    for name, relative_path in manifest["artifacts"].items():
        paths.setdefault(name, output_directory / relative_path)
    return paths


def write_audit_test_yaml(path: Path, contents: object) -> None:
    """Write synthetic YAML with mappings inferred from test-owned CSV headers."""
    if not isinstance(contents, dict):
        path.write_text(yaml.safe_dump(contents), encoding="utf-8")
        return
    configuration = copy.deepcopy(contents)
    snapshots = configuration.get("snapshots")
    files = configuration.get("files")
    if not isinstance(snapshots, dict) or not isinstance(files, dict):
        path.write_text(yaml.safe_dump(configuration), encoding="utf-8")
        return

    schema_files: dict[str, dict[str, dict[str, str]]] = {}
    for dataset_name, file_definition in files.items():
        candidates_by_field = _SOURCE_COLUMNS.get(str(dataset_name))
        if candidates_by_field is None:
            continue
        if isinstance(file_definition, str):
            relative_file_path = Path(file_definition)
        elif isinstance(file_definition, dict) and isinstance(
            file_definition.get("path"), str
        ):
            relative_file_path = Path(file_definition["path"])
        else:
            continue
        available_columns: set[str] = set()
        for snapshot in snapshots.values():
            if not isinstance(snapshot, dict) or not isinstance(
                snapshot.get("path"), str
            ):
                continue
            source_path = path.parent / snapshot["path"] / relative_file_path
            if source_path.exists():
                available_columns.update(pl.read_csv(source_path, n_rows=0).columns)
        mappings: dict[str, str] = {}
        for normalized_field, candidates in candidates_by_field.items():
            if normalized_field in available_columns:
                mappings[normalized_field] = normalized_field
                continue
            source_name = next(
                (candidate for candidate in candidates if candidate in available_columns),
                None,
            )
            if source_name is not None:
                mappings[normalized_field] = source_name
        if mappings:
            schema_files[str(dataset_name)] = {"columns": mappings}

    if schema_files:
        schema_name = "source_column_mappings.yaml"
        (path.parent / schema_name).write_text(
            yaml.safe_dump({"files": schema_files}, sort_keys=False),
            encoding="utf-8",
        )
        for snapshot in snapshots.values():
            if isinstance(snapshot, dict):
                snapshot.setdefault("schema", schema_name)
    path.write_text(yaml.safe_dump(configuration), encoding="utf-8")

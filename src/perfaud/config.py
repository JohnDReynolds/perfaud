"""Load, validate, and resolve the canonical perfaud configuration."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, TypeAlias, cast

import yaml

# Project imports
from perfaud.errors import PerfaudError
if TYPE_CHECKING:
    from perfaud.specification import Specification

__all__ = [
    "Configuration",
    "Settings",
    "load_config",
    "settings",
    "validate_config",
]

_REPORTS: Final[frozenset[str]] = frozenset({"portfolio", "security"})
_OUTPUTS: Final[frozenset[str]] = frozenset({"html", "xlsx"})
_BOOLEAN_SETTINGS: Final[tuple[str, ...]] = (
    "exclude_suppressed",
    "reconstruction_diagnostics",
    "require_causal_attribution",
)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Load YAML while rejecting duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    """Construct one mapping and reject duplicate keys."""
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate YAML key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class Configuration:
    """Parsed perfaud configuration loaded exactly once for a workspace run.

    Attributes:
        path: Resolved ``perfaud.yaml`` path.
        values: Validated root YAML mapping.
    """

    path: Path
    values: dict[str, Any]


@dataclass(frozen=True)
class Settings:
    """Resolved operational choices for one perfaud run.

    Attributes:
        reports: Report levels to generate in deterministic order.
        outputs: Presentation formats to generate in deterministic order.
        exclude_suppressed: Whether suppressed findings are omitted.
        reconstruction_diagnostics: Whether detailed diagnostics are included.
        require_causal_attribution: Whether supported causal setup is mandatory.
    """

    reports: tuple[str, ...]
    outputs: tuple[str, ...]
    exclude_suppressed: bool
    reconstruction_diagnostics: bool
    require_causal_attribution: bool


ConfigLike: TypeAlias = Configuration | str | Path
_ACTIVE_CONFIGURATION: ContextVar[Configuration | None] = ContextVar(
    "perfaud_active_configuration",
    default=None,
)


def load_config(path: str | Path) -> Configuration:
    """Load and structurally validate one perfaud YAML file.

    Args:
        path: Configuration path.

    Returns:
        Parsed configuration suitable for every downstream consumer.

    Raises:
        PerfaudError: If the file is missing, malformed, or has invalid run settings.
    """
    config_path = Path(path).expanduser().resolve()
    active = _ACTIVE_CONFIGURATION.get()
    if active is not None and active.path == config_path:
        return active
    if not config_path.is_file():
        raise PerfaudError(f"Configuration file does not exist: {config_path}")
    try:
        loaded: object = yaml.load(
            config_path.read_text(encoding="utf-8"),
            Loader=_UniqueKeySafeLoader,
        )
    except (OSError, yaml.YAMLError) as error:
        raise PerfaudError(f"Invalid YAML in {config_path}: {error}") from error
    if not isinstance(loaded, dict) or not all(
        isinstance(key, str) for key in loaded
    ):
        raise PerfaudError(f"{config_path} must contain a string-keyed YAML mapping.")
    values = cast(dict[str, Any], loaded)
    return Configuration(path=config_path, values=values)


@contextmanager
def active_configuration(configuration: Configuration) -> Iterator[None]:
    """Make one loaded configuration available to every run-scoped consumer."""
    token = _ACTIVE_CONFIGURATION.set(configuration)
    try:
        yield
    finally:
        _ACTIVE_CONFIGURATION.reset(token)


def settings(configuration: Configuration) -> Settings:
    """Validate and return the operational settings for a configuration."""
    reports = _choice_list(configuration, "reports", _REPORTS)
    outputs = _choice_list(configuration, "outputs", _OUTPUTS)
    boolean_values: dict[str, bool] = {}
    for name in _BOOLEAN_SETTINGS:
        value = configuration.values.get(name, False)
        if not isinstance(value, bool):
            raise PerfaudError(f"{name} must be true or false.")
        boolean_values[name] = value
    return Settings(
        reports=reports,
        outputs=outputs,
        exclude_suppressed=boolean_values["exclude_suppressed"],
        reconstruction_diagnostics=boolean_values["reconstruction_diagnostics"],
        require_causal_attribution=boolean_values["require_causal_attribution"],
    )


def _choice_list(
    configuration: Configuration,
    name: str,
    allowed: frozenset[str],
) -> tuple[str, ...]:
    """Return a required, unique list of supported string choices."""
    value = configuration.values.get(name)
    if not isinstance(value, list) or not value:
        raise PerfaudError(f"{name} must be a non-empty list.")
    if not all(isinstance(item, str) for item in value):
        raise PerfaudError(f"{name} must contain only strings.")
    choices = cast(list[str], value)
    unsupported = sorted(set(choices) - allowed)
    if unsupported:
        raise PerfaudError(
            f"{name} contains unsupported values: {', '.join(unsupported)}."
        )
    if len(set(choices)) != len(choices):
        raise PerfaudError(f"{name} must not contain duplicate values.")
    return tuple(choices)


def source_file_definition(
    values: Mapping[str, object],
    file_name: str,
    error_message: Callable[[str], str],
) -> Mapping[str, object]:
    """Return one validated nested ``files`` definition."""
    raw_files = values.get("files", {})
    if not isinstance(raw_files, Mapping):
        raise PerfaudError(error_message("files must be a mapping."))
    raw_definition = raw_files.get(file_name, {})
    if isinstance(raw_definition, str):
        return {"path": raw_definition}
    if not isinstance(raw_definition, Mapping):
        raise PerfaudError(
            error_message(f"files.{file_name} must be a string or mapping.")
        )
    return cast(Mapping[str, object], raw_definition)


def source_file_columns(
    values: Mapping[str, object],
    file_name: str,
    error_message: Callable[[str], str],
) -> Mapping[str, object]:
    """Return one validated source-column mapping."""
    definition = source_file_definition(values, file_name, error_message)
    raw_columns = definition.get("columns", {})
    if not isinstance(raw_columns, Mapping):
        raise PerfaudError(
            error_message(f"files.{file_name}.columns must be a mapping.")
        )
    return cast(Mapping[str, object], raw_columns)


def validate_config(
    configuration: ConfigLike,
    *,
    require_complete_yaml_setup: bool = True,
) -> dict[str, object]:
    """Validate one comparison YAML file and return a compact summary.

    Args:
        configuration: Loaded configuration or path to ``perfaud.yaml``.
        require_complete_yaml_setup: Whether to reject changed source-data
            fields that lack additive, evidence-only, or suppression YAML.

    Returns:
        Summary fields for the resolved snapshots, configured datasets, and
        transaction files checked.

    Raises:
        PerfaudError: If the comparison specification, configured files,
            transaction rules, or transaction impact methods are invalid.
    """
    loaded = (
        configuration
        if isinstance(configuration, Configuration)
        else load_config(configuration)
    )
    return _validate_config(
        loaded,
        require_complete_yaml_setup=require_complete_yaml_setup,
    )


def _validate_config(
    configuration: Configuration,
    *,
    require_complete_yaml_setup: bool,
) -> dict[str, object]:
    """Validate one comparison YAML file with explicit YAML setup strictness."""
    from perfaud import schema as _pc_cols
    from perfaud.data_issues.config import (
        data_issues_config_summary,
        security_master_filter_fields,
    )
    from perfaud.extract_contract import extract_contract_summary
    from perfaud.runner import ComparisonViews, validate_yaml_setup_complete
    from perfaud.source_data_contract import (
        comparison_required_dataset_names,
        source_data_contract_summary,
    )
    from perfaud.specification import (
        PORTFOLIO_COMPARISON_LEVEL,
        SECURITY_COMPARISON_LEVEL,
        Specification,
    )
    from perfaud.transaction_summary import format_codes

    specification = Specification(
        configuration.path,
        comparison_level=PORTFOLIO_COMPARISON_LEVEL,
        values=configuration.values,
    )
    comparison_views = ComparisonViews(
        configuration.path,
        values=configuration.values,
    )
    findings = comparison_views.findings(PORTFOLIO_COMPARISON_LEVEL)
    if require_complete_yaml_setup:
        validate_yaml_setup_complete(findings)
    validated_levels = [PORTFOLIO_COMPARISON_LEVEL]
    security_file = specification.files.get(_pc_cols.SECURITY_PERFORMANCE)
    if (
        security_file is not None
        and security_file.snapshot_a_path.is_file()
        and security_file.snapshot_b_path.is_file()
    ):
        security_findings = comparison_views.findings(SECURITY_COMPARISON_LEVEL)
        if require_complete_yaml_setup:
            validate_yaml_setup_complete(security_findings)
        validated_levels.append(SECURITY_COMPARISON_LEVEL)
    transaction_preview = _validate_transactions(specification)
    _validate_security_master(specification)
    contract_summary = extract_contract_summary(
        specification.values,
        specification_path=specification.path,
    )
    dataset_names = ", ".join(sorted(specification.files))
    minimum_contract = source_data_contract_summary(
        comparison_level=specification.comparison_level,
        include_reconstruction_sources=(
            specification.portfolio_return_reconstruction is not None
            or specification.security_return_reconstruction is not None
        ),
        include_security_performance=(
            specification.security_return_reconstruction is not None
        ),
        include_security_master=bool(
            security_master_filter_fields(specification.values)
        ),
    )
    data_issues_summary = data_issues_config_summary(specification.values)
    return {
        "snapshot_a": specification.snapshot_a.path,
        "snapshot_b": specification.snapshot_b.path,
        "dataset_names": dataset_names,
        "validated_report_levels": ", ".join(validated_levels),
        "minimum_required_datasets": ", ".join(
            comparison_required_dataset_names(specification)
        ),
        "required_source_data_columns": minimum_contract["required_columns"],
        "missing_optional_files": _missing_optional_files(specification),
        "holding_impact_methods": _holding_impact_methods(specification),
        "price_impact_methods": _price_impact_methods(specification),
        "evidence_only_impact_methods": _evidence_only_impact_methods(specification),
        "data_issues_checks_enabled": data_issues_summary["checks_enabled"],
        "data_issues_policy": data_issues_summary["policy"],
        "transaction_rule_count": _transaction_rule_count(specification),
        "transaction_impact_methods": _transaction_impact_methods(specification),
        "extract_contract": contract_summary["path"],
        "enforce_ambiguous_axys_flows": (
            contract_summary["enforce_ambiguous_axys_flows"]
        ),
        "required_transaction_context_columns": format_codes(
            contract_summary["required_transaction_context_columns"]
        ),
        "transaction_files_checked": transaction_preview["files_checked"],
        "transaction_codes_observed": transaction_preview["codes_observed"],
        "transaction_codes_without_yaml_rules": (
            transaction_preview["codes_without_yaml_rules"]
        ),
        "transaction_semantics_sources": transaction_preview["semantics_sources"],
        "transaction_semantics": transaction_preview["summary"],
        "extract_contract_summary": contract_summary,
    }


def _validate_transactions(
    specification: Specification,
) -> dict[str, object]:
    """Validate configured transaction files and return preview fields."""
    from perfaud import schema as _pc_cols
    from perfaud.data_issues.config import required_transaction_columns
    from perfaud.transaction_summary import (
        format_codes,
        format_semantics_source_counts,
        transaction_rule_codes,
        transaction_semantics_summary,
    )
    from perfaud.transactions import TransactionsLoader

    required_columns = required_transaction_columns(specification.values)
    if _pc_cols.TRANSACTIONS not in specification.files:
        if required_columns:
            raise PerfaudError(
                (
                    f"{specification.path}: enabled Data Issues checks require "
                    "files.transactions."
                ),
            )
        return {
            "files_checked": 0,
            "codes_observed": "none",
            "codes_without_yaml_rules": "none",
            "semantics_sources": "none",
            "summary": transaction_semantics_summary([]),
        }
    loader = TransactionsLoader(specification)
    checked = 0
    frames = []
    for snapshot_key in ("a", "b"):
        frame = loader.load(snapshot_key)
        if frame is None:
            if required_columns:
                raise PerfaudError(
                    (
                        f"{specification.path}: enabled Data Issues checks require "
                        f"transactions for snapshot {snapshot_key}."
                    ),
                )
            continue
        missing_columns = sorted(required_columns - set(frame.columns))
        if missing_columns:
            raise PerfaudError(
                (
                    f"{specification.path}: transactions for snapshot "
                    f"{snapshot_key} are missing columns required by enabled "
                    f"Data Issues checks: {', '.join(missing_columns)}."
                ),
            )
        checked += 1
        frames.append(frame)
    summary = transaction_semantics_summary(
        frames,
        rule_codes=transaction_rule_codes(specification.values),
    )
    return {
        "files_checked": checked,
        "codes_observed": format_codes(summary["observed_codes"]),
        "codes_without_yaml_rules": format_codes(summary["codes_without_yaml_rules"]),
        "semantics_sources": format_semantics_source_counts(
            summary["semantics_source_counts"]
        ),
        "summary": summary,
    }


def _validate_security_master(specification: Specification) -> None:
    """Validate fields required by configured reference qualifiers."""
    from perfaud.data_issues.config import security_master_filter_fields
    from perfaud.security_master import SecurityMasterLoader

    required_columns = security_master_filter_fields(specification.values)
    if not required_columns:
        return

    loader = SecurityMasterLoader(specification)
    for snapshot_key in ("a", "b"):
        frame = loader.load(snapshot_key)
        if frame is None:
            raise PerfaudError(
                (
                    "Data Issues security_master.* filters require "
                    f"files.security_master in snapshot {snapshot_key}.  |  "
                    f"audit_specification_path={specification.path}"
                ),
            )
        missing_columns = sorted(required_columns - set(frame.columns))
        if missing_columns:
            raise PerfaudError(
                (
                    f"security_master for snapshot {snapshot_key} is missing "
                    f"filter columns: {', '.join(missing_columns)}.  |  "
                    f"audit_specification_path={specification.path}"
                ),
            )


def _missing_optional_files(
    specification: Specification,
) -> str:
    """Return a readable list of configured optional files that are absent."""
    missing_files: list[str] = []
    for comparison_file in specification.files.values():
        if comparison_file.required:
            continue
        for snapshot_key, file_path in (
            ("a", comparison_file.snapshot_a_path),
            ("b", comparison_file.snapshot_b_path),
        ):
            if not file_path.exists():
                missing_files.append(f"{comparison_file.name}:{snapshot_key}")
    return ", ".join(sorted(missing_files)) if missing_files else "none"


def _transaction_rule_count(
    specification: Specification,
) -> int:
    """Return the number of configured transaction code rules."""
    rules_value = specification.values.get("transaction_rules", {})
    return len(rules_value) if isinstance(rules_value, dict) else 0


def _transaction_impact_methods(
    specification: Specification,
) -> str:
    """Return configured transaction impact method keys."""
    methods_value = specification.values.get("transaction_impact_methods", {})
    if not isinstance(methods_value, dict) or not methods_value:
        return "none"
    return ", ".join(sorted(str(key) for key in methods_value))


def _holding_impact_methods(
    specification: Specification,
) -> str:
    """Return configured holding impact method keys."""
    methods_value = specification.values.get("holding_impact_methods", {})
    if not isinstance(methods_value, dict) or not methods_value:
        return "none"
    return ", ".join(sorted(str(key) for key in methods_value))


def _price_impact_methods(
    specification: Specification,
) -> str:
    """Return configured price impact method keys."""
    methods_value = specification.values.get("price_impact_methods", {})
    if not isinstance(methods_value, dict) or not methods_value:
        return "none"
    return ", ".join(sorted(str(key) for key in methods_value))


def _evidence_only_impact_methods(
    specification: Specification,
) -> str:
    """Return configured evidence-only impact method keys."""
    methods_value = specification.values.get("evidence_only_impact_methods", {})
    if not isinstance(methods_value, dict) or not methods_value:
        return "none"
    return ", ".join(sorted(str(key) for key in methods_value))

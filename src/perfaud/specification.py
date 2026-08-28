"""Read and validate Audit YAML specifications."""

from __future__ import annotations

# Python imports
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Final, cast

# Project imports
from perfaud.errors import PerfaudError
from perfaud.data_issues.config import (
    security_master_filter_fields,
    validate_data_issues_config,
)
from perfaud.comparison.methods import (
    ModifiedDietzDayCount,
    ModifiedDietzFlowTiming,
    ModifiedDietzInclusionRule,
    ReturnBasis,
    ReturnReconstructionFlowSource,
    ReturnReconstructionMethod,
    ReturnReconstructionSignConvention,
    ReturnReconstructionValueSource,
)
import perfaud.paths as util

_SNAPSHOT_A_KEY: Final[str] = "a"
_SNAPSHOT_B_KEY: Final[str] = "b"
_SNAPSHOTS_KEY: Final[str] = "snapshots"
_FILES_KEY: Final[str] = "files"
_PATH_KEY: Final[str] = "path"
_COLUMNS_KEY: Final[str] = "columns"
_LABEL_KEY: Final[str] = "label"
_SCHEMA_KEY: Final[str] = "schema"
_SUPPORTED_SNAPSHOT_KEYS: Final[frozenset[str]] = frozenset(
    {_LABEL_KEY, _PATH_KEY, _SCHEMA_KEY}
)
_REQUIRED_KEY: Final[str] = "required"
_SUPPORTED_FILE_FIELDS: Final[frozenset[str]] = frozenset(
    {_PATH_KEY, _COLUMNS_KEY, _REQUIRED_KEY}
)
_COMPARISON_KEY: Final[str] = "comparison"
_LEVEL_KEY: Final[str] = "level"
_TOLERANCES_KEY: Final[str] = "tolerances"
_REQUIRED_TOLERANCE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "return",
        "market_value",
        "quantity",
        "price",
        "split_factor",
    }
)
_EXTRACT_CONTRACT_KEY: Final[str] = "extract_contract"
_EXTRACT_CONTRACT_SUPPORTED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "enforce_ambiguous_axys_flows",
        "path",
    }
)
_PORTFOLIO_RETURN_RECONSTRUCTION_KEY: Final[str] = "portfolio_return_reconstruction"
_SECURITY_RETURN_RECONSTRUCTION_KEY: Final[str] = "security_return_reconstruction"
_PORTFOLIO_PERFORMANCE_KEY: Final[str] = "portfolio_performance"
_SECURITY_PERFORMANCE_KEY: Final[str] = "security_performance"
_SECURITY_MASTER_KEY: Final[str] = "security_master"
_SUPPORTED_FILE_KEYS: Final[frozenset[str]] = frozenset(
    {
        _PORTFOLIO_PERFORMANCE_KEY,
        _SECURITY_PERFORMANCE_KEY,
        "splits",
        "holdings",
        "transactions",
        _SECURITY_MASTER_KEY,
    }
)
_DEFAULT_FILE_PATHS: Final[dict[str, str]] = {
    _PORTFOLIO_PERFORMANCE_KEY: "portperf.csv",
    _SECURITY_PERFORMANCE_KEY: "secperf.csv",
    "holdings": "holdings.csv",
    "transactions": "transactions.csv",
    _SECURITY_MASTER_KEY: "secmast.csv",
}
_SUPPORTED_ROOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "exclude_suppressed",
        "outputs",
        "reconstruction_diagnostics",
        "reports",
        "require_causal_attribution",
        _COMPARISON_KEY,
        "data_issues",
        "evidence_only_impact_methods",
        _EXTRACT_CONTRACT_KEY,
        _FILES_KEY,
        "holding_impact_methods",
        _PORTFOLIO_RETURN_RECONSTRUCTION_KEY,
        "price_impact_methods",
        _SECURITY_RETURN_RECONSTRUCTION_KEY,
        "security_return_impact_methods",
        _SNAPSHOTS_KEY,
        "suppressions",
        _TOLERANCES_KEY,
        "transaction_impact_methods",
        "transaction_rules",
    }
)
PORTFOLIO_COMPARISON_LEVEL: Final[str] = "portfolio"
SECURITY_COMPARISON_LEVEL: Final[str] = "security"
SECURITY_PERFORMANCE_UNAVAILABLE_REASON: Final[str] = (
    "security_performance_unavailable"
)
COMPARISON_LEVELS: Final[frozenset[str]] = frozenset(
    {PORTFOLIO_COMPARISON_LEVEL, SECURITY_COMPARISON_LEVEL}
)
_RECONSTRUCTION_REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "method",
    "beginning_value_source",
    "ending_value_source",
    "flow_source",
    "flow_categories",
    "income_categories",
    "return_basis",
    "sign_convention",
)
_RECONSTRUCTION_TIMED_FLOW_KEYS: Final[tuple[str, ...]] = (
    "flow_timing",
    "day_count",
    "inclusion_rule",
)
_RETURN_RECONSTRUCTION_METHODS: Final[frozenset[str]] = frozenset(
    method.value for method in ReturnReconstructionMethod
)


@dataclass(frozen=True)
class ComparisonSnapshot:
    """Resolved comparison snapshot configuration.

    Attributes:
        key: Neutral snapshot key, currently ``"a"`` or ``"b"``.
        label: User-facing snapshot label.
        path: Resolved snapshot directory path.
        schema_path: Optional resolved source-column mapping YAML path.
    """

    key: str
    label: str
    path: Path
    schema_path: Path | None


@dataclass(frozen=True)
class ComparisonFile:
    """Resolved comparison source-file configuration for both snapshots.

    Attributes:
        name: Normalized dataset name such as ``portfolio_performance``.
        relative_path: File path configured relative to each snapshot.
        snapshot_a_path: Resolved file path in snapshot A.
        snapshot_b_path: Resolved file path in snapshot B.
        required: Whether optional-file existence must be validated up front.
    """

    name: str
    relative_path: Path
    snapshot_a_path: Path
    snapshot_b_path: Path
    required: bool


@dataclass(frozen=True)
class PortfolioReturnReconstruction:
    """Resolved portfolio return-reconstruction settings.

    Attributes:
        method: Return reconstruction method.
        beginning_value_source: Dataset used for beginning value.
        ending_value_source: Dataset used for ending value.
        flow_source: Dataset used for dated external flows.
        flow_timing: Transaction date field used for dated flow weighting, or
            ``None`` for methods that do not use dated flow weights.
        day_count: Day-count convention, or ``None`` for methods that do not
            use dated flow weights.
        inclusion_rule: Beginning/end-of-day flow inclusion rule, or ``None``
            for methods that do not use dated flow weights.
        flow_categories: Transaction categories treated as external flows.
        income_categories: Transaction categories treated as income inputs.
        return_basis: Reported-return basis for fee/expense interpretation.
        sign_convention: Transaction amount sign convention.
    """

    method: str
    beginning_value_source: str
    ending_value_source: str
    flow_source: str
    flow_timing: str | None
    day_count: str | None
    inclusion_rule: str | None
    flow_categories: tuple[str, ...]
    income_categories: tuple[str, ...]
    return_basis: str
    sign_convention: str


SecurityReturnReconstruction = PortfolioReturnReconstruction


class Specification:
    """Read Audit YAML settings and resolve fixture paths.

    Attributes:
        path: Filesystem path to the comparison YAML specification.
        values: Parsed YAML settings dictionary.
        snapshot_a: Resolved snapshot A settings.
        snapshot_b: Resolved snapshot B settings.
        files: Resolved file settings keyed by normalized dataset name.
        comparison_level: Primary performance-result level to compare. The
            caller or YAML must explicitly select ``"portfolio"`` or
            ``"security"``; ``"security"`` uses ``security_performance`` as
            the target performance-result dataset.

    Notes:
        The primary performance-result file is always required. Other files are
        optional unless configured with ``required: true``, which only controls
        preflight file-existence validation.
    """

    def __init__(
        self,
        path: util.PathLike,
        *,
        comparison_level: str | None = None,
        values: dict[str, Any] | None = None,
    ) -> None:
        """Read and validate a performance comparison specification.

        Args:
            path: Path to the comparison YAML specification.
            comparison_level: Optional primary performance-result level override.
                When omitted, the YAML must provide ``comparison.level``.
            values: Already-loaded configuration values. Workspace execution uses
                this to guarantee that YAML is loaded exactly once.

        Raises:
            PerfaudError: If the YAML cannot be parsed, its shape is invalid, the
                required snapshots are missing, or required files do not exist.
        """
        if values is None:
            from perfaud.config import load_config

            configuration = load_config(path)
            self.path = configuration.path
            self.values = configuration.values
        else:
            self.path = Path(path).expanduser().resolve()
            self.values = values
        self._validate_comparison_configuration(comparison_level)
        self._validate_tolerances_configuration()
        self._validate_extract_contract_configuration()
        self._validate_data_issues_configuration()
        self._validate_root_keys()
        self.comparison_level = self._comparison_level(comparison_level)
        self.portfolio_return_reconstruction = (
            self._portfolio_return_reconstruction()
        )
        self.security_return_reconstruction = self._security_return_reconstruction()
        self.snapshot_a = self._snapshot(_SNAPSHOT_A_KEY)
        self.snapshot_b = self._snapshot(_SNAPSHOT_B_KEY)
        self.files = self._files()
        self._validate_reconstruction_files()
        self._validate_data_issues_reference_file()
        self._validate_required_files()

    def _validate_data_issues_configuration(self) -> None:
        """Validate Data Issues before loading or reporting.

        Raises:
            PerfaudError: If Data Issues configuration is malformed, unknown, or
                unsafe.
        """
        try:
            validate_data_issues_config(self.values)
        except ValueError as error:
            raise PerfaudError(self._error_message(str(error))) from error

    def _validate_root_keys(self) -> None:
        """Reject unknown top-level configuration keys.

        Raises:
            PerfaudError: If the YAML root contains a key that no Audit component
                consumes.
        """
        unsupported = sorted(
            str(key) for key in self.values if key not in _SUPPORTED_ROOT_KEYS
        )
        if unsupported:
            raise PerfaudError(
                self._error_message(
                    "YAML has unsupported top-level keys: "
                    + ", ".join(unsupported)
                    + "."
                ),
            )

    def _validate_comparison_configuration(self, override: str | None) -> None:
        """Require a caller or YAML primary comparison level."""
        comparison = self.values.get(_COMPARISON_KEY)
        if comparison is None and override is not None:
            return
        if not isinstance(comparison, dict):
            raise PerfaudError(
                self._error_message("comparison must be a mapping."),
            )
        if _LEVEL_KEY not in comparison:
            raise PerfaudError(
                self._error_message("comparison.level is required."),
            )

    def _validate_tolerances_configuration(self) -> None:
        """Require every comparison tolerance as an explicit finite value."""
        tolerances = self.values.get(_TOLERANCES_KEY)
        if not isinstance(tolerances, dict):
            raise PerfaudError(
                self._error_message("tolerances must be a mapping."),
            )
        unsupported = sorted(
            str(key) for key in tolerances if key not in _REQUIRED_TOLERANCE_KEYS
        )
        if unsupported:
            raise PerfaudError(
                self._error_message(
                    "tolerances has unsupported keys: " + ", ".join(unsupported) + "."
                ),
            )
        missing = sorted(_REQUIRED_TOLERANCE_KEYS - set(tolerances))
        if missing:
            raise PerfaudError(
                self._error_message(
                    "tolerances is missing required keys: " + ", ".join(missing) + "."
                ),
            )
        for key in sorted(_REQUIRED_TOLERANCE_KEYS):
            value = tolerances[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0.0
            ):
                raise PerfaudError(
                    self._error_message(
                        f"tolerances.{key} must be a finite nonnegative number."
                    ),
                )

    def _validate_extract_contract_configuration(self) -> None:
        """Validate any explicit extract-contract overrides."""
        contract = self.values.get(_EXTRACT_CONTRACT_KEY)
        if contract is None:
            return
        if not isinstance(contract, dict):
            raise PerfaudError(
                self._error_message("extract_contract must be a mapping."),
            )
        unsupported = sorted(
            str(key) for key in contract if key not in _EXTRACT_CONTRACT_SUPPORTED_KEYS
        )
        if unsupported:
            raise PerfaudError(
                self._error_message(
                    "extract_contract has unsupported keys: "
                    + ", ".join(unsupported)
                    + "."
                ),
            )
    def resolve_path(self, file_path: util.PathLike) -> Path:
        """Return an absolute or comparison-YAML-relative path.

        Args:
            file_path: Path from the comparison specification.

        Returns:
            Absolute paths unchanged; relative paths resolved beside the
            comparison YAML file.
        """
        path = Path(file_path)
        return path if path.is_absolute() else self.path.parent / path

    def _snapshot(self, key: str) -> ComparisonSnapshot:
        """Return one resolved snapshot definition."""
        snapshots = self.values.get(_SNAPSHOTS_KEY)
        if not isinstance(snapshots, dict):
            raise PerfaudError(self._error_message("snapshots must be a mapping."))

        snapshot = snapshots.get(key)
        if not isinstance(snapshot, dict):
            raise PerfaudError(
                self._error_message(f"snapshots.{key} must be a mapping."),
            )

        unsupported_keys = sorted(
            str(setting) for setting in snapshot if setting not in _SUPPORTED_SNAPSHOT_KEYS
        )
        if unsupported_keys:
            raise PerfaudError(
                self._error_message(
                    f"snapshots.{key} has unsupported keys: "
                    + ", ".join(unsupported_keys)
                    + "."
                ),
            )

        snapshot_path_value = snapshot.get(_PATH_KEY)
        if not isinstance(snapshot_path_value, str) or not snapshot_path_value:
            raise PerfaudError(
                self._error_message(f"snapshots.{key}.path must be a string."),
            )
        snapshot_path = self.resolve_path(snapshot_path_value)

        label_value = snapshot.get(_LABEL_KEY, key)
        if not isinstance(label_value, str) or not label_value:
            raise PerfaudError(
                self._error_message(f"snapshots.{key}.label must be a string."),
            )

        schema_value = snapshot.get(_SCHEMA_KEY)
        schema_path = self._schema_path(key, schema_value)

        return ComparisonSnapshot(
            key=key,
            label=label_value,
            path=snapshot_path,
            schema_path=schema_path,
        )

    def _schema_path(self, key: str, schema_value: object) -> Path | None:
        """Return a resolved external schema path or ``None`` when omitted."""
        if schema_value is None:
            return None
        if not isinstance(schema_value, str) or not schema_value:
            raise PerfaudError(
                self._error_message(
                    f"snapshots.{key}.schema must be a nonempty string path; "
                    "inline mappings are not supported."
                ),
            )
        return self.resolve_path(schema_value)

    def _files(self) -> dict[str, ComparisonFile]:
        """Return resolved comparison files keyed by normalized dataset name."""
        files_value = self.values.get(_FILES_KEY, {})
        if not isinstance(files_value, dict):
            raise PerfaudError(self._error_message("files must be a mapping."))

        files: dict[str, ComparisonFile] = {}
        file_values = self._default_file_values(files_value)
        for file_name, file_value in file_values.items():
            if not isinstance(file_name, str) or not file_name:
                raise PerfaudError(self._error_message("File names must be strings."))
            if file_name not in _SUPPORTED_FILE_KEYS:
                supported = ", ".join(sorted(_SUPPORTED_FILE_KEYS))
                raise PerfaudError(
                    self._error_message(
                        f"files.{file_name} is not supported. Supported files: "
                        f"{supported}."
                    ),
                )
            files[file_name] = self._file(file_name, file_value)
        return files

    def _default_file_values(
        self,
        configured_values: dict[object, object],
    ) -> dict[object, object]:
        """Return explicit paths plus required standard filename defaults.

        A required dataset always receives its standard filename when omitted,
        so normal missing-file validation remains fail-closed. Optional evidence
        remains explicit because silently activating a discovered dataset can
        change comparison findings and its required accounting policies.
        """
        values = dict(configured_values)
        required_names = self._required_file_names()
        for file_name, default_path in _DEFAULT_FILE_PATHS.items():
            if file_name in values:
                continue
            if file_name in required_names:
                values[file_name] = default_path
        return values

    def _portfolio_return_reconstruction(
        self,
    ) -> PortfolioReturnReconstruction | None:
        """Return validated portfolio return-reconstruction settings."""
        return self._return_reconstruction(_PORTFOLIO_RETURN_RECONSTRUCTION_KEY)

    def _security_return_reconstruction(
        self,
    ) -> SecurityReturnReconstruction | None:
        """Return validated security return-reconstruction settings."""
        return self._return_reconstruction(_SECURITY_RETURN_RECONSTRUCTION_KEY)

    def _return_reconstruction(
        self,
        section: str,
    ) -> PortfolioReturnReconstruction | None:
        """Return validated return-reconstruction settings for a YAML section."""
        reconstruction = self.values.get(section)
        if reconstruction is None:
            return None
        if not isinstance(reconstruction, dict):
            raise PerfaudError(
                self._error_message(
                    f"{section} must be a mapping."
                ),
            )

        supported_keys = set(_RECONSTRUCTION_REQUIRED_KEYS) | set(
            _RECONSTRUCTION_TIMED_FLOW_KEYS
        )
        unsupported_keys = sorted(str(key) for key in reconstruction if key not in supported_keys)
        if unsupported_keys:
            raise PerfaudError(
                self._error_message(
                    f"{section} has unsupported keys: {', '.join(unsupported_keys)}."
                ),
            )

        missing_keys = [
            key for key in _RECONSTRUCTION_REQUIRED_KEYS if key not in reconstruction
        ]
        if missing_keys:
            raise PerfaudError(
                self._error_message(
                    f"{section} missing required keys: {', '.join(missing_keys)}."
                ),
            )
        method = self._required_choice(
            section,
            "method",
            reconstruction["method"],
            set(_RETURN_RECONSTRUCTION_METHODS),
        )
        timing_values = self._return_reconstruction_timing_values(
            section,
            reconstruction,
            method,
        )

        return PortfolioReturnReconstruction(
            method=method,
            beginning_value_source=self._required_choice(
                section,
                "beginning_value_source",
                reconstruction["beginning_value_source"],
                {ReturnReconstructionValueSource.HOLDINGS.value},
            ),
            ending_value_source=self._required_choice(
                section,
                "ending_value_source",
                reconstruction["ending_value_source"],
                {ReturnReconstructionValueSource.HOLDINGS.value},
            ),
            flow_source=self._required_choice(
                section,
                "flow_source",
                reconstruction["flow_source"],
                {ReturnReconstructionFlowSource.TRANSACTIONS.value},
            ),
            flow_timing=timing_values[0],
            day_count=timing_values[1],
            inclusion_rule=timing_values[2],
            flow_categories=self._required_string_list(
                section,
                "flow_categories",
                reconstruction["flow_categories"],
            ),
            income_categories=self._required_string_list(
                section,
                "income_categories",
                reconstruction["income_categories"],
            ),
            return_basis=self._required_choice(
                section,
                "return_basis",
                reconstruction["return_basis"],
                {ReturnBasis.GROSS.value, ReturnBasis.NET.value},
            ),
            sign_convention=self._required_choice(
                section,
                "sign_convention",
                reconstruction["sign_convention"],
                {ReturnReconstructionSignConvention.SIGNED_AMOUNT.value},
            ),
        )

    def _return_reconstruction_timing_values(
        self,
        section: str,
        reconstruction: dict[object, object],
        method: str,
    ) -> tuple[str | None, str | None, str | None]:
        """Return validated timing fields for one reconstruction method."""
        if method == ReturnReconstructionMethod.MODIFIED_DIETZ.value:
            missing_keys = [
                key for key in _RECONSTRUCTION_TIMED_FLOW_KEYS if key not in reconstruction
            ]
            if missing_keys:
                raise PerfaudError(
                    self._error_message(
                        f"{section} missing required keys for method "
                        f"{method}: {', '.join(missing_keys)}."
                    ),
                )
            return (
                self._required_choice(
                    section,
                    "flow_timing",
                    reconstruction["flow_timing"],
                    {
                        "transaction_date",
                        ModifiedDietzFlowTiming.TRADE_DATE.value,
                        ModifiedDietzFlowTiming.SETTLEMENT_DATE.value,
                    },
                ),
                self._required_choice(
                    section,
                    "day_count",
                    reconstruction["day_count"],
                    {ModifiedDietzDayCount.ACTUAL_DAYS.value},
                ),
                self._required_choice(
                    section,
                    "inclusion_rule",
                    reconstruction["inclusion_rule"],
                    {
                        ModifiedDietzInclusionRule.BEGINNING_OF_DAY.value,
                        ModifiedDietzInclusionRule.END_OF_DAY.value,
                    },
                ),
            )

        unsupported_keys = [
            key for key in _RECONSTRUCTION_TIMED_FLOW_KEYS if key in reconstruction
        ]
        if unsupported_keys:
            raise PerfaudError(
                self._error_message(
                    f"{section} keys are not valid for method {method}: "
                    f"{', '.join(unsupported_keys)}."
                ),
            )
        return (None, None, None)

    def _required_choice(
        self,
        section: str,
        key: str,
        value: object,
        allowed_values: set[str],
    ) -> str:
        """Return a required string enum value or raise."""
        if not isinstance(value, str) or not value:
            raise PerfaudError(
                self._error_message(f"{section}.{key} must be a string."),
            )
        if value not in allowed_values:
            allowed = ", ".join(sorted(allowed_values))
            raise PerfaudError(
                self._error_message(
                    f"{section}.{key} must be one of: {allowed}."
                ),
            )
        return value

    def _required_string_list(
        self,
        section: str,
        key: str,
        value: object,
    ) -> tuple[str, ...]:
        """Return a required list of strings or raise."""
        if not isinstance(value, list):
            raise PerfaudError(
                self._error_message(f"{section}.{key} must be a list."),
            )
        if not all(isinstance(item, str) and item for item in value):
            raise PerfaudError(
                self._error_message(
                    f"{section}.{key} must contain only non-empty strings."
                ),
            )
        return tuple(value)

    def _file(self, file_name: str, file_value: object) -> ComparisonFile:
        """Return one resolved comparison file definition."""
        required_file_names = self._required_file_names()
        required = file_name in required_file_names
        if isinstance(file_value, str):
            relative_path = Path(file_value)
        elif isinstance(file_value, dict):
            unsupported_keys = sorted(
                str(key) for key in file_value if key not in _SUPPORTED_FILE_FIELDS
            )
            if unsupported_keys:
                raise PerfaudError(
                    self._error_message(
                        f"files.{file_name} has unsupported keys: "
                        + ", ".join(unsupported_keys)
                        + "."
                    ),
                )
            path_value = file_value.get(_PATH_KEY)
            if not isinstance(path_value, str) or not path_value:
                raise PerfaudError(
                    self._error_message(f"files.{file_name}.path must be a string."),
                )
            if _REQUIRED_KEY in file_value:
                if file_name in required_file_names:
                    raise PerfaudError(
                        self._error_message(
                            f"files.{file_name} is required by the comparison "
                            "contract and must not specify required."
                        ),
                    )
                required_value = file_value[_REQUIRED_KEY]
                if not isinstance(required_value, bool):
                    raise PerfaudError(
                        self._error_message(
                            f"files.{file_name}.required must be a boolean."
                        ),
                    )
                required = required_value
            columns_value = file_value.get(_COLUMNS_KEY, {})
            if not isinstance(columns_value, dict):
                raise PerfaudError(
                    self._error_message(
                        f"files.{file_name}.columns must be a mapping."
                    ),
                )
            relative_path = Path(path_value)
        else:
            raise PerfaudError(
                self._error_message(f"files.{file_name} must be a string or mapping."),
            )

        return ComparisonFile(
            name=file_name,
            relative_path=relative_path,
            snapshot_a_path=self._snapshot_file_path(self.snapshot_a, relative_path),
            snapshot_b_path=self._snapshot_file_path(self.snapshot_b, relative_path),
            required=required,
        )

    def _comparison_level(self, override: str | None = None) -> str:
        """Return the explicit caller or YAML primary comparison level."""
        if override is not None:
            level_value = override
        else:
            comparison_value = cast(dict[str, Any], self.values[_COMPARISON_KEY])
            level_value = comparison_value[_LEVEL_KEY]
        if not isinstance(level_value, str) or level_value not in COMPARISON_LEVELS:
            allowed_values = ", ".join(sorted(COMPARISON_LEVELS))
            raise PerfaudError(
                self._error_message(
                    f"comparison.level must be one of: {allowed_values}."
                ),
            )
        return level_value

    def _required_performance_file_name(self) -> str:
        """Return the required performance-result file for the comparison level."""
        if self.comparison_level == SECURITY_COMPARISON_LEVEL:
            return _SECURITY_PERFORMANCE_KEY
        return _PORTFOLIO_PERFORMANCE_KEY

    def _required_file_names(self) -> frozenset[str]:
        """Return source file names required by comparison level and formulas."""
        required_names = {self._required_performance_file_name()}
        if self._active_return_reconstruction_configured():
            required_names.update({"holdings", "transactions"})
        if security_master_filter_fields(self.values):
            required_names.add(_SECURITY_MASTER_KEY)
        return frozenset(required_names)

    def _active_return_reconstruction_configured(self) -> bool:
        """Return whether the active comparison level has reconstruction enabled."""
        if self.comparison_level == SECURITY_COMPARISON_LEVEL:
            return self.security_return_reconstruction is not None
        return self.portfolio_return_reconstruction is not None

    @staticmethod
    def _snapshot_file_path(
        snapshot: ComparisonSnapshot,
        relative_path: Path,
    ) -> Path:
        """Return a snapshot file path resolved relative to the snapshot path."""
        return relative_path if relative_path.is_absolute() else snapshot.path / relative_path

    def _validate_required_files(self) -> None:
        """Validate existence for portfolio performance and required files."""
        for comparison_file in self.files.values():
            if not comparison_file.required:
                continue
            for snapshot_key, file_path in (
                ("a", comparison_file.snapshot_a_path),
                ("b", comparison_file.snapshot_b_path),
            ):
                if not util.file_path_exists(file_path):
                    context: dict[str, object] = {
                        "dataset": comparison_file.name,
                        "snapshot": snapshot_key,
                        "path": str(file_path),
                    }
                    if (
                        comparison_file.name == _SECURITY_PERFORMANCE_KEY
                        and self.comparison_level == SECURITY_COMPARISON_LEVEL
                    ):
                        context["reason"] = SECURITY_PERFORMANCE_UNAVAILABLE_REASON
                    raise PerfaudError(
                        self._error_message(
                            f"files.{comparison_file.name} is required but "
                            f"snapshot {snapshot_key} is missing {file_path}."
                        ),
                        context=context,
                    )

    def _validate_reconstruction_files(self) -> None:
        """Raise if opted-in return reconstruction lacks required source files."""
        if not self._active_return_reconstruction_configured():
            return
        for file_name in ("holdings", "transactions"):
            if file_name not in self.files:
                raise PerfaudError(
                    self._error_message(
                        f"return reconstruction requires files.{file_name}."
                    ),
                )

    def _validate_data_issues_reference_file(self) -> None:
        """Require the optional reference dataset when a filter names it."""
        if not security_master_filter_fields(self.values):
            return
        if _SECURITY_MASTER_KEY not in self.files:
            raise PerfaudError(
                self._error_message(
                    "Data Issues security_master.* filters require "
                    "files.security_master."
                ),
            )

    def _error_message(self, message: str) -> str:
        """Return an error message with Audit specification context."""
        return f"{message}  |  audit_specification_path={self.path}"

"""Execute complete perfaud workspaces with atomic output publication."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import polars as pl

from perfaud import atomic_directory
from perfaud import report
from perfaud import review as review
from perfaud import source_loader
from perfaud.config import active_configuration, load_config, settings
from perfaud.data_issues import checks as data_issue_checks
from perfaud.errors import PerfaudError
from perfaud.runner import ComparisonViews
from perfaud.specification import (
    PORTFOLIO_COMPARISON_LEVEL,
    SECURITY_COMPARISON_LEVEL,
)
from perfaud.workbook.reconstruction import WorkbookReconstructionCache

CONFIG_FILE_NAME: Final[str] = "perfaud.yaml"
OUTPUT_DIRECTORY_NAME: Final[str] = "output"
_REPORT_TITLES: Final[dict[str, str]] = {
    PORTFOLIO_COMPARISON_LEVEL: "Portfolio Audit Report",
    SECURITY_COMPARISON_LEVEL: "Security Audit Report",
}


@dataclass(frozen=True)
class RunResult:
    """Describe one successfully published workspace result.

    Attributes:
        workspace: Resolved workspace directory.
        output_directory: Fixed published output directory.
        artifacts: Immutable, deterministic inventory of published files.
    """

    workspace: Path
    output_directory: Path
    artifacts: tuple[Path, ...]


@source_loader.source_frame_cache()
def run(workspace: str | Path = ".") -> RunResult:
    """Validate and execute a complete perfaud workspace.

    Args:
        workspace: Directory containing exactly ``perfaud.yaml``. Defaults to
            the current directory.

    Returns:
        Published workspace paths after every required validation succeeds.

    Raises:
        PerfaudError: If the workspace, configuration, inputs, or output fails.
    """
    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.is_dir():
        raise PerfaudError(f"Workspace is not a directory: {workspace_path}")
    config_path = workspace_path / CONFIG_FILE_NAME
    if not config_path.is_file():
        raise PerfaudError(
            f"{config_path} is missing. Create a workspace with "
            "'perfaud setup WORKSPACE'."
        )

    configuration = load_config(config_path)
    run_settings = settings(configuration)
    output_directory = workspace_path / OUTPUT_DIRECTORY_NAME
    with active_configuration(configuration):
        artifacts = _build_and_publish(
            configuration.path,
            configuration.values,
            output_directory,
            report_levels=run_settings.reports,
            include_workbook="xlsx" in run_settings.outputs,
            include_html="html" in run_settings.outputs,
            exclude_suppressed=run_settings.exclude_suppressed,
            include_reconstruction_diagnostics=(
                run_settings.reconstruction_diagnostics
            ),
            require_causal_attribution=run_settings.require_causal_attribution,
        )
    return RunResult(
        workspace=workspace_path,
        output_directory=output_directory,
        artifacts=artifacts,
    )


def _build_and_publish(
    config_path: Path,
    values: dict[str, object],
    output_directory: Path,
    *,
    report_levels: tuple[str, ...],
    include_workbook: bool,
    include_html: bool,
    exclude_suppressed: bool,
    include_reconstruction_diagnostics: bool,
    require_causal_attribution: bool,
) -> tuple[Path, ...]:
    """Build the complete artifact set and atomically replace prior output."""
    data_issues = data_issue_checks.data_issues_table(config_path)
    reconstruction_cache = WorkbookReconstructionCache(config_path)
    comparison_views = ComparisonViews(
        config_path,
        include_suppressed=not exclude_suppressed,
        require_causal_attribution=require_causal_attribution,
        reconstruction_cache=reconstruction_cache,
        values=values,
    )
    with atomic_directory.staged_directory(output_directory) as staging_directory:
        for comparison_level in report_levels:
            findings = comparison_views.findings(comparison_level)
            _write_report_level(
                config_path,
                findings,
                staging_directory / comparison_level,
                comparison_level=comparison_level,
                include_workbook=include_workbook,
                include_html=include_html,
                include_reconstruction_diagnostics=(
                    include_reconstruction_diagnostics
                ),
                require_causal_attribution=require_causal_attribution,
                data_issues=data_issues,
                reconstruction_cache=reconstruction_cache,
            )
    return tuple(
        sorted(path for path in output_directory.rglob("*") if path.is_file())
    )


def _write_report_level(
    config_path: Path,
    findings: pl.DataFrame,
    output_directory: Path,
    *,
    comparison_level: str,
    include_workbook: bool,
    include_html: bool,
    include_reconstruction_diagnostics: bool,
    require_causal_attribution: bool,
    data_issues: pl.DataFrame,
    reconstruction_cache: WorkbookReconstructionCache,
) -> None:
    """Write and validate one configured report level inside staging."""
    paths = report._write_audit_report_bundle_in_place(
        findings,
        output_directory,
        title=_REPORT_TITLES[comparison_level],
        top_evidence_limit=10,
        include_workbook=include_workbook,
        include_html_output=include_html,
        require_causal_attribution=require_causal_attribution,
        comparison_path=config_path,
        comparison_level=comparison_level,
        include_reconstruction_diagnostics=include_reconstruction_diagnostics,
        _data_issues=data_issues,
        _reconstruction_cache=reconstruction_cache,
    )
    if include_workbook and review.REVIEW_WORKBOOK_ARTIFACT not in paths:
        raise PerfaudError(
            f"{comparison_level} output did not include its required workbook."
        )
    if include_html and review.HTML_REPORT_ARTIFACT not in paths:
        raise PerfaudError(
            f"{comparison_level} output did not include its required HTML report."
        )

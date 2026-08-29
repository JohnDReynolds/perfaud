"""Regenerate or verify the single README marketing image."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from lxml import html as lxml_html  # type: ignore[import-untyped]
from lxml.html import HtmlElement  # type: ignore[import-untyped]
from PIL import Image, ImageChops

from perfaud import rendering
from perfaud import review
from perfaud.cli.setup import setup
from perfaud.workspace import run


_ROOT = Path(__file__).resolve().parents[1]
_IMAGE_NAME = "PerformanceAuditPortfolio.jpg"
_IMAGE_PATH = _ROOT / "docs" / "images" / _IMAGE_NAME
_IMAGE_SIZE = (1440, 3380)
_RAW_URL = (
    "https://raw.githubusercontent.com/JohnDReynolds/perfaud/"
    f"main/docs/images/{_IMAGE_NAME}"
)
_FINGERPRINT_KEY = "perfaud-source-fingerprint"
_FINGERPRINT_VERSION = "perfaud-readme-image-v1"
_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chrome",
)
_SCENARIOS = {
    ("ALPHA", "2026-01-31", "2026-02-27"),
    ("ALPHA", "2026-05-01", "2026-05-29"),
    ("BALANCED", "2026-04-01", "2026-04-10"),
    ("BALANCED", "2026-05-09", "2026-05-14"),
    ("INCOME", "2026-01-01", "2026-01-30"),
    ("INCOME", "2026-02-28", "2026-03-31"),
    ("INCOME", "2026-04-01", "2026-04-30"),
}
_ISSUE_TYPES = {
    "missing_dividend",
    "holdings_accrued_rate",
    "pa_sa_rate",
    "transactions_price_range",
    "dividend_rate",
    "holdings_price_range",
}


def main(argv: Sequence[str] | None = None) -> int:
    """Render the image or verify its source fingerprint and public contract."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)

    _validate_readme_inventory()
    if args.check:
        _validate_image(_IMAGE_PATH)
        return 0

    with tempfile.TemporaryDirectory(prefix="perfaud_readme_image_") as directory:
        temporary = Path(directory)
        candidate = temporary / _IMAGE_NAME
        _render(candidate, temporary, _source_fingerprint())
        _validate_image(candidate)
        if args.output_dir is not None:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, args.output_dir / _IMAGE_NAME)
        _IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        candidate.replace(_IMAGE_PATH)
        print(f"Wrote {_IMAGE_PATH.relative_to(_ROOT)}")
    return 0


def _render(destination: Path, temporary: Path, fingerprint: str) -> None:
    """Generate a fresh demo report and render its reviewer-facing preview."""
    workspace = temporary / "workspace"
    setup(workspace)
    run(workspace)
    source = workspace / "output" / "portfolio" / "portfolio_audit.html"
    preview = temporary / "preview.html"
    _write_preview(source, preview)
    png_path = temporary / "preview.png"
    _render_png(
        _find_chrome(),
        preview,
        png_path,
        (1440, 16000),
        temporary / "chrome_profile",
        device_scale_factor=1,
    )
    size = _crop_and_save_jpg(png_path, destination, fingerprint)
    if size[0] < 1200 or size[1] < 1000:
        raise OSError(f"README image is implausibly small: {size[0]}x{size[1]}")


def _write_preview(source: Path, destination: Path) -> None:
    """Retain a concise, deterministic set of complete review scenarios."""
    document = lxml_html.document_fromstring(source.read_text(encoding="utf-8"))
    differences = document.get_element_by_id(
        rendering.html_section_id(review.PERFORMANCE_DIFFERENCES_SHEET)
    )
    causes = document.get_element_by_id(
        rendering.html_section_id(review.PERFORMANCE_DIFFERENCE_CAUSES_SHEET)
    )
    issues = document.get_element_by_id(
        rendering.html_section_id(review.DATA_ISSUES_SHEET)
    )
    _retain_scenario_rows(differences)
    _retain_scenario_rows(causes)
    _retain_issue_rows(issues)
    destination.write_text(
        lxml_html.tostring(document, encoding="unicode", doctype="<!doctype html>"),
        encoding="utf-8",
    )


def _retain_scenario_rows(section: HtmlElement) -> None:
    """Keep rows belonging to the selected complete review scenarios."""
    retained: set[tuple[str, str, str]] = set()
    kept = 0
    for row in section.xpath(".//tbody/tr"):
        values = [_cell_text(cell) for cell in row.xpath("./td")]
        scenario = (values[0], values[1], values[2])
        if scenario in _SCENARIOS:
            retained.add(scenario)
            kept += 1
        else:
            row.getparent().remove(row)
    if retained != _SCENARIOS:
        raise ValueError(f"README preview is missing scenarios: {sorted(_SCENARIOS - retained)}")
    _set_row_count(section, kept)


def _retain_issue_rows(section: HtmlElement) -> None:
    """Keep one connected example for each selected data-issue type."""
    retained: set[str] = set()
    for row in section.xpath(".//tbody/tr"):
        values = [_cell_text(cell) for cell in row.xpath("./td")]
        issue_type = values[5]
        matches = any(
            values[1] == portfolio and from_date <= values[2] <= thru_date
            for portfolio, from_date, thru_date in _SCENARIOS
        )
        if issue_type in _ISSUE_TYPES and issue_type not in retained and matches:
            retained.add(issue_type)
        else:
            row.getparent().remove(row)
    if retained != _ISSUE_TYPES:
        raise ValueError(f"README preview is missing issue types: {sorted(_ISSUE_TYPES - retained)}")
    _set_row_count(section, len(retained))


def _cell_text(cell: HtmlElement) -> str:
    """Return normalized text from one HTML table cell."""
    return " ".join(cell.text_content().split())


def _set_row_count(section: HtmlElement, count: int) -> None:
    """Update the visible row-count label after preview filtering."""
    labels = section.xpath('.//p[contains(@class, "pc-table-meta")]')
    if labels:
        labels[0].text = f"Rows: {count}"


def _render_png(
    chrome_path: str,
    html_path: Path,
    png_path: Path,
    window_size: Sequence[int],
    user_data_dir: Path,
    device_scale_factor: int = 1,
) -> None:
    """Render HTML with one retry using a fresh browser profile."""
    for attempt in range(2):
        profile = (
            user_data_dir
            if attempt == 0
            else user_data_dir.with_name(f"{user_data_dir.name}_retry")
        )
        command = [
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--hide-scrollbars",
            f"--force-device-scale-factor={device_scale_factor}",
            f"--user-data-dir={profile}",
            f"--screenshot={png_path}",
            f"--window-size={window_size[0]},{window_size[1]}",
            html_path.resolve().as_uri(),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                timeout=120,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if png_path.exists() and png_path.stat().st_size > 0:
                return
            if attempt == 1:
                raise
            shutil.rmtree(profile, ignore_errors=True)


def _crop_and_save_jpg(
    png_path: Path, jpg_path: Path, fingerprint: str
) -> tuple[int, int]:
    """Crop uniform browser margins and write a deterministic JPEG."""
    image = Image.open(png_path).convert("RGB")
    background = Image.new("RGB", image.size, image.getpixel((0, 0)))
    threshold = [0 if value <= 6 else 255 for value in range(256)]
    mask = ImageChops.difference(image, background).convert("L").point(threshold)
    bounds = mask.getbbox()
    if bounds is not None:
        padding = 48
        image = image.crop(
            (
                max(0, bounds[0] - padding),
                max(0, bounds[1] - padding),
                min(image.width, bounds[2] + padding),
                min(image.height, bounds[3] + padding),
            )
        )
    image.save(
        jpg_path,
        quality=95,
        optimize=True,
        comment=f"{_FINGERPRINT_KEY}:{fingerprint}".encode("ascii"),
    )
    return image.width, image.height


def _fingerprint_files() -> Sequence[Path]:
    """Return every repository input that can affect the marketing image."""
    files = [
        _ROOT / "scripts" / "render_readme_images.py",
        _ROOT / "constraints" / "ci.txt",
        _ROOT / "pyproject.toml",
    ]
    files.extend(
        path
        for path in sorted((_ROOT / "src" / "perfaud").rglob("*"))
        if path.is_file()
        and (
            path.suffix in {".csv", ".md", ".py", ".yaml"}
            or path.name == "py.typed"
        )
    )
    return files


def _source_fingerprint() -> str:
    """Return a stable digest of code, inputs, and pinned rendering dependencies."""
    digest = hashlib.sha256()
    digest.update(f"{_FINGERPRINT_VERSION}\0".encode("ascii"))
    for path in _fingerprint_files():
        content = path.read_bytes()
        relative = path.relative_to(_ROOT).as_posix()
        digest.update(f"{relative}\0{len(content)}\0".encode("utf-8"))
        digest.update(content)
    return digest.hexdigest()


def _validate_readme_inventory() -> None:
    """Require one canonical README reference and exactly one retained image."""
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    references = re.findall(r'https://raw\.githubusercontent\.com/[^"\s]+', readme)
    if references != [_RAW_URL]:
        raise RuntimeError("README must reference the canonical perfaud image exactly once.")
    images = {path.name for path in _IMAGE_PATH.parent.iterdir() if path.is_file()}
    if images != {_IMAGE_NAME}:
        raise RuntimeError(f"README image inventory differs: {sorted(images)}")


def _validate_image(path: Path) -> None:
    """Validate image format, dimensions, decodability, and source fingerprint."""
    if not path.is_file():
        raise RuntimeError(f"README image is missing: {path}")
    with Image.open(path) as image:
        if image.format != "JPEG" or image.size != _IMAGE_SIZE:
            raise RuntimeError(
                f"README image has unexpected format or dimensions: {_IMAGE_NAME}"
            )
        comment = image.info.get("comment")
        expected = f"{_FINGERPRINT_KEY}:{_source_fingerprint()}".encode("ascii")
        if comment != expected:
            raise RuntimeError(
                f"README image source fingerprint is stale: {_IMAGE_NAME}; "
                f"rerun {Path(__file__).as_posix()}"
            )
        image.verify()


def _find_chrome() -> str:
    """Return an available Chrome or Chromium executable."""
    for candidate in _CHROME_CANDIDATES:
        path = shutil.which(candidate) if "/" not in candidate else candidate
        if path and Path(path).exists():
            return path
    raise RuntimeError("Could not find Chrome or Chromium for image rendering.")


if __name__ == "__main__":
    raise SystemExit(main())

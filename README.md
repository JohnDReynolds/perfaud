# perfaud

> **Status:** perfaud is no longer supported. This repository is retained for
> historical reference and possible future resurrection.

`perfaud` explains why reported Axys/APX portfolio performance changed between
two snapshots. It produces reviewer-oriented portfolio and security workbooks,
HTML reports, source detail, and compact supporting evidence.

<img
  src="https://raw.githubusercontent.com/JohnDReynolds/perfaud/main/docs/images/PerformanceAuditPortfolio.jpg"
  alt="perfaud portfolio review report"
  width="100%"
>

## Start

Python 3.11.9 or newer is required.

```bash
python -m pip install perfaud
perfaud setup ./my_review
perfaud run ./my_review
```

Setup creates one complete, runnable Axys/APX demonstration workspace:

```text
my_review/
  README.md
  perfaud.yaml
  input/
    snapshot_a/
    snapshot_b/
  output/
```

Replace the CSV files in the two input directories, then describe local filenames,
columns, policies, and tolerances in `perfaud.yaml`. Output is always published
atomically to `WORKSPACE/output`; a failed run leaves the last successful output
unchanged.

## What it produces

For each selected report level, `perfaud` writes:

- an Excel review workbook;
- an HTML review report;
- `source_detail.csv` for source-level investigation; and
- `audit_support.zip` with the complete supporting tables and manifest.

The product is local-first: source files and reports remain in the workspace. Its
financial policies are explicit and fail closed when evidence is insufficient.

## Documentation

- [Configuration](docs/configuration.md)
- [Methodology and controls](docs/methodology.md)
- [Python API](docs/python_api.md)
- [Maintenance](docs/maintenance.md)

Detailed Axys/APX evidence and engineering contracts are retained under
[`docs/reference`](docs/reference/).

## License

Copyright John Reynolds. See [LICENSE](LICENSE). Downloading, installing, accessing,
copying, or using `perfaud` constitutes acceptance of that license.

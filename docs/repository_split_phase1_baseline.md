# Repository Split Phase 1 Baseline

## Scope

This baseline records the combined product immediately before source extraction. The
implementation plan was committed first, and no Phase 2 restructuring is included.

| Item | Baseline |
| --- | --- |
| Commit exercised | `ef76ac6a0c4164b6ded7b4e32fae2e05b5519b58` |
| Distribution | `ppar==0.1.7` |
| Python | `3.12.1` |
| Platform | `macOS-26.5.2-arm64-arm-64bit` |
| Machine-readable evidence | `docs/repository_split_phase1_baseline.json` |
| Retained local workspaces | `.cache/repository_split_phase1/workspaces/` |
| Retained wheel | `dist/ppar-0.1.7-py3-none-any.whl` |

The JSON evidence contains exact public exports, CLI help and exit behavior, declared
and installed dependency versions, YAML paths and types, workspace file inventories,
file sizes and SHA-256 digests, CSV schemas and numeric sums, HTML table shapes and
value digests, workbook sheet/value digests, ZIP member schemas and values, and all 136
wheel members.

## Current Interface

- The package root exports `AuditSpecification`, `compare_snapshots`,
  `write_audit_report_bundle`, and `__version__`.
- `ppar.analytics` exports nine calculation and presentation types.
- `ppar.audit` exports nineteen loader, comparison, validation, report, and bundle
  symbols.
- Top-level help advertises `setup` and `audit`; the implemented but hidden
  `analytics` command also executes.
- Setup selects Audit by default and accepts `--analytics`, `--generic-analytics`, and
  `--overwrite`.
- Audit exposes output-directory, title, and format overrides.
- Analytics exposes portfolio, benchmark, frequency, holiday, output, date,
  classification, risk, value, and currency overrides.

The exact help text and process exit codes are in the JSON evidence.

## Current Configuration

| Template | Top-level keys | SHA-256 |
| --- | --- | --- |
| Axys/APX Analytics | `analytics`, `files`, `mappings` | `cd57f15f67b76447ab16259c6702b5140b799f5a7cc890daccfe57756d3d5abe` |
| Axys/APX Audit | `audit`, `data_issues`, impact/reconstruction policy, `files`, `snapshots`, `tolerances`, `transaction_rules` | `c83f536f0cb110a7bc2721efc207f339abd0eddb14d031217e05b99395ca2a65` |
| Demo extract availability | evidence-contract metadata and dataset declarations | `801899bc12a574ad6acf95e1d00df4f9e841cb77da1ec60c6469a0f3ce41eb3b` |

The JSON evidence records every leaf path and resolved YAML value type.

## Representative Workflows and Artifacts

All three setup and first-run workflows passed:

| Workspace | Files | Generated artifacts |
| --- | ---: | ---: |
| Audit | 25 | 10 |
| Axys/APX Analytics | 18 | 11 |
| Generic Analytics | 19 | 11 |

The Audit baseline contains both portfolio and security HTML/XLSX reports,
`audit_support.zip`, `source_detail.csv`, and report READMEs. Both Analytics baselines
contain three HTML tables, eight PNG charts, and identical artifact names.

Selected financial/value checkpoints are:

| Evidence | Rows | Value checkpoint |
| --- | ---: | --- |
| Axys/APX sector overall attribution | 13 | total-attribution display sum `0.1368`; digest `b6f005978381f722d098974ce78e01947033e76563e15c82eab3c2a01186f084` |
| Axys/APX cumulative attribution | 21 | cumulative-total-attribution display sum `0.6984`; digest `6ffdc9b374ddbd4659eeeac801313b670d4740bbbc8ab960618e6010cb773951` |
| Axys/APX risk statistics | 31 | portfolio/benchmark/difference display sums `9399.6261`/`9390.3876`/`6.2125`; digest `caa4cad150cb49d37feb5818fdf25708d288cd374c5d77b2339f77dbf99da7f4` |
| Audit portfolio findings | 191 | digest `eb0dfc0e17bc0a1b85a9febb936bc4b1c3903a27ea7ec459855413fb5175aac3` |
| Audit security findings | 218 | digest `3373ed369f42d22b59a8b30bb79df38fe2f881c37824ded7da364d87c07a9ff6` |
| Audit portfolio performance differences | 26 | performance/estimated/unexplained sums `0.0065407176`/`0.005990717597`/`0.000550000042` |
| Audit security performance differences | 53 | performance/estimated/unexplained sums `-3.9466552681`/`-3.964535412862`/`0.017880145002` |

The JSON evidence is authoritative for complete schemas, numeric sums, hashes, and
rendered-value digests. The ignored local workspace copies retain the actual files for
visual or byte-level investigation.

## Dependency and Package Baseline

Current base dependencies are Polars, OpenPyXL, and PyYAML. The Analytics extra adds
lxml, Matplotlib, NumPy, pandas, PyArrow, and Seaborn. The JSON evidence records the
developer requirements and every installed direct requirement version.

The retained combined wheel is:

```text
dist/ppar-0.1.7-py3-none-any.whl
size: 1,067,196 bytes
sha256: 58a2a464af975da4c87d5c50b2bea437fb14f5c08582a298452029a9f7b93529
members: 136
```

The current release build also produced the historical sdist path:

```text
dist/ppar-0.1.7.tar.gz
size: 1,115,456 bytes
sha256: 313e513c8a743e33d7cda94e04737eded382d14b1204cc67d0b904a0078849f8
```

## Phase 1 Gate Results

### Project gate

`./.venv/bin/python scripts/check_project.py` passed:

- 959 tests in 133.261 seconds;
- mypy: no issues in 104 source files;
- pyright: zero errors and warnings;
- pylint error checks: passed.

### Explicit 500x gate

`./.venv/bin/python scripts/check_scale.py --scale 500` passed:

| Scenario | Result | Time ratio | Warning | Failure |
| --- | --- | ---: | ---: | ---: |
| Analytics large-site 500x | WARN | `1.06x` | `1.05x` | `1.10x` |
| Audit large-site 500x versus 100x | WARN | `5.30x` | `5.25x` | `5.50x` |
| Analytics selected-workload 10x | PASS | `1.75x` | `2.10x` | `2.20x` |
| Analytics long-history 5x | PASS | `0.94x` | `1.58x` | `1.65x` |
| Audit long-history 5x | PASS | `1.67x` | `1.75x` | `2.00x` |

The gate's financial and output-equivalence checks passed. Neither warning crossed its
unchanged failure threshold.

### Release-candidate gate

`./.venv/bin/python scripts/check_release_candidate.py --build --clean-output` passed
after rerunning outside the filesystem sandbox so required headless Chrome execution
was permitted. The first sandboxed attempt stopped with Chrome `SIGABRT`; no product
code or gate was changed.

The passing release candidate completed:

- packaged Audit health;
- portfolio and security report generation and bundle validation;
- both Analytics setup-workspace smokes;
- README image and product PDF rendering;
- the combined 500x gate;
- the nested full project/build/installed-wheel gate;
- direct wheel and sdist creation; and
- Twine validation.

The Yahoo-dependent Generic data refresh was the release runner's documented,
non-default skip and was not required by the deterministic release path.

## Generated-Asset Observation

The release refresh reproduced every tracked README image byte-for-byte. `PPAR.pdf`
retained the same size and renderer but changed its embedded creation/modification time:

```text
committed sha256:   721c7b7f7b995ff7d1732b40465ef1459cdff97f5128065bfd03c3ce6bfb3276
regenerated sha256: 54475f1538b2ab54f93e5d6c89da2cd86d64df8e0145d92c812f52b048131c29
size:               1,252,689 bytes in both files
```

This is generated timestamp drift, not a financial, documentation-content, or image
change. It is recorded because the existing release gate intentionally refreshes the
tracked PDF.

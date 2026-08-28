# perfaud workspace

This self-contained workspace was created with `perfaud setup`. It includes
perfaud-normalized demonstration data modeled on Axys/APX source and report data,
plus the documented Audit configuration in `perfaud.yaml`.

Run the demonstration first, then replace the CSV files with reviewed exports
from your own environment.

## What This Folder Is For

perfaud answers the question: "Why did my reported performance change?"

- **Performance Comparison:** identifies changed portfolio and security
  performance for each time period, quantitatively attributes the differences
  to supported source-data changes, and highlights anything that still needs
  human review.

- **Data Issues:** flags suspicious source-data relationships—including price
  ranges, dividend rates, accrued-interest rates, and missing dividends—that
  may indicate data-quality issues.

## First Run

Run Audit from this directory:

```bash
perfaud run .
```

Open the output files printed by the command. Normal output is written under
`output/portfolio` and, when security-performance files are available,
`output/security`.

## Customizing With Your Own Data

Audit compares two snapshots:

- `input/snapshot_a`: the original or older source-data snapshot.
- `input/snapshot_b`: the newer, corrected, or restated source-data snapshot.

Steps:

1. Replace the CSV data in `input/snapshot_a` with reviewed exports from your own
   environment.
2. Replace the CSV data in `input/snapshot_b` with reviewed exports from your own
   environment.
3. Edit `perfaud.yaml`.
4. Run `perfaud run .`.

### Getting Data from Axys/APX

Start by reviewing the comments under `files:` in `perfaud.yaml`. They classify
every workspace field as **Required**, **Required only when applicable**, or
**Optional**.

Required data is intentionally narrow: it includes only what perfaud needs to
account for a reported return change with supported evidence, within the
configured tolerance. The report labels that outcome as **Fully Explained**.

The most defensible source plan from the currently available Axys/APX evidence
is:

- Portfolio and security reported returns: use a REP performance or attribution
  report. perfaud does not assume that a native performance IMEX object exists.
- Holdings: use an IMEX positions/holdings export or a REP appraisal report.
- Transactions: try IMEX first. If `dp`, `li`, `lo`, or `wd` rows can occur, the
  extract must include the source/destination and special-security context named
  in `perfaud.yaml`; otherwise use REP, a custom report, or another reviewed
  source.
- Security master: needed only when Data Issues filters use
  `security_master.*` qualifiers. Use a reviewed security-information IMEX
  export, security-master report, or equivalent extract and preserve exact case.
- Foreign-currency holdings and transactions: include both reported local and
  base values. perfaud reports the row's implied conversion ratio as reported base
  value divided by reported local value.
- Split factors: optional review information, usually from `split.inf` or an
  equivalent local export.

The demonstration CSV names and headers are perfaud-normalized examples, not
guaranteed native Axys/APX schemas. Confirm the exact local object, report,
field names, date basis, currency basis, and return basis before relying on an
extract.

## Folder Map

```text
./
  README.md
  perfaud.yaml
  input/
    snapshot_a/
      portperf.csv
      holdings.csv
      transactions.csv
      secmast.csv
      secperf.csv
      splits.csv
    snapshot_b/
      portperf.csv
      holdings.csv
      transactions.csv
      secmast.csv
      secperf.csv
      splits.csv
  output/
```

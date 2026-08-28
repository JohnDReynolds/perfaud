# Configuration

Every workspace has exactly one configuration file: `perfaud.yaml`. A run reads that
file only from the requested workspace; it does not search parent directories or infer
another configuration.

The smallest operational shape is:

```yaml
reports:
  - portfolio
  - security

outputs:
  - xlsx
  - html

snapshots:
  a:
    path: input/snapshot_a
  b:
    path: input/snapshot_b

files:
  portfolio_performance:
    path: portperf.csv
    columns:
      portfolio_id: Portfolio Code
      from_date: From Date
      thru_date: Thru Date
      portfolio_return: Portfolio Return
```

`reports` accepts `portfolio` and `security`. `outputs` accepts `xlsx` and `html`.
Both lists are required for a complete workspace run. Output has no configuration
key: it is always `WORKSPACE/output`.

The generated configuration is the canonical working reference for the remaining
file mappings and financially material policies. Keep transaction interpretation,
return reconstruction, tolerances, impact methods, suppressions, causal attribution,
and data-issue populations explicit. Unknown keys, duplicate YAML keys, ambiguous
columns, unsupported policy values, and missing required inputs fail validation.

Paths are resolved relative to `perfaud.yaml`. Intentional external input paths are
supported, but output can never be redirected outside the workspace.

# Python API

The root API intentionally contains one complete workflow:

```python
from perfaud import run

result = run("./my_review")
print(result.output_directory)
for artifact in result.artifacts:
    print(artifact)
```

`run(workspace=".")` validates and executes the workspace, atomically publishes its
output, and returns a frozen `RunResult` with exactly `workspace`, `output_directory`,
and `artifacts`.

Focused engineering APIs live in their owning modules:

```python
from perfaud.config import load_config, settings
from perfaud.report import write_report_bundle
from perfaud.runner import ComparisonViews
from perfaud.specification import Specification
from perfaud.workspace import RunResult
```

These focused interfaces are useful for controlled integrations and tests. The root
`run()` service remains the supported way to execute a complete workspace and obtain
the same artifact inventory as `perfaud run`.

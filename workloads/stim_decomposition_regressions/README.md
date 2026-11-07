# Stim decomposition regression DEMs

Regression fixtures for the 32-bit shift bug in Stim's `decompose_errors=True`
path (Stim PR #1123, merged 16 Oct 2026): detector targets at index 32 and
above could be dropped. The latest tagged Stim release (v1.16.0) predates the
fix, so downstream consumers must use patched Stim main for affected workflows.

These DEMs are generated with `decompose_errors=True` and contain detector
counts well above 32 (40 / 120 / 336), so that any 32-bit indexing
regression in emlint or in a Stim-based pipeline is exercised.

Regenerate with:

```python
import stim
for gen, d, r, fname in [...]:
    c = stim.Circuit.generated(gen, distance=d, rounds=r, ...)
    dem = c.detector_error_model(decompose_errors=True)
    open(fname, "w").write(str(dem))
```

See: https://github.com/quantumlib/Stim/pull/1123
EOF
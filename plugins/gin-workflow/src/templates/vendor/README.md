# Vendored libraries

## mermaid.min.js

- Source: https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js
- Version: 11.4.1
- SHA-384 (base64): `rbtjAdnIQE/aQJGEgXrVUlMibdfTSa4PQju4HDhN3sR2PmaKFzhEafuePsl9H/9I`
- Licence: MIT (Mermaid's licence)
- Why: the SRS and explain pages embed it, so their diagrams draw and print offline.

Never edit the file. To upgrade, replace it, update `MERMAID_SHA384` in
`scripts/workflow_core/specs_export.py` and the version and hash above, then run
`tests/workflow_core/test_specs_export.py` and `tests/workflow_core/test_specs_explain.py`.

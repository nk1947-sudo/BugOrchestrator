# shared-schema

JSON Schema (draft-07) definitions for the four core resources that cross
service boundaries: `Target`, `Scan`, `Finding`, `Approval`. These mirror
`services/api/src/api/models.py` and `schemas.py` and exist as a
language-agnostic reference contract - services/api's FastAPI/Pydantic
schemas remain the source of runtime validation truth; these files are for
external consumers (docs, future non-Python clients, contract tests) that
need the shape without importing Python.

If you change a field on the API side, update the matching `.schema.json`
here in the same change.

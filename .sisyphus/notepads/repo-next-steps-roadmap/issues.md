# Issues

- `python -m src.business_analyzer_combined --help` initially failed due a pre-existing `IndentationError` in `DecimalEncoder.default` (duplicate malformed method definitions around line 73).
- Applied the minimum compatibility fix by collapsing duplicate malformed method declarations into one valid `default` method so baseline CLI smoke can execute.

- Initial quality-command run failed due invalid TOML escaping in `pyproject.toml` and broken pipx shims for `isort`/`flake8`; both were corrected by fixing TOML regex quoting and reinstalling CLI tools in the active Python environment.
- `src/contracts/row_contracts.py` contained trailing NUL bytes, which caused tooling to treat it as binary; rewriting the file to clean UTF-8 text fixed `Read`/analysis compatibility.
- `mypy` with Python 3.9 target rejected `typing.TypeAlias` and bare `|` type-alias syntax; switching to `typing_extensions.TypeAlias` with a quoted alias resolved the compatibility error.
- New data-access modules initially used Python 3.10 union syntax (`|`), which failed `mypy` under the repo's Python 3.9 target; replacing with `typing.Optional[...]` restored compatibility.
- Report smoke generation emits expected matplotlib font warnings for emoji glyphs in report text; this is cosmetic-only and does not impact file generation, report path contract, or test pass/fail.
- `mypy src` initially failed in the provider factory because class statements cannot use runtime class variables as base types; replaced those with `type(...)` dynamic class construction to preserve behavior and satisfy typing.
- Multiple legacy docs still reference `business_analyzer_combined.py` as the default implementation surface, so architecture alignment required targeted wording changes to prevent future feature additions in the monolith.
- Resolved flake8 blockers in src/data_access/banco_datos.py (E501 line wrap) and tests/test_data_access_boundaries.py (long XML line). Visualization F841 blockers pending adjustment in src/reporting/visualization.py; plan to clean up by removing or obsoleting unused bars plotting. 

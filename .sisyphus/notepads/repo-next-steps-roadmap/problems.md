# Problems

- `src/business_analyzer_combined.py` still has a large set of pre-existing basedpyright errors outside this task scope; they do not block runtime/tests/mypy but prevent a fully clean LSP state for that legacy module.
- Task 6 kept analyzer edits minimal to avoid widening this legacy type-debt surface; new reporting modules are clean, but facade file still inherits existing basedpyright error backlog.
- Legacy analysis docs (`START_HERE`/`QUICK_START_IMPROVEMENTS`) include historical monolith-oriented guidance, so alignment work must be incremental to avoid rewriting unrelated product messaging in this task.

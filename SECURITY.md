# Security

## Credentials

Database, Magento, API, and other secrets belong in a local `.env` file (or the
host secret store). Never commit them.

- Copy `.env.example` to `.env` and fill in values locally.
- `.env` is gitignored. Do not add allowlist exceptions for secret files.
- Docs and scripts must use placeholders such as `<DB_SERVER>`, `<DB_USER>`,
  and `<DB_PASSWORD>`, or load values with `os.getenv(...)`.

More detail: [docs/SECURITY.md](docs/SECURITY.md).

## Secret scanning

Gitleaks runs via pre-commit (see `.pre-commit-config.yaml` and `.gitleaks.toml`)
to block new credential literals on the working tree.

```bash
pre-commit install
pre-commit run gitleaks --all-files
```

## History

This repository's git history may still contain old secrets that were committed
before the HEAD cleanup. Removing them from the current tree does **not** rotate
them or purge history.

The repository owner should:

1. Rotate SQL Server, Magento, and any other credentials that were ever committed.
2. Rewrite history with `git filter-repo` (or equivalent) if those historical
   copies must be purged.

This cleanup does not rotate passwords and does not rewrite history.

## Reporting issues

Do not open a public issue that includes secrets. Contact the maintainer
privately (see README).

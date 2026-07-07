"""Resolve authoritative product attributes from master data vs banco_datos."""

from __future__ import annotations

from typing import Optional

BAD_ATTR_VALUES = {
    "",
    "S/I",
    "S.I",
    "SIN PROVEEDOR",
    "N/A",
    ".",
    "SIN IVA",
    "NA",
}


def is_bad_attr_value(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    return text.upper() in BAD_ATTR_VALUES or len(text) <= 2


def resolve_effective_marca(
    bd_marca: object,
    producto_marca: object,
) -> Optional[str]:
    """Prefer productos_adicional.producto_marca over banco_datos.marca."""
    for candidate in (producto_marca, bd_marca):
        if is_bad_attr_value(candidate):
            continue
        return str(candidate).strip()
    return None


def effective_marca_sql(alias: str = "bd", pa_alias: str = "pa") -> str:
    """SQL expression: authoritative marca with master-first precedence."""
    master = (
        f"NULLIF(LTRIM(RTRIM({pa_alias}.producto_marca COLLATE DATABASE_DEFAULT)), '')"
    )
    txn = f"NULLIF(LTRIM(RTRIM({alias}.marca COLLATE DATABASE_DEFAULT)), '')"
    combined = f"COALESCE({master}, {txn}, '')"
    return f"""
        CASE
          WHEN UPPER(LTRIM(RTRIM({combined}))) IN (
              '', 'S/I', 'S.I', 'SIN PROVEEDOR', 'N/A', '.', 'SIN IVA', 'NA'
          ) OR LEN(LTRIM(RTRIM({combined}))) <= 2
          THEN NULL
          ELSE LTRIM(RTRIM(COALESCE({master}, {txn})))
        END
        """.strip()

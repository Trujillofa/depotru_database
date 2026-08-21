"""Assemble a customer-facing summary from selected invoice numbers."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from business_analyzer.core.database import Database, qualified_sb_table
from depotru_kernel.documents import excluded_document_sql_in_list

MAX_INVOICES = 40
MIN_INVOICE_DIGITS = 5

SEDE_PUBLIC_NAMES: Dict[str, str] = {
    "FED": "Almacén Principal",
    "FEF": "Sika Center",
    "FET": "Calle 5",
}

_INVOICE_RE = re.compile(r"\d{" + str(MIN_INVOICE_DIGITS) + r",10}")


def parse_invoice_numbers(text: str) -> List[int]:
    """Extract unique invoice numbers from free text (commas, newlines, codes)."""
    seen: set[int] = set()
    out: List[int] = []
    for match in _INVOICE_RE.finditer(text or ""):
        value = int(match.group(0))
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        out.append(value)
        if len(out) >= MAX_INVOICES:
            break
    return out


def public_sede_name(document_code: Any) -> str:
    code = str(document_code or "").strip().upper()
    return SEDE_PUBLIC_NAMES.get(code, "Sede comercial")


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(Decimal(str(value)))
    except (TypeError, ValueError, Exception):
        return 0


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def assemble_invoice_summary(
    *,
    requested: Sequence[int],
    line_rows: Sequence[Mapping[str, Any]],
    cartera_rows: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Build a customer-facing report dict from already-fetched rows."""
    requested_list = [int(n) for n in requested]
    cartera_index: Dict[tuple, Mapping[str, Any]] = {}
    for row in cartera_rows or []:
        tipo = str(row.get("documento_tipo") or "").strip().upper()
        numero = _as_int(row.get("documento_numero"))
        if numero:
            cartera_index[(tipo, numero)] = row
            cartera_index.setdefault(("", numero), row)

    grouped: Dict[tuple, List[Mapping[str, Any]]] = defaultdict(list)
    for row in line_rows:
        key = (
            str(row.get("DocumentosCodigo") or "").strip().upper(),
            _as_int(row.get("NumeroDocumento")),
        )
        if key[1]:
            grouped[key].append(row)

    invoices: List[Dict[str, Any]] = []
    found_numbers: set[int] = set()
    for (doc_code, numero), rows in sorted(
        grouped.items(),
        key=lambda item: (_as_date(item[1][0].get("Fecha")) or date.min, item[0][1]),
    ):
        found_numbers.add(numero)
        first = rows[0]
        lines = []
        total_sin = 0.0
        total_mas = 0.0
        qty = 0.0
        for raw in rows:
            cantidad = _as_float(raw.get("Cantidad"))
            sin = _as_float(raw.get("TotalSinIva"))
            mas = _as_float(raw.get("TotalMasIva"))
            iva_pct = _as_float(raw.get("Iva"))
            unit = sin / cantidad if cantidad else 0.0
            lines.append(
                {
                    "codigo": str(raw.get("ArticulosCodigo") or "").strip(),
                    "nombre": _clean(raw.get("ArticulosNombre")),
                    "categoria": _clean(raw.get("categoria")) or "OTROS",
                    "cantidad": cantidad,
                    "unitario_sin_iva": unit,
                    "total_sin_iva": sin,
                    "total_mas_iva": mas,
                    "iva_pct": iva_pct,
                    "iva_valor": mas - sin,
                    "exento": abs(iva_pct) < 0.01,
                }
            )
            total_sin += sin
            total_mas += mas
            qty += cantidad
        car = cartera_index.get((doc_code, numero)) or cartera_index.get(("", numero))
        vence = _as_date((car or {}).get("documento_fecha_vencimiento"))
        saldo = _as_float((car or {}).get("total")) if car else total_mas
        invoices.append(
            {
                "codigo": doc_code,
                "sede": public_sede_name(doc_code),
                "numero": numero,
                "fecha": (_as_date(first.get("Fecha")) or date.min).isoformat(),
                "vence": vence.isoformat() if vence else None,
                "detalle": _clean(first.get("Detalle")),
                "dias_credito": _as_int(first.get("DiasCredito")),
                "vendedor": _clean(first.get("VendedorFactura")),
                "terceros_id": first.get("TercerosID"),
                "nit": str(first.get("TercerosIdentificacion") or "").strip(),
                "cliente": _clean(first.get("TercerosNombres")),
                "lineas": len(lines),
                "cantidad": qty,
                "total_sin_iva": total_sin,
                "iva": total_mas - total_sin,
                "total_mas_iva": total_mas,
                "saldo": saldo,
                "pagado": bool(
                    car
                    and (
                        car.get("documento_fecha_cancela")
                        or _as_float(car.get("total")) == 0
                    )
                ),
                "corriente": _as_float((car or {}).get("corriente")),
                "vencido": _as_float((car or {}).get("vencido")),
                "lines": lines,
            }
        )

    missing = [n for n in requested_list if n not in found_numbers]

    by_customer: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for inv in invoices:
        by_customer[
            (inv.get("terceros_id"), inv.get("nit"), inv.get("cliente"))
        ].append(inv)

    customers = []
    for (tid, nit, name), invs in by_customer.items():
        customers.append(
            {
                "terceros_id": tid,
                "nit": nit,
                "name": name,
                "invoices": [i["numero"] for i in invs],
                "total_mas_iva": sum(i["total_mas_iva"] for i in invs),
                "saldo": sum(i["saldo"] for i in invs),
            }
        )
    customers.sort(key=lambda c: -c["total_mas_iva"])
    multiple = len(customers) > 1
    primary = customers[0] if customers else {"name": "", "nit": ""}

    obras = sorted({inv["detalle"] for inv in invoices if inv.get("detalle")})
    obra = obras[0] if len(obras) == 1 else None

    families: Dict[str, float] = defaultdict(float)
    sku_map: Dict[str, Dict[str, Any]] = {}
    for inv in invoices:
        for line in inv["lines"]:
            families[line["categoria"]] += line["total_mas_iva"]
            sku = line["codigo"] or line["nombre"]
            entry = sku_map.setdefault(
                sku,
                {
                    "codigo": line["codigo"],
                    "nombre": line["nombre"],
                    "cantidad": 0.0,
                    "total_sin_iva": 0.0,
                    "facturas": set(),
                },
            )
            entry["cantidad"] += line["cantidad"]
            entry["total_sin_iva"] += line["total_sin_iva"]
            entry["facturas"].add(inv["numero"])

    repeated = []
    for entry in sku_map.values():
        facts = sorted(entry["facturas"])
        if len(facts) < 2:
            continue
        repeated.append(
            {
                "codigo": entry["codigo"],
                "nombre": entry["nombre"],
                "facturas": facts,
                "cantidad": entry["cantidad"],
                "total_sin_iva": entry["total_sin_iva"],
            }
        )
    repeated.sort(key=lambda r: -r["total_sin_iva"])

    family_rows = [
        {"categoria": name, "total_mas_iva": amount}
        for name, amount in sorted(families.items(), key=lambda kv: -kv[1])
    ]

    total_sin = sum(i["total_sin_iva"] for i in invoices)
    total_mas = sum(i["total_mas_iva"] for i in invoices)
    exento = sum(
        line["total_sin_iva"]
        for inv in invoices
        for line in inv["lines"]
        if line["exento"]
    )
    saldo = sum(i["saldo"] for i in invoices)

    return {
        "requested": requested_list,
        "missing": missing,
        "multiple_customers": multiple,
        "customer": {"name": primary.get("name", ""), "nit": primary.get("nit", "")},
        "customers": customers,
        "obra": obra,
        "obras": obras,
        "invoices": invoices,
        "families": family_rows,
        "repeated": repeated,
        "summary": {
            "invoice_count": len(invoices),
            "line_count": sum(i["lineas"] for i in invoices),
            "total_sin_iva": total_sin,
            "base_gravada": total_sin - exento,
            "exento": exento,
            "iva": total_mas - total_sin,
            "total_mas_iva": total_mas,
            "saldo": saldo,
            "pagos": max(total_mas - saldo, 0.0),
        },
    }


class InvoiceSummaryRunner:
    """Load selected invoices from SmartBusiness and assemble the summary."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        sb_database: Optional[str] = None,
        document_code: Optional[str] = None,
    ) -> None:
        self.db = db or Database()
        self.sb_database = sb_database
        code = str(document_code or "").strip().upper()
        self.document_code = code or None

    def _execute(
        self, sql: str, params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        self.db.connect()
        rows = cast(
            List[Dict[str, Any]],
            self.db.execute_query(sql, params),
        )
        return [dict(row) for row in rows]

    def fetch_lines(self, numbers: Sequence[int]) -> List[Dict[str, Any]]:
        if not numbers:
            return []
        table = qualified_sb_table("banco_datos", self.sb_database)
        excluded = excluded_document_sql_in_list()
        placeholders = ",".join(["%s"] * len(numbers))
        sql = f"""
SELECT
    DocumentosCodigo, DocumentosNombre, NumeroDocumento, Fecha,
    TercerosID, TercerosIdentificacion, TercerosNombres, DiasCredito,
    VendedorFactura, ArticulosCodigo, ArticulosNombre, categoria,
    Cantidad, TotalSinIva, TotalMasIva, Iva
FROM {table}
WHERE NumeroDocumento IN ({placeholders})
  AND DocumentosCodigo NOT IN ({excluded})
""".strip()
        params: List[Any] = list(numbers)
        if self.document_code:
            sql += " AND DocumentosCodigo = %s"
            params.append(self.document_code)
        sql += " ORDER BY Fecha, NumeroDocumento, ArticulosNombre"
        return self._execute(sql, tuple(params))

    def fetch_headers(self, numbers: Sequence[int]) -> List[Dict[str, Any]]:
        """Invoice-level Detalle from v_banco_facturas when available."""
        if not numbers:
            return []
        table = qualified_sb_table("v_banco_facturas", self.sb_database)
        excluded = excluded_document_sql_in_list()
        placeholders = ",".join(["%s"] * len(numbers))
        sql = f"""
SELECT DocumentosCodigo, NumeroDocumento, Detalle, DiasCredito
FROM {table}
WHERE NumeroDocumento IN ({placeholders})
  AND DocumentosCodigo NOT IN ({excluded})
""".strip()
        params: List[Any] = list(numbers)
        if self.document_code:
            sql += " AND DocumentosCodigo = %s"
            params.append(self.document_code)
        try:
            return self._execute(sql, tuple(params))
        except Exception:
            return []

    def fetch_cartera(self, numbers: Sequence[int]) -> List[Dict[str, Any]]:
        if not numbers:
            return []
        table = qualified_sb_table("banco_cartera", self.sb_database)
        placeholders = ",".join(["%s"] * len(numbers))
        sql = f"""
SELECT
    documento_tipo, documento_numero, documento_fecha_vencimiento,
    documento_fecha_cancela, debitos, creditos, total, corriente,
    vencido, dias_vencidos
FROM {table}
WHERE documento_numero IN ({placeholders})
""".strip()
        params: List[Any] = list(numbers)
        if self.document_code:
            sql += " AND LTRIM(RTRIM(documento_tipo)) = %s"
            params.append(self.document_code)
        try:
            return self._execute(sql, tuple(params))
        except Exception:
            return []

    def build_report(self, numbers: Sequence[int]) -> Dict[str, Any]:
        lines = self.fetch_lines(numbers)
        headers = {
            (
                _clean(h.get("DocumentosCodigo")).upper(),
                _as_int(h.get("NumeroDocumento")),
            ): h
            for h in self.fetch_headers(numbers)
        }
        if headers:
            enriched = []
            for row in lines:
                key = (
                    str(row.get("DocumentosCodigo") or "").strip().upper(),
                    _as_int(row.get("NumeroDocumento")),
                )
                extra = headers.get(key) or {}
                merged = dict(row)
                if extra.get("Detalle") and not merged.get("Detalle"):
                    merged["Detalle"] = extra.get("Detalle")
                if extra.get("DiasCredito") is not None:
                    merged["DiasCredito"] = extra.get("DiasCredito")
                enriched.append(merged)
            lines = enriched
        cartera = self.fetch_cartera(numbers)
        return assemble_invoice_summary(
            requested=numbers,
            line_rows=lines,
            cartera_rows=cartera,
        )

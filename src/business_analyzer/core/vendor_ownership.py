"""Commercial vendor code ownership card and purity checks.

Source of truth for:
- Official Factura→code owners (budget fallback when Asignado empty)
- Display names on presupuesto rows
- Field hygiene / purity flags (multi-name, wrong-home, handoff)

Budget attribution priority remains in presupuesto_2026.attribute_sale:
  Asignado > Factura owner map > vendedor_codigo > POOL
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)

# Built-in merge map: source code → canonical meta code
DEFAULT_CODE_MERGES: Dict[str, str] = {
    "123": "162",  # William Hernando Quintero (Sika)
    "133": "162",
}

# Commercial owners for budget when only VendedorFactura is available.
# Huber transferred credit customers to Betsy (163). Factura may still say
# HUBER on those rows — Asignado 163-BETSY must win. Factura→044 is only a
# fallback when Asignado is empty (Huber's own residual book on 044).
OFFICIAL_FACTURA_OWNERS: Dict[str, str] = {
    "HUBER SANTIAGO ENCISO": "044",
    "OLGA LUCIA TORRES": "131",
    "WILLIAM HERNANDO QUINTERO G": "162",
    "WILLIAM HERNANDO QUINTERO": "162",
    "CRISTIAN GUSTAVO": "164",
    "DANIEL ENRIQUE CAICEDO": "095",
    "JULIAN ANDRES PINEDA": "102",
    "CARLOS EFREY PASCUAS": "003",
    "DIANA PATRICIA CULMA": "106",
    "BETSY GUZMAN": "163",
    "OSCAR IVAN POLANIA GARCIA": "035",
    "FELIPE RAMIREZ": "116",
    "ANDRES FELIPE VARGAS JOVEL": "057",
    "ANDRES MAURICIO CORTEZ CULMA": "089",
    "YULI ALEJANDRA HIGUERA": "060",
    "LUIS ESTEBAN MEDINA": "140",
    "JAVIER ANDRES APACHE": "130",
    "LINA ISABEL TOVAR": "159",
}

# Preferred display names on presupuesto rows
OFFICIAL_CODE_NAMES: Dict[str, str] = {
    "000": "SIN COMISION",
    "003": "CARLOS EFREY PASCUAS",
    "035": "OSCAR IVAN POLANIA GARCIA",
    "044": "HUBER SANTIAGO ENCISO",
    "057": "ANDRES FELIPE VARGAS JOVEL",
    "060": "YULI ALEJANDRA HIGUERA",
    "089": "ANDRES MAURICIO CORTEZ CULMA",
    "095": "DANIEL ENRIQUE CAICEDO",
    "102": "JULIAN ANDRES PINEDA",
    "106": "DIANA PATRICIA CULMA",
    "116": "FELIPE RAMIREZ",
    "130": "JAVIER ANDRES APACHE",
    "131": "OLGA LUCIA TORRES",
    "140": "LUIS ESTEBAN MEDINA",
    "159": "LINA ISABEL TOVAR",
    "162": "WILLIAM HERNANDO QUINTERO G",
    "163": "BETSY GUZMAN",
    "164": "CRISTIAN GUSTAVO",
}

# Post-merge active meta roster (2026-06 last complete month)
ACTIVE_META_CODES_2026: Tuple[str, ...] = tuple(sorted(OFFICIAL_CODE_NAMES.keys()))

# Material COP threshold for purity flags (ignore noise)
DEFAULT_MATERIAL_THRESHOLD = 1_000_000.0

# People who must not book on listed foreign codes
WRONG_HOME_RULES: Tuple[Tuple[str, str, FrozenSet[str]], ...] = (
    # (name substring, home_code, forbidden_codes)
    ("DANIEL ENRIQUE CAICEDO", "095", frozenset({"044"})),
    ("JULIAN ANDRES PINEDA", "102", frozenset({"044"})),
    ("FELIPE RAMIREZ", "116", frozenset({"044"})),
    ("CARLOS EFREY PASCUAS", "003", frozenset({"131"})),
    ("DIANA PATRICIA CULMA", "106", frozenset({"131"})),
)


@dataclass(frozen=True)
class OwnerRule:
    """Field ownership rule for one vendor code."""

    code: str
    owner: str
    preferred_sedes: FrozenSet[str] = frozenset()
    flags: FrozenSet[str] = frozenset()
    notes: str = ""
    allowed_names: FrozenSet[str] = frozenset()

    def allowed_factura_names(self) -> FrozenSet[str]:
        if self.allowed_names:
            return self.allowed_names
        if self.owner:
            return frozenset({self.owner})
        return frozenset()


def _rule(
    code: str,
    owner: str,
    *,
    sedes: Iterable[str] = (),
    flags: Iterable[str] = (),
    notes: str = "",
    allowed: Iterable[str] = (),
) -> OwnerRule:
    return OwnerRule(
        code=code,
        owner=owner,
        preferred_sedes=frozenset(sedes),
        flags=frozenset(flags),
        notes=notes,
        allowed_names=frozenset(allowed) if allowed else frozenset(),
    )


# Confirmed commercial ownership card (all 18 active meta codes)
OWNER_CARD: Dict[str, OwnerRule] = {
    "000": _rule(
        "000",
        "SIN COMISION",
        notes="Ops bucket, not a salesperson target",
    ),
    "003": _rule(
        "003",
        "CARLOS EFREY PASCUAS",
        sedes={"FED"},
        notes="Prefer 003; do not book Carlos on 131",
    ),
    "035": _rule("035", "OSCAR IVAN POLANIA GARCIA", sedes={"FED"}),
    "044": _rule(
        "044",
        "HUBER SANTIAGO ENCISO",
        sedes={"FED"},
        flags={"no_multi_name"},
        notes="Huber own remaining book only; Daniel→095, Julian→102",
    ),
    "057": _rule("057", "ANDRES FELIPE VARGAS JOVEL", sedes={"FED"}),
    "060": _rule("060", "YULI ALEJANDRA HIGUERA", sedes={"FED"}),
    "089": _rule("089", "ANDRES MAURICIO CORTEZ CULMA", sedes={"FED"}),
    "095": _rule(
        "095",
        "DANIEL ENRIQUE CAICEDO",
        sedes={"FED", "FEF"},
        notes="Do not use 044 for Daniel",
    ),
    "102": _rule(
        "102",
        "JULIAN ANDRES PINEDA",
        sedes={"FED"},
        notes="Prefer 102 over booking on 044",
    ),
    "106": _rule(
        "106",
        "DIANA PATRICIA CULMA",
        sedes={"FED"},
        notes="Do not spill onto 131",
    ),
    "116": _rule("116", "FELIPE RAMIREZ", sedes={"FED"}),
    "130": _rule("130", "JAVIER ANDRES APACHE", sedes={"FED"}),
    "131": _rule(
        "131",
        "OLGA LUCIA TORRES",
        sedes={"FET"},
        flags={"no_multi_name", "olga_calle5"},
        notes="Olga Calle 5 only; Carlos→003, Diana→106",
    ),
    "140": _rule("140", "LUIS ESTEBAN MEDINA", sedes={"FED"}),
    "159": _rule("159", "LINA ISABEL TOVAR", sedes={"FED"}),
    "162": _rule(
        "162",
        "WILLIAM HERNANDO QUINTERO G",
        sedes={"FEF"},
        notes="Sika canonical; 123/133 merged into 162",
        allowed={"WILLIAM HERNANDO QUINTERO G", "WILLIAM HERNANDO QUINTERO"},
    ),
    "163": _rule(
        "163",
        "BETSY GUZMAN",
        sedes={"FED"},
        flags={"credit_handoff_from_huber"},
        notes=(
            "Includes credit book Huber transferred to Betsy. "
            "Asignado 163 wins even if Factura still says HUBER."
        ),
        allowed={"BETSY GUZMAN", "HUBER SANTIAGO ENCISO"},  # Factura lag OK
    ),
    "164": _rule(
        "164",
        "CRISTIAN GUSTAVO",
        sedes={"FEF"},
        notes="Sika; keep separate from William",
    ),
}


@dataclass
class PurityFinding:
    severity: str  # error | warn | info
    code: str
    check: str
    message: str
    sales: float = 0.0
    detail: str = ""


@dataclass
class PurityReport:
    period_label: str
    findings: List[PurityFinding] = field(default_factory=list)
    by_code_sales: Dict[str, float] = field(default_factory=dict)
    by_code_names: Dict[str, Dict[str, float]] = field(default_factory=dict)
    merge_orphan_sales: Dict[str, float] = field(default_factory=dict)
    handoff_ok_sales: float = 0.0
    material_threshold: float = DEFAULT_MATERIAL_THRESHOLD

    @property
    def errors(self) -> List[PurityFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warns(self) -> List[PurityFinding]:
        return [f for f in self.findings if f.severity == "warn"]


@dataclass(frozen=True)
class SalesSlice:
    """Aggregated sales slice for purity analysis."""

    code: Optional[str]
    factura_name: str
    asignado: Optional[str]
    sede: str  # DocumentosCodigo branch: FED/FET/FEF/...
    sales: float


def normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(str(name).upper().split())


def normalize_code(code: Optional[str]) -> Optional[str]:
    if code is None:
        return None
    c = str(code).strip()
    return c or None


def parse_asignado_code(asignado: Optional[str]) -> Optional[str]:
    """Extract leading code from values like ``044-HUBER SANTIAGO ENCISO``."""
    import re

    if not asignado:
        return None
    m = re.match(r"^\s*(\d+)\s*[-–]", str(asignado))
    if not m:
        return None
    return normalize_code(m.group(1))


def official_owner_for_factura(name: Optional[str]) -> Optional[str]:
    """Commercial owner code from VendedorFactura (budget rule overrides)."""
    n = normalize_name(name)
    if not n:
        return None
    if n in OFFICIAL_FACTURA_OWNERS:
        return OFFICIAL_FACTURA_OWNERS[n]
    for key, code in OFFICIAL_FACTURA_OWNERS.items():
        if key in n or n in key:
            return code
    return None


def is_huber_to_betsy_handoff(
    *,
    factura_name: Optional[str],
    asignado: Optional[str],
) -> bool:
    """True when Asignado is Betsy (163) and Factura still says Huber."""
    ac = parse_asignado_code(asignado)
    if ac != "163":
        return False
    n = normalize_name(factura_name)
    return "HUBER" in n


def analyze_purity(
    slices: Sequence[SalesSlice],
    *,
    period_label: str = "",
    material_threshold: float = DEFAULT_MATERIAL_THRESHOLD,
    owner_card: Optional[Mapping[str, OwnerRule]] = None,
    merges: Optional[Mapping[str, str]] = None,
) -> PurityReport:
    """Analyze vendor-code hygiene from aggregated sales slices.

    Known non-violations:
    - Factura HUBER + Asignado 163-BETSY (credit handoff)
    """
    card = owner_card or OWNER_CARD
    merges = merges or DEFAULT_CODE_MERGES
    report = PurityReport(
        period_label=period_label,
        material_threshold=material_threshold,
    )

    by_code_names: Dict[str, Dict[str, float]] = {}
    by_code_sales: Dict[str, float] = {}
    by_code_sede_name: Dict[str, Dict[Tuple[str, str], float]] = {}
    merge_orphans: Dict[str, float] = {}
    handoff_ok = 0.0

    for s in slices:
        sales = float(s.sales or 0.0)
        if sales == 0:
            continue
        raw_code = normalize_code(s.code)
        name = normalize_name(s.factura_name)
        sede = (s.sede or "").strip().upper()
        asignado = s.asignado

        if raw_code is not None and raw_code in merges:
            merge_orphans[raw_code] = merge_orphans.get(raw_code, 0.0) + sales

        if is_huber_to_betsy_handoff(factura_name=name, asignado=asignado):
            handoff_ok += sales
            # Attribute purity view to Betsy book (163), not Huber dual-identity
            code_key = "163"
        elif raw_code is None:
            continue
        else:
            code_key = raw_code

        by_code_sales[code_key] = by_code_sales.get(code_key, 0.0) + sales
        by_code_names.setdefault(code_key, {})
        by_code_names[code_key][name or "(sin nombre)"] = (
            by_code_names[code_key].get(name or "(sin nombre)", 0.0) + sales
        )
        by_code_sede_name.setdefault(code_key, {})
        key = (sede or "?", name or "(sin nombre)")
        by_code_sede_name[code_key][key] = (
            by_code_sede_name[code_key].get(key, 0.0) + sales
        )

    report.by_code_sales = by_code_sales
    report.by_code_names = by_code_names
    report.merge_orphan_sales = merge_orphans
    report.handoff_ok_sales = handoff_ok

    # Multi-name on restricted codes
    for code, rule in card.items():
        if "no_multi_name" not in rule.flags:
            continue
        names = by_code_names.get(code) or {}
        allowed = {normalize_name(n) for n in rule.allowed_factura_names()}
        material_others = {
            n: v
            for n, v in names.items()
            if v >= material_threshold and normalize_name(n) not in allowed
        }
        if material_others:
            detail = ", ".join(
                f"{n}: ${v:,.0f}"
                for n, v in sorted(material_others.items(), key=lambda x: -x[1])
            )
            report.findings.append(
                PurityFinding(
                    severity="error",
                    code=code,
                    check="multi_name",
                    message=(
                        f"Code {code} ({rule.owner}) has material Factura names "
                        f"other than owner"
                    ),
                    sales=sum(material_others.values()),
                    detail=detail,
                )
            )

    # Wrong-home bookings
    for name_key, home, forbidden in WRONG_HOME_RULES:
        nk = normalize_name(name_key)
        for fcode in forbidden:
            names = by_code_names.get(fcode) or {}
            for n, v in names.items():
                if v < material_threshold:
                    continue
                nn = normalize_name(n)
                if nk in nn or nn in nk:
                    report.findings.append(
                        PurityFinding(
                            severity="error",
                            code=fcode,
                            check="wrong_home",
                            message=(
                                f"{name_key} booked ${v:,.0f} on {fcode}; "
                                f"home code is {home}"
                            ),
                            sales=v,
                            detail=f"Factura={n}",
                        )
                    )

    # Sede preference warnings for flagged codes
    for code, rule in card.items():
        if not rule.preferred_sedes:
            continue
        if code not in by_code_sede_name:
            continue
        off_sede: Dict[str, float] = {}
        for (sede, _name), v in by_code_sede_name[code].items():
            if (
                sede
                and sede not in rule.preferred_sedes
                and sede in {"FED", "FET", "FEF"}
            ):
                off_sede[sede] = off_sede.get(sede, 0.0) + v
        material_off = {s: v for s, v in off_sede.items() if v >= material_threshold}
        if material_off and (
            "no_multi_name" in rule.flags or "olga_calle5" in rule.flags
        ):
            detail = ", ".join(
                f"{s}: ${v:,.0f}"
                for s, v in sorted(material_off.items(), key=lambda x: -x[1])
            )
            preferred = "/".join(sorted(rule.preferred_sedes))
            report.findings.append(
                PurityFinding(
                    severity="warn",
                    code=code,
                    check="sede",
                    message=(
                        f"Code {code} has material sales outside preferred sede(s) "
                        f"{preferred}"
                    ),
                    sales=sum(material_off.values()),
                    detail=detail,
                )
            )

    # Merge orphans (123/133 still used while meta is 162)
    for src, total in merge_orphans.items():
        if total < material_threshold:
            if total > 0:
                report.findings.append(
                    PurityFinding(
                        severity="info",
                        code=src,
                        check="merge_orphan",
                        message=(
                            f"Code {src} still has sales ${total:,.0f}; "
                            f"meta is merged into {merges.get(src, '?')}"
                        ),
                        sales=total,
                    )
                )
            continue
        report.findings.append(
            PurityFinding(
                severity="warn",
                code=src,
                check="merge_orphan",
                message=(
                    f"Code {src} still has material sales ${total:,.0f}; "
                    f"prefer {merges.get(src, '?')} (William merge)"
                ),
                sales=total,
            )
        )

    if abs(handoff_ok) >= material_threshold:
        report.findings.append(
            PurityFinding(
                severity="info",
                code="163",
                check="handoff_ok",
                message=(
                    f"Huber→Betsy handoff pattern OK: Asignado 163 + Factura HUBER "
                    f"net ${handoff_ok:,.0f} (not a dual-code violation; "
                    f"negatives = returns/credit notes)"
                ),
                sales=handoff_ok,
            )
        )

    # Sort findings: error, warn, info
    order = {"error": 0, "warn": 1, "info": 2}
    report.findings.sort(key=lambda f: (order.get(f.severity, 9), f.code, f.check))
    return report


def render_purity_markdown(
    report: PurityReport,
    *,
    enero_smoke: Optional[Mapping[str, object]] = None,
) -> str:
    """Render purity report as Spanish field-friendly markdown."""
    lines: List[str] = [
        f"# Vendor code purity — {report.period_label or 'periodo'}",
        "",
        f"- **Material threshold:** ${report.material_threshold:,.0f}".replace(
            ",", "."
        ),
        f"- **Handoff OK (Asignado 163 + Factura Huber):** "
        f"${report.handoff_ok_sales:,.0f}".replace(",", "."),
        f"- **Findings:** {len(report.errors)} errors, {len(report.warns)} warnings",
        "",
        "## Field one-pager (enforce this week)",
        "",
        "| Code | Official owner | Rule |",
        "|------|----------------|------|",
        "| **044** | Huber Santiago Enciso | Own remaining book only; Daniel→**095**, Julian→**102** |",
        "| **163** | Betsy Guzman | + credit from Huber; **Asignado 163** wins if Factura still says Huber |",
        "| **131** | Olga Lucia Torres | Calle 5 (**FET**) only; Carlos→**003**, Diana→**106** |",
        "| **162** | William H. Quintero | Sika; use **162** only (not 123/133) |",
        "| 095 | Daniel | Do not book on 044 |",
        "| 102 | Julian | Do not book on 044 |",
        "| 003 | Carlos | Prefer 003 over 131 |",
        "| 106 | Diana | Prefer 106 over 131 |",
        "",
        "## Findings",
        "",
    ]

    if not report.findings:
        lines.append("_No material findings._")
        lines.append("")
    else:
        lines.append("| Sev | Code | Check | Sales | Message |")
        lines.append("|-----|------|-------|------:|---------|")
        for f in report.findings:
            sales = f"${f.sales:,.0f}".replace(",", ".")
            msg = f.message.replace("|", "/")
            if f.detail:
                msg = f"{msg} — {f.detail.replace('|', '/')}"
            lines.append(f"| {f.severity} | {f.code} | {f.check} | {sales} | {msg} |")
        lines.append("")

    lines.extend(
        [
            "## Sales by code (material names)",
            "",
            "| Code | Owner (card) | Total | Top Factura names |",
            "|------|--------------|------:|-------------------|",
        ]
    )
    for code in sorted(
        report.by_code_sales.keys(), key=lambda c: -report.by_code_sales[c]
    ):
        total = report.by_code_sales[code]
        rule = OWNER_CARD.get(code)
        owner = rule.owner if rule is not None else ""
        names = report.by_code_names.get(code) or {}
        top = sorted(names.items(), key=lambda x: -x[1])[:4]
        top_s = "; ".join(
            f"{n} ${v:,.0f}".replace(",", ".")
            for n, v in top
            if v >= report.material_threshold / 10
        )
        lines.append(
            f"| {code} | {owner} | ${total:,.0f} | {top_s} |".replace(",", ".")
        )
    lines.append("")

    if report.merge_orphan_sales:
        lines.extend(["## Merge orphans (123/133 → 162)", ""])
        for c, v in sorted(report.merge_orphan_sales.items()):
            lines.append(f"- **{c}:** ${v:,.0f}".replace(",", "."))
        lines.append("")

    if enero_smoke:
        code_count = str(enero_smoke.get("code_count", "?"))
        expected = str(enero_smoke.get("expected", 18))
        raw_meta = enero_smoke.get("total_meta")
        if isinstance(raw_meta, (int, float)):
            total_meta = float(raw_meta)
        elif isinstance(raw_meta, str) and raw_meta.strip():
            total_meta = float(raw_meta)
        else:
            total_meta = 0.0
        status = str(enero_smoke.get("status", "?"))
        lines.extend(
            [
                "## Enero 2026 presupuesto smoke",
                "",
                f"- **Codes with meta:** {code_count}",
                f"- **Expected:** {expected}",
                f"- **Total meta (periodo 20261):** "
                f"${total_meta:,.0f}".replace(",", "."),
                f"- **Status:** {status}",
                "",
            ]
        )
        missing_raw = enero_smoke.get("missing_codes")
        extra_raw = enero_smoke.get("extra_codes")
        missing = [str(x) for x in missing_raw] if isinstance(missing_raw, list) else []
        extra = [str(x) for x in extra_raw] if isinstance(extra_raw, list) else []
        if missing:
            lines.append(f"- **Missing from card:** {', '.join(missing)}")
        if extra:
            lines.append(f"- **Extra vs card:** {', '.join(extra)}")
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "- Purity is **read-only**; no ERP writes.",
            "- Budget attribution: **Asignado > Factura owner > vendedor_codigo** "
            "(see `presupuesto_2026.attribute_sale`).",
            "- Re-generate 2026 metas only after ~30 days of cleaner booking.",
            "",
            f"*Generated from live SmartBusiness analysis.*",
            "",
        ]
    )
    return "\n".join(lines)


def field_one_pager_lines() -> List[str]:
    """Short checklist for Comercial."""
    return [
        "044 = Huber only (Daniel→095, Julian→102)",
        "163 = Betsy (+ Huber credit); Asignado 163 wins over Factura Huber",
        "131 = Olga Calle 5; Carlos→003, Diana→106",
        "162 = William Sika only (not 123/133)",
    ]

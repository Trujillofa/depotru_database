"""Problem → product guides for storefront customers (no SKU language).

Customers describe a job or problem (“pintar una habitación”, “una gotera”).
We answer with a short shopping list of product *types*, then ground it with
catalog search by name when possible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ProductNeed:
    """One line in a shopping list for a problem/project."""

    label: str  # Spanish, customer-friendly
    query: str  # catalog search fragment


@dataclass(frozen=True)
class ProblemGuide:
    id: str
    title: str
    patterns: Tuple[str, ...]
    intro: str
    needs: Tuple[ProductNeed, ...]
    tip: str = ""


# Curated ferretería / materiales guides (Neiva / Colombia colloquial Spanish).
GUIDES: Tuple[ProblemGuide, ...] = (
    ProblemGuide(
        id="pintar_interior",
        title="Pintar una habitación o pared interior",
        patterns=(
            r"pintar\s+(una\s+)?(habitaci[oó]n|cuarto|pieza|pared|interior)",
            r"pintura\s+para\s+(pared|habitaci|interior)",
            r"quiero\s+pintar",
            r"necesito\s+pintar",
            r"c[oó]mo\s+pinto",
        ),
        intro="Para pintar un interior normalmente te conviene tener:",
        needs=(
            ProductNeed("Pintura para interiores (vinilo o similar)", "pintura"),
            ProductNeed("Rodillo y/o brochas", "rodillo"),
            ProductNeed("Cinta de enmascarar", "cinta enmascarar"),
            ProductNeed("Lija o resanador si hay huecos", "resanador"),
            ProductNeed("Bandeja para pintura", "bandeja pintura"),
        ),
        tip="Si la pared está muy manchada o es de otro color fuerte, pregunta por sellador o base.",
    ),
    ProblemGuide(
        id="pintar_exterior",
        title="Pintar fachada o exterior",
        patterns=(
            r"pintar\s+(la\s+)?(fachada|exterior|casa\s+por\s+fuera)",
            r"pintura\s+(para\s+)?(fachada|exterior)",
        ),
        intro="Para pintar exterior/fachada suele hacer falta:",
        needs=(
            ProductNeed("Pintura para exteriores / fachada", "pintura exterior"),
            ProductNeed("Rodillo o brocha gruesa", "rodillo"),
            ProductNeed(
                "Sellador o impermeabilizante (según superficie)", "impermeabilizante"
            ),
        ),
        tip="En clima húmedo conviene pintura exterior y buen sellado de grietas antes de pintar.",
    ),
    ProblemGuide(
        id="gotera",
        title="Gotera o filtración",
        patterns=(
            r"gotera",
            r"filtraci[oó]n",
            r"se\s+mete\s+agua",
            r"gotea\s+(el\s+)?(techo|cielo|teja)",
            r"agua\s+en\s+el\s+techo",
        ),
        intro="Para una gotera o filtración suele servir:",
        needs=(
            ProductNeed("Impermeabilizante o sellador de techos", "impermeabilizante"),
            ProductNeed("Cinta o masilla selladora", "sellador"),
            ProductNeed("Cemento o mortero si hay grieta estructural", "cemento"),
            ProductNeed("Brocha o rodillo para aplicar", "brocha"),
        ),
        tip="Si la gotera es grande o en teja, también puede hacer falta teja de repuesto o manto asfáltico.",
    ),
    ProblemGuide(
        id="fuga_agua",
        title="Fuga de agua o grifo",
        patterns=(
            r"fuga\s+de\s+agua",
            r"gotea\s+(el\s+)?(grifo|llave|tubo|tuber[ií]a)",
            r"(grifo|llave|mezclador).{0,40}gotea",
            r"gotea.{0,40}(grifo|llave|mezclador)",
            r"(?:da[nñ][oó]|rompi[oó]|averi[oó]).{0,30}(grifo|llave|mezclador|tuber[ií]a)",
            r"(grifo|llave|mezclador).{0,30}(?:da[nñ]ad|rot[oa]|averiad)",
            r"cambiar\s+(el\s+)?(grifo|llave|mezclador)",
            r"instalar\s+(un\s+)?(grifo|llave)",
            r"tuber[ií]a\s+(rota|da[nñ]ada|que\s+gotea)",
            r"\bplomer[ií]a\b",
        ),
        intro="Para una fuga o cambio de grifería/tubería suele necesitarse:",
        needs=(
            ProductNeed("Cinta teflón (cinta de teflón)", "teflon"),
            ProductNeed("Tubo o accesorio PVC / CPVC según el sistema", "pvc"),
            ProductNeed("Pegamento o cemento solvente para PVC", "pegamento pvc"),
            ProductNeed("Empaques o grifería de repuesto", "grifo"),
            ProductNeed("Llave stillson o herramienta de plomería", "stillson"),
        ),
        tip="Cierra la llave de paso antes de trabajar. Si no sabes si es PVC o metálico, tráenos una foto o un trozo del tubo.",
    ),
    ProblemGuide(
        id="electricidad_basica",
        title="Toma, interruptor o cableado básico",
        patterns=(
            r"tomacorriente|toma\s+corriente|enchufe",
            r"interruptor\s+(el[eé]ctrico|de\s+luz)",
            r"cableado|cable\s+el[eé]ctrico",
            r"no\s+hay\s+luz\s+en",
            r"corto\s+circuito",
            r"instalar\s+(una\s+)?l[aá]mpara",
        ),
        intro="Para trabajos eléctricos básicos en casa suele usarse:",
        needs=(
            ProductNeed("Cable eléctrico del calibre adecuado", "cable electrico"),
            ProductNeed("Tomacorrientes o interruptores", "tomacorriente"),
            ProductNeed("Caja eléctrica / tapa", "caja electrica"),
            ProductNeed("Cinta aislante", "cinta aislante"),
            ProductNeed("Destornilladores y, si aplica, breaker", "destornillador"),
        ),
        tip="La electricidad es delicada: si hay duda, un electricista. No trabajes con la red energizada.",
    ),
    ProblemGuide(
        id="resane_pared",
        title="Huecos o grietas en la pared",
        patterns=(
            r"hueco\s+en\s+(la\s+)?pared",
            r"grieta\s+en\s+(la\s+)?pared",
            r"resanar|resane",
            r"rellenar\s+(un\s+)?hueco",
            r"pared\s+da[nñ]ada",
        ),
        intro="Para resanar o tapar huecos en pared suele servir:",
        needs=(
            ProductNeed("Masilla o resanador de pared", "resanador"),
            ProductNeed("Estuco o yeso (según acabado)", "estuco"),
            ProductNeed("Lija", "lija"),
            ProductNeed("Espátula", "espatula"),
            ProductNeed("Pintura para retocar", "pintura"),
        ),
        tip="Limpia el polvo del hueco antes de resanar; lija cuando seque y luego pinta.",
    ),
    ProblemGuide(
        id="ceramica_piso",
        title="Instalar o reparar cerámica / piso",
        patterns=(
            r"cer[aá]mica",
            r"instalar\s+(el\s+)?piso",
            r"pegar\s+(los\s+)?baldos",
            r"enchape|enchapar",
            r"piso\s+(roto|levantado|suelto)",
        ),
        intro="Para instalar o reparar cerámica/piso normalmente necesitas:",
        needs=(
            ProductNeed("Pegante o mortero para cerámica", "pegante ceramica"),
            ProductNeed("Boquilla / fraguado", "boquilla"),
            ProductNeed("Espaciadores (crucetas)", "cruceta"),
            ProductNeed("Llana dentada", "llana"),
            ProductNeed(
                "Cortadora o herramienta de corte (si aplica)", "corta ceramica"
            ),
        ),
        tip="Mide bien el área y compra un poco de más de cerámica por cortes y roturas.",
    ),
    ProblemGuide(
        id="losa_concreto",
        title="Losa, concreto o mezcla",
        patterns=(
            r"\blosa\b",
            r"concreto|hormig[oó]n",
            r"fundaci[oó]n",
            r"vaciar\s+(una\s+)?placa",
            r"mezcla\s+para\s+(piso|columna|viga)",
        ),
        intro="Para trabajos de concreto/losa suele requerirse:",
        needs=(
            ProductNeed("Cemento", "cemento"),
            ProductNeed("Arena y/o grava (agregados)", "arena"),
            ProductNeed("Varilla / hierro de refuerzo", "varilla"),
            ProductNeed("Alambre de amarre", "alambre amarre"),
            ProductNeed("Formaleta o formaletería (si aplica)", "formaleta"),
        ),
        tip="La dosificación depende del uso (placa, columna, pañete). Cuéntanos el trabajo y te orientamos mejor.",
    ),
    ProblemGuide(
        id="techo_teja",
        title="Techo o tejas",
        patterns=(
            r"\btejas?\b",
            r"arreglar\s+(el\s+)?techo",
            r"cambiar\s+(una\s+)?teja",
            r"cubierta\s+(del\s+)?techo",
        ),
        intro="Para techo/tejas suele necesitarse:",
        needs=(
            ProductNeed("Tejas de repuesto (tipo compatible)", "teja"),
            ProductNeed("Impermeabilizante o sellador", "impermeabilizante"),
            ProductNeed("Clavos o fijaciones para teja", "clavo teja"),
            ProductNeed("Manto o tela asfáltica (si aplica)", "manto asfaltico"),
        ),
        tip="Lleva el tipo/foto de la teja actual: hay muchas medidas y perfiles.",
    ),
    ProblemGuide(
        id="cerradura_puerta",
        title="Cerradura o puerta",
        patterns=(
            r"cerradura|chapa\s+de\s+puerta",
            r"cambiar\s+(la\s+)?chapa",
            r"puerta\s+(que\s+no\s+cierra|trabada|da[nñ]ada)",
            r"candado",
        ),
        intro="Para cerradura o seguridad de puerta suele servir:",
        needs=(
            ProductNeed("Cerradura o chapa del tipo de tu puerta", "cerradura"),
            ProductNeed("Tornillos y, si aplica, pasador", "pasador"),
            ProductNeed("Candado (para portón o reja)", "candado"),
            ProductNeed("Destornilladores", "destornillador"),
        ),
        tip="Mide el grueso de la puerta y el tipo de chapa (embutir, sobreponer, multipunto).",
    ),
    ProblemGuide(
        id="humedad_moho",
        title="Humedad o moho",
        patterns=(
            r"\bhumedad\b",
            r"\bmoho\b",
            r"pared\s+mojada",
            r"manchas\s+de\s+humedad",
            r"se\s+descascara\s+la\s+pintura",
        ),
        intro="Para humedad/moho en paredes suele usarse:",
        needs=(
            ProductNeed("Antihongos o sellador antimohos", "antihongos"),
            ProductNeed("Impermeabilizante de muros", "impermeabilizante"),
            ProductNeed("Pintura con protección (si aplica)", "pintura"),
            ProductNeed("Resanador si hay desprendimientos", "resanador"),
        ),
        tip="Primero hay que cortar la fuente de humedad (gotera, filtración, falta de ventilación).",
    ),
    ProblemGuide(
        id="taladrar_colgar",
        title="Taladrar o colgar en la pared",
        patterns=(
            r"taladrar|taladro",
            r"colgar\s+(un\s+)?(cuadro|tele|estante|espejo)",
            r"taco\s+fisher|chazo|tarugo",
            r"broca\s+para\s+(concreto|pared)",
        ),
        intro="Para taladrar o fijar algo en la pared suele hacer falta:",
        needs=(
            ProductNeed("Taladro y brocas adecuadas (concreto/madera)", "broca"),
            ProductNeed("Chazos / tacos de expansión", "chazo"),
            ProductNeed("Tornillos del tamaño correcto", "tornillo"),
            ProductNeed("Nivel de burbuja (opcional pero útil)", "nivel"),
        ),
        tip="Identifica si la pared es ladrillo, bloque o drywall: el chazo y la broca cambian.",
    ),
    ProblemGuide(
        id="malla_cerca",
        title="Cercado o malla",
        patterns=(
            r"\bcerca\b|\bcercado\b",
            r"malla\s+(eslabonada|cicl[oó]n|ganadera)",
            r"cerrar\s+(el\s+)?lote",
            r"alambrado",
        ),
        intro="Para un cercado o malla suele necesitarse:",
        needs=(
            ProductNeed("Malla (eslabonada u otro tipo)", "malla"),
            ProductNeed("Postes o tubos", "poste"),
            ProductNeed("Alambre de amarre / grapas", "alambre"),
            ProductNeed("Cemento para fijar postes", "cemento"),
        ),
        tip="Mide el perímetro y la altura deseada antes de comprar.",
    ),
    ProblemGuide(
        id="soldadura",
        title="Soldadura o trabajo en metal",
        patterns=(
            r"soldar|soldadura",
            r"electrodo",
            r"varilla\s+de\s+soldar",
            r"estructura\s+met[aá]lica",
        ),
        intro="Para soldadura básica en metal suele usarse:",
        needs=(
            ProductNeed("Electrodos / varilla de soldar", "electrodo"),
            ProductNeed("Discos de corte o amoladora (si aplica)", "disco corte"),
            ProductNeed("Guantes y careta de protección", "careta soldar"),
            ProductNeed("Ángulos o perfiles metálicos", "angular"),
        ),
        tip="Protección personal es obligatoria. Indica el espesor del metal si puedes.",
    ),
    ProblemGuide(
        id="jardin_riego",
        title="Jardín o riego",
        patterns=(
            r"\bjard[ií]n\b",
            r"\briego\b",
            r"manguera",
            r"aspersor",
            r"cerca\s+viva",  # weak - skip
        ),
        intro="Para jardín o riego suele servir:",
        needs=(
            ProductNeed("Manguera y conexiones", "manguera"),
            ProductNeed("Aspersores o pistola de riego", "aspersor"),
            ProductNeed("Teflón y adaptadores de rosca", "teflon"),
            ProductNeed("Tijera o herramientas de jardín", "tijera jardin"),
        ),
        tip="Dinos si el agua es de grifo de jardín o de tanque para orientarte en conexiones.",
    ),
)


_PROBLEM_HINT_RE = re.compile(
    r"(?:"
    r"qu[eé]\s+(?:necesito|me\s+falta|productos?\s+necesito)|"
    r"qu[eé]\s+(?:compro|debo\s+comprar|sirve\s+para)|"
    r"(?:para|c[oó]mo)\s+(?:puedo\s+)?(?:hacer|arreglar|reparar|instalar|solucionar)|"
    r"necesito\s+(?:material(?:es)?|cosas|productos?)\s+para|"
    r"material(?:es)?\s+para|"
    r"se\s+me\s+(?:da[nñ][oó]|rompi[oó]|averi[oó])|"
    r"tengo\s+(?:un\s+problema|una\s+gotera|humedad)|"
    r"c[oó]mo\s+(?:arreglo|reparo|soluciono|pinto|instalo)"
    r")",
    re.I,
)


def match_guide(text: str) -> Optional[ProblemGuide]:
    """Return the first guide whose patterns match the user message."""
    t = text or ""
    for guide in GUIDES:
        for pat in guide.patterns:
            if re.search(pat, t, flags=re.I):
                return guide
    return None


def looks_like_problem(text: str) -> bool:
    """True if the message looks like a job/problem, not a bare product name."""
    if match_guide(text):
        return True
    return bool(_PROBLEM_HINT_RE.search(text or ""))


def extract_problem_topic(text: str) -> Optional[str]:
    """Best-effort free-text topic when no curated guide matches.

    Examples:
      "qué necesito para arreglar el portón" → "arreglar el portón"
      "materiales para una cerca" → "una cerca"
    """
    t = (text or "").strip()
    patterns = (
        r"qu[eé]\s+(?:necesito|compro|debo\s+comprar|me\s+falta)\s+para\s+(.+?)(?:\?|$)",
        r"material(?:es)?\s+para\s+(.+?)(?:\?|$)",
        r"productos?\s+para\s+(.+?)(?:\?|$)",
        r"c[oó]mo\s+(?:arreglo|reparo|soluciono|hago)\s+(.+?)(?:\?|$)",
        r"para\s+(?:arreglar|reparar|instalar|hacer)\s+(.+?)(?:\?|$)",
        r"necesito\s+(?:material(?:es)?|cosas|productos?)\s+para\s+(.+?)(?:\?|$)",
    )
    for pat in patterns:
        m = re.search(pat, t, flags=re.I)
        if m:
            topic = m.group(1).strip()
            topic = re.sub(r"[¿?¡!.,;:]+$", "", topic).strip()
            topic = re.sub(
                r"^(el|la|los|las|un|una|unos|unas)\s+",
                "",
                topic,
                flags=re.I,
            ).strip()
            if 2 <= len(topic) <= 80:
                return topic
    return None


def format_need_list(needs: Sequence[ProductNeed]) -> str:
    return "\n".join(f"• {n.label}" for n in needs)


def search_queries_for_guide(guide: ProblemGuide, max_queries: int = 4) -> List[str]:
    """Distinct catalog queries to ground the guide with real product names."""
    seen = set()
    out: List[str] = []
    for need in guide.needs:
        q = need.query.strip().lower()
        if q and q not in seen:
            seen.add(q)
            out.append(need.query.strip())
        if len(out) >= max_queries:
            break
    return out

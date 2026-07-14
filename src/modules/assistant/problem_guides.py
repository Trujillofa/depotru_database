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
            r"sistema\s+de\s+riego",
            r"\briego\b",
            r"manguera",
            r"aspersor",
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
    # --- Expanded guides (common storefront jobs) ---
    ProblemGuide(
        id="bano_remodelar",
        title="Remodelar o arreglar un baño",
        patterns=(
            r"remodelar\s+(el\s+)?ba[nñ]o",
            r"arreglar\s+(el\s+)?ba[nñ]o",
            r"material(?:es)?\s+para\s+(el\s+)?ba[nñ]o",
            r"obra\s+(de\s+)?ba[nñ]o",
            r"ba[nñ]o\s+(nuevo|completo|desde\s+cero)",
        ),
        intro="Para un baño (obra o remodelación) suele hacer falta, según el alcance:",
        needs=(
            ProductNeed("Cerámica o enchape para piso/muro", "ceramica"),
            ProductNeed("Pegante y boquilla para cerámica", "pegante ceramica"),
            ProductNeed("Impermeabilizante para zonas húmedas", "impermeabilizante"),
            ProductNeed("Tubería y accesorios sanitarios (PVC)", "pvc sanitario"),
            ProductNeed("Sanitarios / grifería (según lo que cambies)", "sanitario"),
        ),
        tip="Dinos si es solo enchape, plomería o baño completo: la lista cambia mucho.",
    ),
    ProblemGuide(
        id="inodoro_sanitario",
        title="Instalar o cambiar inodoro / sanitario",
        patterns=(
            r"\binodoro\b",
            r"\bsanitario\b",
            r"cambiar\s+(el\s+)?(inodoro|sanitario|poceta)",
            r"instalar\s+(el\s+)?(inodoro|sanitario|poceta)",
            r"\bpoceta\b",
        ),
        intro="Para instalar o cambiar un inodoro suele necesitarse:",
        needs=(
            ProductNeed("Inodoro / sanitario compatible", "sanitario"),
            ProductNeed("Empaque o sello de cera / goma", "empaque inodoro"),
            ProductNeed("Tornillos de anclaje y tuercas", "tornillo inodoro"),
            ProductNeed("Manguera o abasto de agua", "manguera abasto"),
            ProductNeed("Teflón y, si aplica, flexibles", "teflon"),
        ),
        tip="Mide la salida (al piso o a la pared) y el espacio disponible antes de comprar.",
    ),
    ProblemGuide(
        id="ducha_regadera",
        title="Ducha, regadera o mezclador",
        patterns=(
            r"\bducha\b",
            r"\bregadera\b",
            r"mezclador\s+(de\s+)?(ducha|ba[nñ]o)",
            r"cambiar\s+(la\s+)?(ducha|regadera)",
            r"instalar\s+(la\s+)?(ducha|regadera)",
        ),
        intro="Para ducha/regadera o mezclador suele servir:",
        needs=(
            ProductNeed("Regadera o set de ducha", "regadera"),
            ProductNeed("Mezclador o monomando (si aplica)", "mezclador"),
            ProductNeed("Teflón y flexibles o tubería", "teflon"),
            ProductNeed("Empaques / válvulas de repuesto", "empaque"),
            ProductNeed("Silicona sanitaria antihongos", "silicona"),
        ),
        tip="Indica si es empotrado o expuesto y si hay agua caliente: el kit cambia.",
    ),
    ProblemGuide(
        id="tanque_agua",
        title="Tanque de agua o almacenamiento",
        patterns=(
            r"tanque\s+de\s+agua",
            r"tanque\s+(elevado|pl[aá]stico|polietileno)",
            r"instalar\s+(un\s+)?tanque",
            r"\bpolietileno\b.*tanque|tanque.*\bpolietileno\b",
            r"almacenamiento\s+de\s+agua",
        ),
        intro="Para instalar o reponer un tanque de agua suele necesitarse:",
        needs=(
            ProductNeed("Tanque del volumen adecuado", "tanque"),
            ProductNeed("Válvula de flotador / flote", "flotador"),
            ProductNeed("Tubería y uniones PVC", "pvc"),
            ProductNeed("Unión universal o niples", "union universal"),
            ProductNeed("Base o soporte nivelado (y a veces malla)", "base tanque"),
        ),
        tip="Elige capacidad (litros) y si es bajo o elevado. Revisa la entrada y el desagüe de rebosadero.",
    ),
    ProblemGuide(
        id="bomba_agua",
        title="Bomba de agua o presión",
        patterns=(
            r"bomba\s+de\s+agua",
            r"bomba\s+(hidroneum[aá]tica|presurizadora|sumergible)",
            r"no\s+hay\s+presi[oó]n\s+(de\s+)?agua",
            r"poca\s+presi[oó]n\s+(de\s+)?agua",
            r"presurizar\s+(el\s+)?agua",
        ),
        intro="Para mejorar presión o bombear agua suele usarse:",
        needs=(
            ProductNeed(
                "Bomba adecuada al uso (cisterna, pozo, presión)", "bomba agua"
            ),
            ProductNeed("Mangueras o tubería de succión/descarga", "manguera"),
            ProductNeed("Válvula check / retención", "valvula check"),
            ProductNeed("Uniones y teflón", "teflon"),
            ProductNeed("Interruptor de presión o flotador (si aplica)", "presostato"),
        ),
        tip="Dinos de dónde saca el agua (tanque, pozo, red) y a qué altura sube: eso define la bomba.",
    ),
    ProblemGuide(
        id="gas_domestico",
        title="Gas doméstico (conexiones básicas)",
        patterns=(
            r"\bgas\s+natural\b",
            r"\bgas\s+propano\b",
            r"manguera\s+de\s+gas",
            r"estufa\s+de\s+gas",
            r"instalar\s+(la\s+)?estufa",
            r"regulador\s+de\s+gas",
            r"pipeta|cilindro\s+de\s+gas",
        ),
        intro="Para conexiones básicas de gas (estufa/cilindro) suele usarse:",
        needs=(
            ProductNeed("Manguera para gas certificada", "manguera gas"),
            ProductNeed("Regulador de gas", "regulador gas"),
            ProductNeed("Abrazaderas / uniones adecuadas", "abrazadera"),
            ProductNeed(
                "Cinta o sellador aprobado para gas (no teflón genérico)", "cinta gas"
            ),
        ),
        tip="El gas es peligroso: usa solo accesorios certificados y, si hay duda, un técnico autorizado. Revisa fugas con agua jabonosa, nunca con fuego.",
    ),
    ProblemGuide(
        id="drywall",
        title="Drywall / Gyplac / cielorraso",
        patterns=(
            r"\bdrywall\b",
            r"\bgyplac\b|\bgypsum\b",
            r"cielorraso|cielo\s+raso",
            r"tablero\s+de\s+yeso",
            r"divisi[oó]n\s+(en\s+)?drywall",
            r"pared\s+de\s+yeso",
        ),
        intro="Para drywall / cielorraso suele necesitarse:",
        needs=(
            ProductNeed("Placas de yeso (drywall)", "drywall"),
            ProductNeed("Perfiles o parales metálicos", "paral"),
            ProductNeed("Tornillos para drywall", "tornillo drywall"),
            ProductNeed("Cinta y masilla para juntas", "masilla drywall"),
            ProductNeed("Lija y, si aplica, pintura", "lija"),
        ),
        tip="Para baños o zonas húmedas pide placa resistente a la humedad (verde / RH).",
    ),
    ProblemGuide(
        id="panete_revoque",
        title="Pañete, revoque o repello",
        patterns=(
            r"pa[nñ]ete",
            r"\brevoque\b",
            r"\brepello\b",
            r"emparejar\s+(la\s+)?pared",
            r"alisar\s+(la\s+)?pared",
            r"estuco\s+grueso",
        ),
        intro="Para pañetear o repellar una pared suele usarse:",
        needs=(
            ProductNeed("Cemento", "cemento"),
            ProductNeed("Arena", "arena"),
            ProductNeed("Cal o aditivo (según mezcla)", "cal"),
            ProductNeed("Palustra / llana", "llana"),
            ProductNeed("Regla o nivel", "nivel"),
        ),
        tip="Humedece el muro y trabaja por paños. Luego estuco fino y pintura.",
    ),
    ProblemGuide(
        id="estuco_acabado",
        title="Estuco y acabado fino",
        patterns=(
            r"\bestuco\b",
            r"acabado\s+fino",
            r"alisar\s+para\s+pintar",
            r"estucar",
        ),
        intro="Para estuco y dejar listo para pintura suele hacer falta:",
        needs=(
            ProductNeed("Estuco o masilla de acabado", "estuco"),
            ProductNeed("Espátula o llana fina", "espatula"),
            ProductNeed("Lija (granos medios y finos)", "lija"),
            ProductNeed("Sellador o base antes de pintar", "sellador"),
            ProductNeed("Pintura", "pintura"),
        ),
        tip="Lija entre manos y limpia el polvo; si no, la pintura se ve rayada.",
    ),
    ProblemGuide(
        id="impermeabilizar_terraza",
        title="Impermeabilizar terraza, placa o azotea",
        patterns=(
            r"impermeabilizar\s+(la\s+)?(terraza|placa|azotea|losa)",
            r"terraza\s+(que\s+)?(se\s+)?(filtra|gotea|moja)",
            r"placa\s+(que\s+)?(se\s+)?(filtra|gotea)",
            r"manto\s+asf[aá]ltico",
            r"membrana\s+impermeable",
        ),
        intro="Para impermeabilizar terraza/placa suele usarse:",
        needs=(
            ProductNeed(
                "Impermeabilizante (acrílico, cementoso o manto)", "impermeabilizante"
            ),
            ProductNeed("Brocha o rodillo de aplicación", "brocha"),
            ProductNeed("Resanador o mortero para grietas", "resanador"),
            ProductNeed("Malla o tela de refuerzo (si aplica)", "malla refuerzo"),
            ProductNeed("Primario / base (según sistema)", "primer"),
        ),
        tip="Repara grietas y limpia bien antes. El clima seco ayuda al curado.",
    ),
    ProblemGuide(
        id="canal_bajante",
        title="Canal de lluvia o bajante",
        patterns=(
            r"canal\s+(de\s+)?(lluvia|aguas)",
            r"\bbajante\b",
            r"canaleta",
            r"desag[uü]e\s+de\s+(techo|lluvia)",
            r"canal[oó]n",
        ),
        intro="Para canal de lluvia o bajante suele necesitarse:",
        needs=(
            ProductNeed("Canal o canaleta", "canaleta"),
            ProductNeed("Bajante / tubo de bajada", "bajante"),
            ProductNeed("Uniones, codos y soportes", "codo pvc"),
            ProductNeed("Silicona o sellador", "silicona"),
            ProductNeed("Tornillos y ganchos de fijación", "gancho canal"),
        ),
        tip="Calcula la pendiente hacia el bajante y el largo del alero.",
    ),
    ProblemGuide(
        id="destape_desague",
        title="Destapar desagüe o tubería tapada",
        patterns=(
            r"destapar",
            r"desag[uü]e\s+tapado",
            r"tap[oó]\s+(el\s+)?desag[uü]e",
            r"se\s+me\s+tap[oó]",
            r"tuber[ií]a\s+tapada",
            r"ca[nñ]er[ií]a\s+tapada",
            r"el\s+(ba[nñ]o|lavaplatos|lavamanos)\s+(se\s+)?tapa",
            r"\bsonda\b.*desag|desag.*\bsonda\b",
        ),
        intro="Para un desagüe tapado suele servir:",
        needs=(
            ProductNeed("Destapacaños o sonda", "destapacaños"),
            ProductNeed("Destapador de succión (bomba manual)", "destapador"),
            ProductNeed("Guantes y bolsas", "guantes"),
            ProductNeed("Si es grasa: desengrasante adecuado", "desengrasante"),
        ),
        tip="Evita mezclar químicos fuertes. Si se tapa seguido, puede haber raíz o rotura: conviene revisar la red.",
    ),
    ProblemGuide(
        id="lavaplatos_griferia",
        title="Lavaplatos o grifería de cocina",
        patterns=(
            r"lavaplatos|lavadero",
            r"grifo\s+de\s+(la\s+)?cocina",
            r"grifer[ií]a\s+de\s+cocina",
            r"instalar\s+(el\s+)?lavaplatos",
            r"sif[oó]n\s+(del\s+)?lavaplatos",
        ),
        intro="Para lavaplatos o grifería de cocina suele necesitarse:",
        needs=(
            ProductNeed("Grifería o monomando de cocina", "grifo cocina"),
            ProductNeed("Sifón y desagüe", "sifon"),
            ProductNeed("Mangueras de abasto (fría/caliente)", "manguera abasto"),
            ProductNeed("Teflón y uniones", "teflon"),
            ProductNeed("Silicona para sellar el mesón", "silicona"),
        ),
        tip="Mide el hueco del mesón y si el agua es de pared o de piso.",
    ),
    ProblemGuide(
        id="puerta_madera_metal",
        title="Instalar o ajustar una puerta",
        patterns=(
            r"instalar\s+(una\s+)?puerta",
            r"cambiar\s+(la\s+)?puerta",
            r"puerta\s+(de\s+)?(madera|metal|aluminio)",
            r"bisagras?\s+(de\s+)?puerta",
            r"puerta\s+(que\s+)?(no\s+cierra|roza|se\s+pega)",
        ),
        intro="Para instalar o ajustar una puerta suele usarse:",
        needs=(
            ProductNeed(
                "Puerta del tamaño correcto (o chapa si solo es seguridad)", "puerta"
            ),
            ProductNeed("Bisagras", "bisagra"),
            ProductNeed("Cerradura / chapa", "cerradura"),
            ProductNeed("Tornillos y, si aplica, espuma o cuñas", "tornillo"),
            ProductNeed("Nivel y destornilladores", "nivel"),
        ),
        tip="Mide alto, ancho y grueso del marco. Si solo “no cierra”, a veces bastan bisagras o ajuste de chapa.",
    ),
    ProblemGuide(
        id="porton",
        title="Portón o reja",
        patterns=(
            r"\bport[oó]n\b",
            r"\breja\b",
            r"port[oó]n\s+(el[eé]ctrico|corredizo|batiente)",
            r"arreglar\s+(el\s+)?port[oó]n",
        ),
        intro="Para portón o reja suele necesitarse:",
        needs=(
            ProductNeed("Perfiles / tubos o malla según diseño", "tubo cuadrado"),
            ProductNeed("Bisagras o riel (si es corredizo)", "riel"),
            ProductNeed("Candado, chapa o motor (si aplica)", "candado"),
            ProductNeed("Pintura anticorrosiva para metal", "anticorrosivo"),
            ProductNeed("Electrodos si hay que soldar", "electrodo"),
        ),
        tip="Dinos si es batiente o corredizo y el material (hierro, aluminio): cambia por completo el listado.",
    ),
    ProblemGuide(
        id="ventana_vidrio",
        title="Ventana, vidrio o silicona",
        patterns=(
            r"\bventana\b",
            r"cambiar\s+(un\s+)?vidrio",
            r"vidrio\s+(roto|quebrado)",
            r"silicona\s+(para\s+)?(vidrio|ventana)",
            r"filtraci[oó]n\s+(en\s+)?ventana",
        ),
        intro="Para ventana o vidrio suele servir:",
        needs=(
            ProductNeed("Silicona para vidrio / construcción", "silicona"),
            ProductNeed("Junquillos o empaques (si aplica)", "empaque ventana"),
            ProductNeed("Cinta o separadores", "cinta"),
            ProductNeed("Destornilladores y, si hay marco, tornillos", "tornillo"),
        ),
        tip="Si el vidrio está roto, mide el vano exacto o trae un trozo del empaque del marco.",
    ),
    ProblemGuide(
        id="piso_laminado",
        title="Piso laminado o flotante",
        patterns=(
            r"piso\s+laminado",
            r"piso\s+flotante",
            r"laminado\s+de\s+piso",
            r"instalar\s+piso\s+laminado",
            r"\bspc\b|\bvinyl\s*plank\b",
        ),
        intro="Para piso laminado/flotante suele necesitarse:",
        needs=(
            ProductNeed("Láminas o listones de piso", "piso laminado"),
            ProductNeed("Espuma o base (underlayment)", "espuma piso"),
            ProductNeed("Zócalos / guardascales", "zocalo"),
            ProductNeed("Separadores y silicona en bordes húmedos", "silicona"),
            ProductNeed("Sierra o cortadora adecuada", "sierra"),
        ),
        tip="El piso base debe estar seco y nivelado. Deja junta de dilatación en el perímetro.",
    ),
    ProblemGuide(
        id="pintura_metal",
        title="Pintar metal u óxido",
        patterns=(
            r"pintar\s+(el\s+)?(metal|hierro|reja|port[oó]n)",
            r"\b[oó]xido\b",
            r"anticorrosiv",
            r"pintura\s+(para\s+)?(metal|hierro)",
            r"quitar\s+[oó]xido",
        ),
        intro="Para pintar metal o tratar óxido suele usarse:",
        needs=(
            ProductNeed("Removedor o cepillo para óxido", "cepillo alambre"),
            ProductNeed("Convertidor de óxido o base anticorrosiva", "anticorrosivo"),
            ProductNeed("Pintura para metal / esmalte", "esmalte"),
            ProductNeed("Brochas o rodillo para esmalte", "brocha"),
            ProductNeed("Thinner o solvente (si aplica)", "thinner"),
        ),
        tip="Lija o cepilla el óxido suelto antes; si no, la pintura se levanta pronto.",
    ),
    ProblemGuide(
        id="carpinteria_basica",
        title="Carpintería básica en madera",
        patterns=(
            r"carpinter[ií]a",
            r"trabajar\s+madera",
            r"hacer\s+(un\s+)?(mueble|repisa|estante|marco)",
            r"cortar\s+madera",
            r"ensamblar\s+madera",
        ),
        intro="Para un trabajo básico en madera suele hacer falta:",
        needs=(
            ProductNeed("Madera o tablones del tipo adecuado", "madera"),
            ProductNeed("Tornillos o clavos para madera", "tornillo madera"),
            ProductNeed("Cola blanca o adhesivo para madera", "cola madera"),
            ProductNeed("Lija y, si aplica, barniz o pintura", "lija"),
            ProductNeed("Serrucho o sierra, escuadra y metro", "serrucho"),
        ),
        tip="Indica si es interior o exterior: la madera y el acabado cambian.",
    ),
    ProblemGuide(
        id="amoladora_corte",
        title="Cortar metal, baldosa o concreto",
        patterns=(
            r"cortar\s+(metal|hierro|tubo|baldosa|cer[aá]mica|concreto)",
            r"\bamoladora\b",
            r"disco\s+de\s+corte",
            r"radial",
            r"cortadora\s+de\s+(cer[aá]mica|baldosa)",
        ),
        intro="Para cortar metal, baldosa o concreto suele usarse:",
        needs=(
            ProductNeed("Amoladora o herramienta de corte", "amoladora"),
            ProductNeed("Disco adecuado (metal, diamante, concreto)", "disco corte"),
            ProductNeed("Gafas y guantes de protección", "gafas"),
            ProductNeed("Orejeras o tapones (ruido)", "tapones"),
            ProductNeed("Regla o guía de corte", "regla"),
        ),
        tip="El disco incorrecto es peligroso. Di qué material vas a cortar y el espesor.",
    ),
    ProblemGuide(
        id="escalera_altura",
        title="Trabajo en altura / escalera",
        patterns=(
            r"\bescalera\b",
            r"trabajo\s+en\s+altura",
            r"subir\s+al\s+techo",
            r"pintar\s+(el\s+)?techo",
            r"alcanzar\s+(lo\s+)?alto",
        ),
        intro="Para trabajar en altura con seguridad suele servir:",
        needs=(
            ProductNeed(
                "Escalera de la altura adecuada (tijera o extensión)", "escalera"
            ),
            ProductNeed("Cinta o señalización si hay paso de gente", "cinta"),
            ProductNeed("Guantes antideslizantes", "guantes"),
            ProductNeed("Linterna si el sitio es oscuro", "linterna"),
        ),
        tip="Nunca uses el último peldaño. En techo mojado o frágil, prioriza seguridad profesional.",
    ),
    ProblemGuide(
        id="mosquitero",
        title="Mosquitero o malla contra insectos",
        patterns=(
            r"mosquitero",
            r"malla\s+(contra\s+)?(insectos|zancudos|mosquitos)",
            r"angeo",
            r"malla\s+angeo",
        ),
        intro="Para mosquitero o angeo suele necesitarse:",
        needs=(
            ProductNeed("Malla angeo / mosquitero", "angeo"),
            ProductNeed("Perfil o marco (aluminio/madera)", "perfil aluminio"),
            ProductNeed("Junquillo o grapa para fijar la malla", "junquillo"),
            ProductNeed("Silicona o tornillos según el marco", "silicona"),
        ),
        tip="Mide el vano de la ventana o puerta al milímetro.",
    ),
    ProblemGuide(
        id="sika_impermeable",
        title="Aditivos e impermeabilizantes de obra (tipo Sika)",
        patterns=(
            r"\bsika\b",
            r"aditivo\s+(para\s+)?(mortero|concreto|impermeabil)",
            r"impermeabilizante\s+cementoso",
            r"hidr[oó]fugo",
            r"cristalizante",
        ),
        intro="Para aditivos e impermeabilizantes de obra suele usarse:",
        needs=(
            ProductNeed(
                "Impermeabilizante cementoso o aditivo hidrófugo", "impermeabilizante"
            ),
            ProductNeed("Cemento y arena (si es sistema cementoso)", "cemento"),
            ProductNeed("Brocha o llana de aplicación", "brocha"),
            ProductNeed("Resanador de grietas", "resanador"),
        ),
        tip="Cada sistema (pintable, cementoso, manto) tiene pasos distintos. Di si es baño, terraza o muro de contención.",
    ),
    ProblemGuide(
        id="seguridad_candado",
        title="Asegurar puerta, reja o candado",
        patterns=(
            r"asegurar\s+(la\s+)?(puerta|casa|local|reja)",
            r"m[aá]s\s+seguridad",
            r"candado\s+(de\s+)?seguridad",
            r"pasador\s+de\s+seguridad",
            r"proteger\s+(la\s+)?entrada",
        ),
        intro="Para reforzar seguridad básica suele servir:",
        needs=(
            ProductNeed("Candado de buena calidad o chapa de seguridad", "candado"),
            ProductNeed("Pasador o cerrojo", "pasador"),
            ProductNeed("Cadenas o argollas (si aplica)", "cadena"),
            ProductNeed("Tornillos de seguridad / anclajes", "tornillo"),
        ),
        tip="Para locales a veces conviene chapa multipunto o reja; cuéntanos el tipo de puerta.",
    ),
    ProblemGuide(
        id="iluminacion",
        title="Iluminación o lámparas",
        patterns=(
            r"iluminaci[oó]n",
            r"\bl[aá]mparas?\b",
            r"instalar\s+(una\s+)?l[aá]mpara",
            r"bombillo|bombill[oa]",
            r"focos?\s+led",
            r"cambiar\s+(el\s+)?bombillo",
        ),
        intro="Para iluminación básica suele necesitarse:",
        needs=(
            ProductNeed("Bombillos o paneles LED", "led"),
            ProductNeed("Lámpara o aplique", "lampara"),
            ProductNeed(
                "Cable e interruptores (si es instalación nueva)", "cable electrico"
            ),
            ProductNeed("Cinta aislante y conectores", "cinta aislante"),
            ProductNeed("Destornilladores", "destornillador"),
        ),
        tip="Revisa el tipo de rosca o base (E27, GU10, etc.) antes de comprar el bombillo.",
    ),
    ProblemGuide(
        id="calentador_agua",
        title="Calentador de agua",
        patterns=(
            r"calentador\s+(de\s+)?agua",
            r"ducha\s+el[eé]ctrica",
            r"calentador\s+(a\s+)?gas",
            r"agua\s+caliente\s+(en\s+)?(el\s+)?ba[nñ]o",
            r"instalar\s+(un\s+)?calentador",
        ),
        intro="Para calentador de agua o ducha eléctrica suele usarse:",
        needs=(
            ProductNeed("Calentador o ducha eléctrica según servicio", "calentador"),
            ProductNeed(
                "Breakers y cable del calibre correcto (si es eléctrico)", "breaker"
            ),
            ProductNeed("Tubería, flexibles y teflón (si es a gas o paso)", "teflon"),
            ProductNeed("Anclajes y tornillos", "chazo"),
        ),
        tip="Eléctrico vs gas cambia todo. No improvises la acometida eléctrica ni la ventilación de gas.",
    ),
    ProblemGuide(
        id="filtracion_muro",
        title="Humedad que sube por el muro (capilaridad)",
        patterns=(
            r"humedad\s+(por\s+)?capilaridad",
            r"humedad\s+que\s+sube",
            r"muro\s+h[uú]medo\s+(abajo|en\s+la\s+base)",
            r"salitre",
            r"pintura\s+que\s+se\s+explota.*abajo",
        ),
        intro="Para humedad que sube por el muro suele valorarse:",
        needs=(
            ProductNeed(
                "Impermeabilizante para muros / salitre", "impermeabilizante muro"
            ),
            ProductNeed("Resanador y estuco", "resanador"),
            ProductNeed("Pintura antimohos o sellador", "antihongos"),
            ProductNeed("Si aplica: drenaje o corrección exterior", "drenaje"),
        ),
        tip="Si el agua entra desde afuera o por tubería, hay que corregir la causa; si no, vuelve el problema.",
    ),
    ProblemGuide(
        id="herramientas_basicas",
        title="Kit básico de herramientas para el hogar",
        patterns=(
            r"kit\s+de\s+herramientas",
            r"herramientas\s+b[aá]sicas",
            r"armario\s+de\s+herramientas",
            r"quiero\s+armar\s+(un\s+)?taller",
            r"herramientas\s+para\s+(la\s+)?casa",
        ),
        intro="Un kit básico de hogar suele incluir:",
        needs=(
            ProductNeed("Destornilladores (plano y estrella)", "destornillador"),
            ProductNeed("Martillo", "martillo"),
            ProductNeed("Alicate y llave ajustable", "alicate"),
            ProductNeed("Metro y nivel", "metro"),
            ProductNeed("Taladro con set de brocas (muy útil)", "taladro"),
        ),
        tip="Si haces un solo tipo de trabajo (plomería o electricidad), mejor un kit enfocado que uno genérico barato.",
    ),
    ProblemGuide(
        id="pisos_epoxicos",
        title="Piso epóxico o pintura de piso",
        patterns=(
            r"piso\s+ep[oó]xic",
            r"pintura\s+de\s+piso",
            r"ep[oó]xico",
            r"garaje\s+(pintar|epox)",
            r"pintar\s+(el\s+)?(garaje|parqueadero)",
        ),
        intro="Para pintar o epoxicar un piso suele usarse:",
        needs=(
            ProductNeed("Pintura epóxica o de tráfico", "epoxico"),
            ProductNeed("Preparación / desengrasante de piso", "desengrasante"),
            ProductNeed("Rodillo de felpa adecuada", "rodillo"),
            ProductNeed(
                "Cinta de enmascarar y sellador de grietas", "cinta enmascarar"
            ),
        ),
        tip="El piso debe estar limpio, seco y sin grasa; si no, el epóxico no adhiere.",
    ),
    ProblemGuide(
        id="teja_zinc",
        title="Teja de zinc, eternit o cubierta liviana",
        patterns=(
            r"teja\s+(de\s+)?zinc",
            r"\bzinc\b",
            r"\beternit\b",
            r"cubierta\s+liviana",
            r"techo\s+de\s+l[aá]mina",
            r"l[aá]mina\s+(de\s+)?techo",
        ),
        intro="Para cubierta de zinc/lámina suele necesitarse:",
        needs=(
            ProductNeed("Láminas o tejas del perfil correcto", "teja zinc"),
            ProductNeed("Tornillos para teja / autofijantes", "tornillo teja"),
            ProductNeed("Caballetes y remates", "caballete"),
            ProductNeed("Sellador o silicona para traslapes", "silicona"),
            ProductNeed(
                "Cinta asfáltica o manto en uniones (si aplica)", "cinta asfaltica"
            ),
        ),
        tip="Lleva la medida del traslape y la longitud de la caída de agua.",
    ),
    ProblemGuide(
        id="pozo_septico",
        title="Pozo séptico o caja de inspección",
        patterns=(
            r"pozo\s+s[eé]ptico",
            r"caja\s+de\s+inspecci[oó]n",
            r"trampa\s+de\s+grasas",
            r"sistema\s+s[eé]ptico",
            r"alcantarillado\s+interno",
        ),
        intro="Para pozo séptico o cajas de inspección suele usarse:",
        needs=(
            ProductNeed("Tubería sanitaria PVC", "pvc sanitario"),
            ProductNeed("Codos, tees y uniones sanitarias", "codo sanitario"),
            ProductNeed("Tapas de inspección", "tapa inspeccion"),
            ProductNeed("Pegamento PVC sanitario", "pegamento pvc"),
            ProductNeed("Cemento y ladrillo/block si hay obra", "cemento"),
        ),
        tip="Las pendientes y ventilación son críticas. Si es instalación nueva, conviene plano o asesoría técnica.",
    ),
    ProblemGuide(
        id="pegamentos_adhesivos",
        title="Pegar, sellar o adherir (adhesivos)",
        patterns=(
            r"qu[eé]\s+pego",
            r"qu[eé]\s+pegamento",
            r"pegamento\s+para",
            r"adhesivo\s+para",
            r"silicona\s+para",
            r"c[oó]mo\s+pego",
        ),
        intro="Según lo que vayas a pegar, el adhesivo cambia. Lo más pedido:",
        needs=(
            ProductNeed("Silicona (baños, vidrio, sellados)", "silicona"),
            ProductNeed("Pegante de contacto / industrial", "pegante contacto"),
            ProductNeed("Epóxico de dos componentes (cargas altas)", "epoxico"),
            ProductNeed("Cola para madera", "cola madera"),
            ProductNeed("Cinta de doble faz o espuma (livianos)", "cinta doble faz"),
        ),
        tip="Dime los dos materiales (ej. metal con concreto, PVC con PVC, espejo con muro) y te afino el producto.",
    ),
    ProblemGuide(
        id="limpieza_obra",
        title="Limpieza después de obra",
        patterns=(
            r"limpiar\s+(despu[eé]s\s+de\s+)?obra",
            r"limpieza\s+de\s+obra",
            r"quitar\s+(cemento|boquilla|pintura)\s+(del\s+)?piso",
            r"remover\s+residuos\s+de\s+obra",
        ),
        intro="Para limpieza post-obra suele servir:",
        needs=(
            ProductNeed("Removedor de cemento / limpia obra", "limpia obra"),
            ProductNeed("Espátulas y cepillos", "espátula"),
            ProductNeed("Bolsas resistentes y guantes", "guantes"),
            ProductNeed("Traperos y desengrasante", "desengrasante"),
        ),
        tip="Prueba el removedor en un rincón: algunos pisos se manchan con ácidos fuertes.",
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

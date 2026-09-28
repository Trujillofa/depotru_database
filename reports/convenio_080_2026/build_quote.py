#!/usr/bin/env python3
"""Cotización convenio 080 de 2026 from the public depositotrujillo.co catalog.

Prices are the published finalPrice captured on 2026-09-22. This script does
not query J3System and does not invent prices for lines without a catalog match.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

OUT_DIR = Path(__file__).resolve().parent
CAPTURED_ON = "2026-09-22"
SOURCE = "https://www.depositotrujillo.co"

# Sell-unit length used only when the product title states it.
PROFILE_M = 2.44
TUBE_6M = 6.0
NAIL_BAG_G = 350.0
LB_TO_G = 453.59237


def pieces(amount: float, size: float) -> int:
    """Whole sell units needed to cover a requested length or weight."""
    return math.ceil((amount / size) - 1e-9)


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price: float
    sell_unit: str
    url: str


@dataclass(frozen=True)
class Line:
    school: str
    item: str
    description: str
    qty: float
    unit: str
    product: Product | None
    bill_qty: float | None
    status: str  # cotizado | salvedad | sin_precio
    note: str

    @property
    def line_total(self) -> float | None:
        if self.product is None or self.bill_qty is None:
            return None
        return round(self.bill_qty * self.product.price)


def cop(value: float | None) -> str:
    if value is None:
        return "—"
    negative = value < 0
    amount = abs(value)
    if abs(amount - round(amount)) < 0.005:
        text = f"{int(round(amount)):,}".replace(",", ".")
    else:
        text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-${text}" if negative else f"${text}"


def qty_text(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return str(value).replace(".", ",")


P = {
    "teja_master_6_azul": Product(
        "0020110014",
        "Cubierta Máster 1000 Calibre 28 X 6M Color Azul",
        224665,
        "un",
        f"{SOURCE}/cubierta-master-1000-azul-c-28-x-6-00-mt-acesco",
    ),
    "caballete_termo_2_azul": Product(
        "0020110083",
        "Caballete Termoacústico 2M Color Azul",
        147709,
        "un",
        f"{SOURCE}/caballete-termoacusti-azul-2-mt-ajover",
    ),
    "amarre_teja": Product(
        "0020030001",
        "Amarres Para Teja",
        181,
        "un",
        f"{SOURCE}/amarres-para-teja-multimarca",
    ),
    "puntilla_2": Product(
        "0010150034",
        "Puntilla 350Gr 2 Pulgadas",
        3094,
        "bolsa 350 g",
        f"{SOURCE}/puntilla-c-a-mejia-350gr-2-c-a-mejia",
    ),
    "soldadura_6013": Product(
        "0010240163",
        "Soldadura 6013 X 1/8 Kg",
        21044,
        "kg",
        f"{SOURCE}/soldadura-west-arco-6013x1-8-west-arco",
    ),
    "anticorrosivo": Product(
        "0050300008",
        "Anticorrosivo Rojo X Galón",
        54145,
        "gal",
        f"{SOURCE}/anticorrosivo-rojo-x-galon-pintuland",
    ),
    "thinner": Product(
        "0050270008",
        "Thinner Corriente X Galón",
        25000,
        "gal",
        f"{SOURCE}/thinner-corriente-x-galon-multimarca",
    ),
    "tubo_san_4": Product(
        "0020390202",
        "Tubo Sanitario 4 Pulgadas X 6M",
        104606,
        "tubo 6 m",
        f"{SOURCE}/tubo-sanitario-4-pulgadas-x-6m",
    ),
    "codo_4": Product(
        "0020390083",
        "Codo Sanitario 90 Cc 4 Pulgadas Tipo Pesado",
        9007,
        "un",
        f"{SOURCE}/codo-sanitario-90-cc-4-pulgadas-tipo-pesado",
    ),
    "teja_arq_366": Product(
        "0020110039",
        "Cubierta Arquitectónica Calibre 30 X 3.66M",
        63243,
        "un",
        f"{SOURCE}/cubierta-arquitectonica-c-30-x-3-66mt-acesco-acesco",
    ),
    "disco_7": Product(
        "0010350136",
        "Disco Metal Corte Fino 7 Pulgadas X 1/16 Pulgadas X 7/8 Pulgadas Dewalt",
        8281,
        "un",
        f"{SOURCE}/disco-metal-c-fino-dewalt-7-x-1-16-x-7-8-dewalt",
    ),
    "disco_14": Product(
        "0010350169",
        "Disco Cb Norton Bna 26 Azul Corte Metal 14 Pulgadas",
        14423,
        "un",
        f"{SOURCE}/disco-cb-norton-bna-26-azul-c-metal-14-norton",
    ),
    "union_4": Product(
        "0020390247",
        "Unión Sanitaria 4 Pulgadas Tipo Pesado",
        5248,
        "un",
        f"{SOURCE}/union-sanitaria-4-pulgadas-tipo-pesado",
    ),
    "soldadura_pvc": Product(
        "0020220014",
        "Soldadura Pavco Pvc 900 Gr (1/4 Galón)",
        65786,
        "un",
        f"{SOURCE}/soldadura-pavco-pvc-900-gr-1-4-gal-pavco",
    ),
    "limpiador_pvc": Product(
        "0020220026",
        "Limpiador Pavco 12 Onzas",
        17378,
        "un",
        f"{SOURCE}/limpiador-pavco-12-onzas-pavco",
    ),
    "angulo_cielo": Product(
        "0020260049",
        "Perfil Angulo Para Cielo Raso Pvc 2.44",
        1990,
        "pieza 2,44 m",
        f"{SOURCE}/perfil-angulo-para-cielo-raso-pvc-2-44",
    ),
    "omega_cielo": Product(
        "0020260047",
        "Perfil Omega Para Cielo Raso Pvc 2.44M",
        3120,
        "pieza 2,44 m",
        f"{SOURCE}/perfil-omega-para-cielo-raso-pvc-2-44m",
    ),
    "vigueta_cielo": Product(
        "0020260048",
        "Perfil Vigueta Para Cielo Raso Pvc 2.44M",
        3120,
        "pieza 2,44 m",
        f"{SOURCE}/perfil-vigueta-para-cielo-raso-pvc-2-44m",
    ),
    "tornillo_6x1": Product(
        "0010240098",
        "Tornillo Para Drywall Negro 6X1 Punta Aguda Caja X 100 U Lamina",
        1728,
        "caja x 100",
        f"{SOURCE}/tornillo-p-drywall-negro-6x1-p-aguda-caja-x-100-u-lamina-c-a-mejia",
    ),
    "fija_ala": Product(
        "0020110017",
        "Tornillo Autoperforante Fijador Ala 1 1/4 Pulgada Tipo Sombrilla",
        1207,
        "un",
        f"{SOURCE}/tornillo-autoperf-fijador-ala-11-4-t-sombrilla-ajover",
    ),
    "autoperf": Product(
        "0020110016",
        "Tornillo Autoperforante 1 1/2 Pulgada Tipo Sombrilla",
        854,
        "un",
        f"{SOURCE}/tornillo-autoperf-11-2-t-sombrilla-c-a-mejia",
    ),
}


def nail_note() -> str:
    return (
        "La lista pide puntilla de 1 1/2\" a 3\" por libra. Se cotiza la de 2\" "
        f"en bolsa de 350 g ({cop(P['puntilla_2'].price)}). "
        "La de 1 1/2\" está en $3.246 (SKU 0010150033). "
        "1 lb = 453,59237 g; se redondea a bolsas completas."
    )


SOLDADURA_8013 = (
    "La lista dice Westarco 8013 x 1/8. Ese código no está en el catálogo. "
    "Se cotiza Soldadura 6013 x 1/8 kg West-Arco."
)
COLOR_NOTE = (
    "Color no indicado. Se usa anticorrosivo rojo galón. "
    "Amarillo está al mismo precio; naranja está en $81.515 (SKU 0050300074)."
)
TUBO_UN_NOTE = "La lista pide unidades. Se cotiza el tubo sanitario de 6 m."
CABALLETE_NOTE = (
    "Coincide tipo y largo (2 m, azul). La ficha no publica el ancho 0,70 m "
    "pedido en la lista."
)
AMARRE_NOTE = (
    "Único amarre de teja del catálogo. La ficha no confirma tapa metálica "
    "de 26 cm ni calibre 18."
)
TEJA_ARQ_NOTE = (
    "No hay lámina de 3,05 m x 0,83 m. Se usa cubierta arquitectónica "
    "calibre 30 (0,30 mm) de 3,66 m. Alternativa de 3 m color azul: "
    "$41.701 (SKU 0020110074)."
)
DISCO_14_NOTE = (
    "La lista no indica el diámetro. Se usa disco de corte de metal de 14\", "
    "medida habitual de tronzadora."
)
FIJA_ALA_NOTE = "La lista no indica el largo. Se usa fijador de ala de 1 1/4\"."
AUTOPERF_NOTE = (
    "La lista no indica medida. Se usa autoperforante de 1 1/2\" tipo sombrilla, "
    "distinto del fijador de ala."
)
ANGULO_NOTE = (
    "La lista dice ángulo galvanizado. Se cotiza el ángulo de PVC para cielo "
    "raso de 2,44 m y se redondea a piezas completas."
)
PROFILE_NOTE = (
    f"Cada pieza mide {str(PROFILE_M).replace('.', ',')} m. "
    "Se redondea a piezas completas."
)
TUBO_M_NOTE = "La lista está en metros. Cada tubo mide 6 m; se redondea hacia arriba."
TORNILLO_6_NOTE = (
    "Caja por 100 unidades. La lista pide cabeza plana; esta referencia es "
    "punta aguda para lámina."
)
PLATINA_NOTE = (
    "No hay platina de 1/4\" x 1\". Referencias sin sumar: "
    "1\" x 1/8\" $18.089 (SKU 0010190014) y 1\" x 3/16\" $26.999 (SKU 0010190020)."
)
LAMINA_22_NOTE = "No hay lámina lisa galvanizada calibre 22 de 1,22 m en el catálogo."
CANAL_22_NOTE = (
    "No hay canal en lámina galvanizada calibre 22. "
    "Los canales publicados son plásticos (Raingo / Amazonas), otra familia."
)
TUBO_100_NOTE = (
    "No hay tubo estructural 100x100 de 2,00 mm. Referencias sin sumar, "
    "longitud no publicada: 100x100 x 3 mm $289.952 (SKU 0020260100) y "
    "cuadrado 10x10 cm calibre 14 $173.651 (SKU 0020260032)."
)
TUBO_100X38_NOTE = (
    "No hay 100x38 mm calibre 18. Referencias sin sumar: "
    "rectangular 4\" x 1 1/2\" x 1,10 m $68.745 (SKU 0020260020) y "
    "4\" x 1 1/2\" calibre 16 $87.998 (SKU 0020260046)."
)
LONA_NOTE = "No hay lona verde de cerramiento de 2,10 m en el catálogo."
TOMA_NOTE = "No hay toma corriente doble de 110 V en el catálogo."
LAMPARA_NOTE = "No hay lámpara ni bombillo incandescente en el catálogo."
PANEL_NOTE = "No hay luminaria panel LED de 0,60 x 0,60 m. Los resultados son espejos LED."
CONDUIT_NOTE = (
    "Hay tubo conduit PVC pesado de 1/2\" a $4.908 (SKU 0020390182), "
    "pero la ficha no publica el largo, así que no se convierte a metros."
)
CABLE_NOTE = (
    "No hay cable THHN/THW No. 10 ni No. 12. "
    "La lista pide las dos líneas; no se cotiza cable de acero ni de cerca."
)
INTERRUPTOR_NOTE = "No hay interruptor doble de 110 V en el catálogo."
ACCESORIO_NOTE = (
    "La lista no dice qué accesorio de 4\". Referencia sin sumar: "
    "Yee sanitario 4\" tipo pesado $18.337 (SKU 0020390267)."
)
PERFIL_160_NOTE = (
    "No hay perfil C 160x60 mm x 1,5 mm. Referencia sin sumar: "
    "perfil C HR 203x67 x 6 m x 2,5 mm $214.139 (SKU 0020260102)."
)
PERFIL_15X5_NOTE = "No hay perfil Acesco calibre 16 de 150x50 mm (15x5)."
LAMINA_CR_NOTE = (
    "No hay lámina cold rolled calibre 18 de 1,22 x 2,44 m. "
    "Las láminas lisas publicadas son calibre 30, 34 y 35."
)
UPVC_NOTE = "No hay teja termoacústica UPVC de 2 mm, 0,92 x 3,05 m."
CABALLETE_UPVC_NOTE = "No hay caballete UPVC de 0,60 x 0,94 m y 2 mm."
CIELO_NOTE = (
    "No hay cielo raso PVC de 10 mm x 6 m. Referencia sin sumar: "
    "cielo raso PVC blanco 30 cm x 9 mm $24.568 (SKU 0020240099); "
    "la ficha no dice que mida 6 m, así que no se pasa a m²."
)
CORNISA_NOTE = (
    "Hay corniza para cielo raso a $8.482 (SKU 0020240102), "
    "sin largo publicado. La lista pide perfil de 2,90 m, así que no se suma."
)
TORNILLO_8_NOTE = (
    "No hay tornillo 8x1 punta aguda cabeza de lenteja. "
    "Referencia sin sumar: 8x1/2\" punta aguda, caja x 100, $2.246 (SKU 0010240260)."
)
TUBO_90_NOTE = "No hay tubo rectangular 90x50 x 2,5 mm x 6 m."
CANAL_20_NOTE = "No hay canal metálico 0,30 x 0,25 x 0,30 m calibre 20."


def L(
    school: str,
    item: str,
    description: str,
    qty: float,
    unit: str,
    product: Product | None,
    bill_qty: float | None,
    status: str,
    note: str,
) -> Line:
    return Line(school, item, description, qty, unit, product, bill_qty, status, note)


def build_lines() -> list[Line]:
    b1 = "IE Barrios Unidos"
    b2 = "IE Barrios Unidos — Soledad Hermida"
    b3 = "IE Luis Calixto Leiva — Sede Megacolegio"
    b4 = "IE Las Acacias — Sede Los Sauces"
    b5 = "IE San Vicente — Sede Los Laureles"
    lines: list[Line] = []

    def roof_pair(school: str, teja: float, caballete: float, amarre: float, lamina: float, puntilla_lb: float, canal: float, platina_m: float, soldadura_kg: float, gal: float, tubos: float, codos: float, soldadura_note: str) -> None:
        lines.extend(
            [
                L(school, "1", "Teja master 1000 1x6 m Azul Cal.28", teja, "un", P["teja_master_6_azul"], teja, "cotizado", "Medida, calibre y color coinciden."),
                L(school, "2", "Caballete termoacústico (2,0 x 0,70)", caballete, "un", P["caballete_termo_2_azul"], caballete, "salvedad", CABALLETE_NOTE),
                L(school, "3", "Amarre teja tapa metálica 26 cm Cal 18", amarre, "un", P["amarre_teja"], amarre, "salvedad", AMARRE_NOTE),
                L(school, "4", "Lámina galvanizada cal. 22 (flanche)", lamina, "un", None, None, "sin_precio", LAMINA_22_NOTE),
                L(school, "5", 'Puntilla 1 1/2" a 3" de acero', puntilla_lb, "lb", P["puntilla_2"], pieces(puntilla_lb * LB_TO_G, NAIL_BAG_G), "salvedad", nail_note()),
                L(school, "6", "Canal lámina galvanizada cal. 22", canal, "un", None, None, "sin_precio", CANAL_22_NOTE),
                L(school, "7", 'Platina de 1/4" x 1"', platina_m, "m", None, None, "sin_precio", PLATINA_NOTE),
                L(school, "8", 'Soldadura Westarco 8013 x 1/8"', soldadura_kg, "kg", P["soldadura_6013"], soldadura_kg, "salvedad", soldadura_note),
                L(school, "9", "Anticorrosivo", gal, "gal", P["anticorrosivo"], gal, "cotizado", COLOR_NOTE),
                L(school, "10", 'Tubería PVC 4" aguas lluvias', tubos, "un", P["tubo_san_4"], tubos, "cotizado", TUBO_UN_NOTE + " La ficha de Pavco incluye aguas lluvias."),
                L(school, "11", 'Codo 90 x 4" CxC sanitaria', codos, "un", P["codo_4"], codos, "cotizado", "CxC se toma como campana-campana (CC)."),
            ]
        )

    roof_pair(b1, 178, 93, 4646, 14, 20, 8, 12, 2, 1, 30, 12, SOLDADURA_8013)
    roof_pair(b2, 90, 71, 2300, 8, 13, 10, 15, 3, 1, 40, 15, SOLDADURA_8013)

    lines.extend(
        [
            L(b3, "1", "Teja arquitectónica 3,05 x 0,83 m, 0,30 mm", 290, "un", P["teja_arq_366"], 290, "salvedad", TEJA_ARQ_NOTE),
            L(b3, "2", "Canal en lámina galvanizada cal. 22", 30, "un", None, None, "sin_precio", CANAL_22_NOTE),
            L(b3, "3", 'Platina de 1/4" x 1"', 42, "m", None, None, "sin_precio", PLATINA_NOTE),
            L(b3, "4", 'Soldadura Westarco 6013 x 1/8"', 6, "kg", P["soldadura_6013"], 6, "cotizado", "Código y diámetro coinciden."),
            L(b3, "5", "Anticorrosivo", 2, "gal", P["anticorrosivo"], 2, "cotizado", COLOR_NOTE),
            L(b3, "6", 'Tubería PVC 4" aguas lluvias', 120, "m", P["tubo_san_4"], pieces(120, TUBE_6M), "cotizado", TUBO_M_NOTE + " 120 m = 20 tubos."),
            L(b3, "7", 'Codo 90 x 4" CxC sanitaria', 30, "un", P["codo_4"], 30, "cotizado", "CxC se toma como campana-campana (CC)."),
            L(b3, "8", "Tubo estructural cuadrado 100x100 cal. 2,00 grado 50", 131, "m", None, None, "sin_precio", TUBO_100_NOTE),
            L(b3, "9", "Tubo rectangular 100x38, 1,10 mm, cal. 18", 510, "m", None, None, "sin_precio", TUBO_100X38_NOTE),
            L(b3, "10", "Pintura anticorrosiva de estructura metálica", 10, "gal", P["anticorrosivo"], 10, "cotizado", COLOR_NOTE),
            L(b3, "11", "Thinner", 4, "gal", P["thinner"], 4, "cotizado", "Thinner corriente por galón."),
            L(b3, "12", 'Discos de corte de 7" extra fino', 10, "un", P["disco_7"], 10, "cotizado", "Corte fino de 7\" para metal."),
            L(b3, "13", "Discos para tronzadora", 4, "un", P["disco_14"], 4, "salvedad", DISCO_14_NOTE),
            L(b4, "1", "Lona verde h=2,10 m para cerramiento", 60, "m", None, None, "sin_precio", LONA_NOTE),
            L(b4, "2", "Toma corriente doble 110 V", 4, "un", None, None, "sin_precio", TOMA_NOTE),
            L(b4, "3", "Lámpara incandescente", 10, "un", None, None, "sin_precio", LAMPARA_NOTE),
            L(b4, "4", "Luminaria panel LED de 0,6 x 0,6 m", 10, "un", None, None, "sin_precio", PANEL_NOTE),
            L(b4, "5", 'Tubería conduit PVC de 1/2" para luminarias', 38, "m", None, None, "sin_precio", CONDUIT_NOTE),
            L(b4, "6", "Cables No. 10 y No. 12 (dos líneas) para luminarias", 38, "m", None, None, "sin_precio", CABLE_NOTE),
            L(b4, "7", "Interruptor doble 110 V", 3, "un", None, None, "sin_precio", INTERRUPTOR_NOTE),
            L(b4, "8", 'Tubería sanitaria PVC 4"', 16, "m", P["tubo_san_4"], pieces(16, TUBE_6M), "cotizado", TUBO_M_NOTE + " 16 m requieren 3 tubos (sobran 2 m)."),
            L(b4, "9", 'Accesorio PVC 4"', 3, "un", None, None, "sin_precio", ACCESORIO_NOTE),
            L(b4, "10", 'Unión PVC 4"', 3, "un", P["union_4"], 3, "cotizado", "Unión sanitaria de 4\" tipo pesado."),
            L(b4, "11", "Soldadura PVC (1/4 gal)", 1, "un", P["soldadura_pvc"], 1, "cotizado", "Pavco PVC, 900 g, 1/4 de galón."),
            L(b4, "12", "Limpiador PVC (12 onz.)", 1, "un", P["limpiador_pvc"], 1, "cotizado", "Limpiador Pavco de 12 onzas."),
            L(b4, "13", "Perfil Acesco galv. PAG C 160x60 mm, 1,5 mm", 15, "un", None, None, "sin_precio", PERFIL_160_NOTE),
            L(b4, "14", "Perfil Acesco cal. 16, 15x5", 121, "m", None, None, "sin_precio", PERFIL_15X5_NOTE),
            L(b4, "15", "Lámina C.R. cal. 18 (1,22 x 2,44 m)", 6, "un", None, None, "sin_precio", LAMINA_CR_NOTE),
            L(b4, "16", 'Soldadura metal 1/8"', 3, "kg", P["soldadura_6013"], 3, "cotizado", "No indica electrodo. Se usa 6013 x 1/8 kg, el mismo de las otras sedes."),
            L(b4, "17", "Anticorrosivo", 1, "gal", P["anticorrosivo"], 1, "cotizado", COLOR_NOTE),
            L(b4, "18", "Lámina galvanizada cal. 22", 9, "un", None, None, "sin_precio", LAMINA_22_NOTE),
            L(b4, "19", 'Platina de 1/4" x 1"', 13, "m", None, None, "sin_precio", PLATINA_NOTE),
            L(b4, "20", "Pintura anticorrosiva de estructura metálica", 5, "gal", P["anticorrosivo"], 5, "cotizado", COLOR_NOTE),
            L(b4, "21", "Thinner", 2, "gal", P["thinner"], 2, "cotizado", "Thinner corriente por galón."),
            L(b4, "22", "Teja termoacústica UPVC 2 mm, 0,92 x 3,05 m", 65, "un", None, None, "sin_precio", UPVC_NOTE),
            L(b4, "23", "Caballete 0,6 x 0,94 m, 2 mm UPVC", 20, "un", None, None, "sin_precio", CABALLETE_UPVC_NOTE),
            L(b4, "24", "Tornillo fija ala", 360, "un", P["fija_ala"], 360, "salvedad", FIJA_ALA_NOTE),
            L(b4, "25", "Tornillo autoperforante", 1080, "un", P["autoperf"], 1080, "salvedad", AUTOPERF_NOTE),
            L(b4, "26", "Cielo raso PVC 10 mm x 6 m blanco", 121, "m2", None, None, "sin_precio", CIELO_NOTE),
            L(b4, "27", "Ángulo galvanizado para PVC", 181, "m", P["angulo_cielo"], pieces(181, PROFILE_M), "salvedad", ANGULO_NOTE),
            L(b4, "28", "Omega para PVC", 254, "m", P["omega_cielo"], pieces(254, PROFILE_M), "cotizado", PROFILE_NOTE),
            L(b4, "29", "Vigueta para PVC", 254, "m", P["vigueta_cielo"], pieces(254, PROFILE_M), "cotizado", PROFILE_NOTE),
            L(b4, "30", "Perfil cornisa de PVC 2,90 m, blanco", 181, "m", None, None, "sin_precio", CORNISA_NOTE),
            L(b4, "31", "Tornillo estructural autoperforante cabeza plana 6x1", 500, "un", P["tornillo_6x1"], 500 / 100, "cotizado", TORNILLO_6_NOTE),
            L(b4, "32", "Tornillos 8x1 punta aguda (cabeza de lenteja)", 500, "un", None, None, "sin_precio", TORNILLO_8_NOTE),
            L(b5, "1", "Lona verde h=2,10 m para cerramiento", 80, "m", None, None, "sin_precio", LONA_NOTE),
            L(b5, "2", "Teja termoacústica UPVC 2 mm, 0,92 x 3,05 m", 55, "un", None, None, "sin_precio", UPVC_NOTE),
            L(b5, "3", "Caballete 0,6 x 0,94 m, 2 mm UPVC", 26, "un", None, None, "sin_precio", CABALLETE_UPVC_NOTE),
            L(b5, "4", "Tubo rectangular 90x50 x 2,5 mm x 6 m", 80, "m", None, None, "sin_precio", TUBO_90_NOTE),
            L(b5, "5", "Soldadura 6013 de 1/8", 2, "kg", P["soldadura_6013"], 2, "cotizado", "Código y diámetro coinciden."),
            L(b5, "6", "Pintura anticorrosiva", 2, "gal", P["anticorrosivo"], 2, "cotizado", COLOR_NOTE),
            L(b5, "7", "Disolvente thinner", 1, "gal", P["thinner"], 1, "cotizado", "Thinner corriente por galón. El disolvente epóxico es otro producto ($56.823)."),
            L(b5, "8", "Canal metálico (0,30 x 0,25 x 0,30) cal. 20", 50, "m", None, None, "sin_precio", CANAL_20_NOTE),
        ]
    )
    return lines


def sum_status(lines: list[Line], status: str) -> float:
    return float(sum(line.line_total or 0 for line in lines if line.status == status))


def render_markdown(lines: list[Line]) -> str:
    firm = sum_status(lines, "cotizado")
    caveat = sum_status(lines, "salvedad")
    grand = firm + caveat
    missing = [line for line in lines if line.status == "sin_precio"]
    schools: list[str] = []
    for line in lines:
        if line.school not in schools:
            schools.append(line.school)

    parts = [
        "# Cotización — Convenio 080 de 2026",
        "",
        f"Precios publicados en {SOURCE} el {CAPTURED_ON}. "
        "Es el precio final de la ficha (finalPrice), en pesos colombianos.",
        "",
        "No es precio de convenio y no tiene descuento. "
        "No se sumó IVA encima del precio publicado. "
        "Este entorno no tiene conexión a J3System, así que no se usó "
        "`ArticulosVenta` de mostrador. Si el precio de mostrador es distinto, "
        "hay que reconfirmar esas líneas.",
        "",
        "El total solo suma líneas con un SKU publicado. "
        "Las líneas sin precio quedan por fuera.",
        "",
        "## Totales",
        "",
        "| Concepto | Valor |",
        "| --- | ---: |",
        f"| Coincidencia de catálogo | {cop(firm)} |",
        f"| Con salvedad (medida o código aproximado) | {cop(caveat)} |",
        f"| **Total cotizado** | **{cop(grand)}** |",
        f"| Líneas sin precio | {len(missing)} |",
        "",
        "## Por sede",
        "",
        "| Sede | Cotizado | Con salvedad | Total sede | Sin precio |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for school in schools:
        group = [line for line in lines if line.school == school]
        school_firm = sum_status(group, "cotizado")
        school_caveat = sum_status(group, "salvedad")
        school_missing = sum(1 for line in group if line.status == "sin_precio")
        parts.append(
            f"| {school} | {cop(school_firm)} | {cop(school_caveat)} | "
            f"{cop(school_firm + school_caveat)} | {school_missing} |"
        )

    parts.extend(
        [
            "",
            "## Sin precio en el catálogo",
            "",
            "Estas líneas no entran al total. Donde había una referencia cercana, "
            "la nota dice el SKU y el precio, sin sumarlo.",
            "",
            "| Sede | Ítem | Pedido | Descripción |",
            "| --- | --- | --- | --- |",
        ]
    )
    for line in missing:
        parts.append(
            f"| {line.school} | {line.item} | {qty_text(line.qty)} {line.unit} | "
            f"{line.description} |"
        )

    for school in schools:
        parts.extend(["", f"## {school}", ""])
        group = [line for line in lines if line.school == school]
        for line in group:
            product = line.product.name if line.product else "Sin referencia para sumar"
            sku = line.product.sku if line.product else "—"
            price = cop(line.product.price) if line.product else "—"
            bill = (
                f"{qty_text(line.bill_qty)} {line.product.sell_unit}"
                if line.product and line.bill_qty is not None
                else "—"
            )
            parts.extend(
                [
                    f"### Ítem {line.item}. {line.description}",
                    "",
                    f"- Pedido: {qty_text(line.qty)} {line.unit}",
                    f"- Estado: {line.status.replace('_', ' ')}",
                    f"- Catálogo: {product}",
                    f"- SKU: {sku}",
                    f"- Precio unitario: {price}",
                    f"- Cantidad cotizada: {bill}",
                    f"- Total línea: {cop(line.line_total)}",
                    f"- Nota: {line.note}",
                    "",
                ]
            )
    parts.append(
        "Disponibilidad: las fichas usadas estaban marcadas en existencia "
        f"el {CAPTURED_ON}. Eso puede cambiar."
    )
    parts.append("")
    return "\n".join(parts)


def write_xlsx(lines: list[Line], path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Cotizacion"
    headers = [
        "Sede",
        "Item",
        "Descripcion solicitada",
        "Cantidad lista",
        "Unidad lista",
        "Estado",
        "SKU",
        "Producto catalogo",
        "Cantidad cotizada",
        "Unidad de venta",
        "Precio unitario",
        "Total linea",
        "Nota",
        "URL",
    ]
    ws.append(headers)
    for line in lines:
        ws.append(
            [
                line.school,
                line.item,
                line.description,
                line.qty,
                line.unit,
                line.status,
                line.product.sku if line.product else None,
                line.product.name if line.product else None,
                line.bill_qty,
                line.product.sell_unit if line.product else None,
                line.product.price if line.product else None,
                line.line_total,
                line.note,
                line.product.url if line.product else None,
            ]
        )
    header_fill = PatternFill("solid", fgColor="1F4E79")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=2, max_col=14):
        row[11].number_format = '#,##0'
        row[10].number_format = '#,##0'
        row[12].alignment = Alignment(wrap_text=True, vertical="top")
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    widths = [42, 8, 52, 16, 14, 14, 14, 55, 18, 16, 16, 16, 70, 55]
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:N{ws.max_row}"

    summary = wb.create_sheet("Resumen", 0)
    firm = sum_status(lines, "cotizado")
    caveat = sum_status(lines, "salvedad")
    summary.append(["Cotizacion convenio 080 de 2026"])
    summary.append([f"Fuente: {SOURCE}"])
    summary.append([f"Fecha de precios: {CAPTURED_ON}"])
    summary.append([])
    summary.append(["Concepto", "Valor COP"])
    summary.append(["Coincidencia de catalogo", firm])
    summary.append(["Con salvedad", caveat])
    summary.append(["Total cotizado", firm + caveat])
    summary.append(["Lineas sin precio", sum(1 for line in lines if line.status == "sin_precio")])
    summary.append([])
    summary.append(["Sede", "Cotizado", "Con salvedad", "Total sede", "Sin precio"])
    schools: list[str] = []
    for line in lines:
        if line.school not in schools:
            schools.append(line.school)
    for school in schools:
        group = [line for line in lines if line.school == school]
        school_firm = sum_status(group, "cotizado")
        school_caveat = sum_status(group, "salvedad")
        summary.append(
            [
                school,
                school_firm,
                school_caveat,
                school_firm + school_caveat,
                sum(1 for line in group if line.status == "sin_precio"),
            ]
        )
    for cell in summary[5]:
        cell.font = Font(bold=True)
    summary["B8"].font = Font(bold=True)
    for row in summary.iter_rows(min_row=6, max_row=8, min_col=2, max_col=2):
        for cell in row:
            cell.number_format = '#,##0'
    for row in summary.iter_rows(min_row=11, min_col=2, max_col=4):
        for cell in row:
            cell.number_format = '#,##0'
    summary.column_dimensions["A"].width = 48
    summary.column_dimensions["B"].width = 22
    summary.column_dimensions["C"].width = 22
    summary.column_dimensions["D"].width = 22
    summary.column_dimensions["E"].width = 16
    wb.save(path)


def main() -> None:
    lines = build_lines()
    firm = sum_status(lines, "cotizado")
    caveat = sum_status(lines, "salvedad")
    priced = [line for line in lines if line.line_total is not None]
    unpriced = [line for line in lines if line.line_total is None]
    assert all(line.status != "sin_precio" for line in priced)
    assert all(line.status == "sin_precio" for line in unpriced)
    assert abs(sum(line.line_total or 0 for line in priced) - (firm + caveat)) < 0.01
    # 120 m of 6 m tube is an exact 20. 16 m rounds up to 3.
    assert pieces(120, TUBE_6M) == 20
    assert pieces(16, TUBE_6M) == 3
    assert pieces(181, PROFILE_M) == 75
    assert pieces(254, PROFILE_M) == 105
    assert pieces(20 * LB_TO_G, NAIL_BAG_G) == 26

    md_path = OUT_DIR / "cotizacion.md"
    xlsx_path = OUT_DIR / "cotizacion.xlsx"
    md_path.write_text(render_markdown(lines), encoding="utf-8")
    write_xlsx(lines, xlsx_path)
    print(f"lines {len(lines)} priced {len(priced)} missing {len(unpriced)}")
    print(f"firm {firm:.0f}")
    print(f"caveat {caveat:.0f}")
    print(f"total {firm + caveat:.0f}")
    print(md_path)
    print(xlsx_path)


if __name__ == "__main__":
    main()

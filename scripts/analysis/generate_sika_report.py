#!/usr/bin/env python3
"""Generar reporte comprensivo PRODUCTOS SIKA en español"""
import json
import os
import sys


def generate_report(
    json_path="/home/yderf/sika_analysis_report.json",
    output_path="/home/yderf/REPORTE_SIKA_ESPANOL.md",
):
    if not os.path.exists(json_path):
        print(f"Error: No se encontro el archivo {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = []

    # ENCABEZADO
    report.append("# PRODUCTOS SIKA - Análisis Empresarial Comprensivo")
    report.append(f"**Generado:** {data.get('generated_at', 'N/A')}")
    report.append(f"**Filtro:** `{data.get('filter', 'SIKA')}`")
    report.append("")
    report.append("---")

    # RESUMEN EJECUTIVO
    report.append("## Resumen Ejecutivo")

    s24 = data.get("summary", {}).get("2024", {})
    s25 = data.get("summary", {}).get("2025", {})

    if s24 and s25:
        rev_growth = (
            (s25.get("net_revenue", 0) - s24.get("net_revenue", 0))
            / (s24.get("net_revenue", 1) or 1)
            * 100
        )
        report.append(f"- **Crecimiento de Ingresos:** {rev_growth:+.1f}% interanual")
    else:
        report.append("Datos interanuales insuficientes.")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"✅ Reporte en español generado: {output_path}")


if __name__ == "__main__":
    generate_report()

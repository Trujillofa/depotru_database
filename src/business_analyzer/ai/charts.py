"""
Smart Plotly chart generation for Vanna web UI.

Uses deterministic heuristics instead of LLM-generated plotly code,
which often picks wrong axes (e.g. scatter of Año vs Mes) or mixes
currency and percentage on a shared Y-axis.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from business_analyzer.ai.formatting import format_number

MONTH_ORDER = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

VALUE_KEYWORDS = (
    "ventas",
    "total",
    "ganancia",
    "facturacion",
    "revenue",
    "ingreso",
    "cantidad",
    "unidades",
    "costo",
    "profit",
)

PERCENTAGE_KEYWORDS = ("margen", "pct", "porcentaje", "percent", "%")

CURRENCY_KEYWORDS = (
    "ventas",
    "total",
    "ganancia",
    "facturacion",
    "revenue",
    "ingreso",
    "costo",
    "profit",
    "facturación",
)

RANKING_QUESTION_KEYWORDS = (
    "rentables",
    "ganancia",
    "clientes",
    "cliente",
    "vendedores",
    "vendedor",
    "desempeño",
    "desempeno",
    "top",
    "proveedores",
    "proveedor",
    "productos",
    "producto",
    "ranking",
    "mayor",
    "menor",
)

RANKING_LABEL_COLUMNS = frozenset(
    {
        "cliente",
        "vendedor",
        "descripcion",
        "proveedor",
        "producto",
        "marca",
        "categoria",
        "subcategoria",
        "ciudad",
        "departamento",
        "ubicacion",
    }
)

GEO_LABEL = "Ubicacion"
YEAR_MONTH_LABEL = "Periodo"

LABEL_PRIORITY = (
    "Descripcion",
    "descripcion",
    "Periodo",
    "periodo",
    "Fecha",
    "fecha",
    "Nombre_Mes",
    "nombre_mes",
    "Mes",
    "mes",
    "Dia",
    "dia",
    "Ubicacion",
    "ubicacion",
    "Categoria",
    "categoria",
    "Subcategoria",
    "subcategoria",
    "Ciudad",
    "ciudad",
    "Departamento",
    "departamento",
    "Producto",
    "producto",
    "ArticuloNombre",
    "articulonombre",
    "ArticulosNombre",
    "articulosnombre",
    "Tipo_Venta",
    "tipo_venta",
    "Cliente",
    "cliente",
    "Vendedor",
    "vendedor",
    "Proveedor",
    "proveedor",
    "Marca",
    "marca",
)

MONTH_ORDER_MAP = {name: idx for idx, name in enumerate(MONTH_ORDER)}

DF_PLOT_PREP_CODE = """\
df_plot = df.copy()
if 'Mes' in df_plot.columns:
    df_plot = df_plot.sort_values('Mes')
elif '{label_col}' in df_plot.columns:
    _month_order = {month_order_map}
    if set(df_plot['{label_col}'].dropna().unique()).issubset(set(_month_order)):
        df_plot = df_plot.assign(
            _month_order=df_plot['{label_col}'].map(lambda n: _month_order.get(n, 99))
        ).sort_values('_month_order').drop(columns='_month_order')
"""


class ChartStrategy(str, Enum):
    TIME_SERIES_VERTICAL = "time_series_vertical"
    HORIZONTAL_SINGLE = "horizontal_single"
    VERTICAL_SINGLE = "vertical_single"
    DUAL_AXIS = "dual_axis"
    LINE_FALLBACK = "line_fallback"


@dataclass(frozen=True)
class ChartPlan:
    strategy: ChartStrategy
    label_col: Optional[str]
    primary_col: str
    secondary_col: Optional[str] = None


def _is_useful_numeric(df: pd.DataFrame, col: str) -> bool:
    if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
        return False
    return df[col].nunique(dropna=True) > 1


def _numeric_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if _is_useful_numeric(df, c)]


def _is_percentage_column(df: pd.DataFrame, col: str) -> bool:
    col_lower = col.lower()
    if any(kw in col_lower for kw in PERCENTAGE_KEYWORDS):
        return True
    # Credit-term averages (e.g. Promedio_Dias_Credito) are days, not percentages.
    if "dias" in col_lower or "días" in col_lower or "days" in col_lower:
        return False
    if col_lower in ("mes", "month", "año", "ano", "year", "dia", "day"):
        return False
    if (
        col_lower.startswith("numero")
        or "cantidad" in col_lower
        or "compras" in col_lower
    ):
        return False
    series = df[col].dropna()
    if series.empty:
        return False
    if pd.api.types.is_integer_dtype(series):
        return False
    vmax, vmin = float(series.max()), float(series.min())
    return vmax <= 100 and vmin >= 0 and vmax < 1000


COUNT_COLUMN_NAMES = frozenset(
    {
        "ventas_este_mes",
        "numero_ventas",
        "numero_transacciones",
        "numero_compras",
        "total_transacciones",
    }
)


def _is_currency_column(df: pd.DataFrame, col: str) -> bool:
    col_lower = col.lower()
    if col_lower in COUNT_COLUMN_NAMES or col_lower.startswith("numero_"):
        return False
    if _is_percentage_column(df, col):
        return False
    if any(kw in col_lower for kw in CURRENCY_KEYWORDS):
        return True
    series = df[col].dropna()
    if series.empty:
        return False
    return float(series.max()) >= 1000


def _classify_value_columns(df: pd.DataFrame) -> Tuple[List[str], List[str], List[str]]:
    numeric = _numeric_columns(df)
    currency = [c for c in numeric if _is_currency_column(df, c)]
    percentage = [c for c in numeric if _is_percentage_column(df, c)]
    counts = [c for c in numeric if c not in currency and c not in percentage]
    return currency, percentage, counts


def _value_columns(df: pd.DataFrame) -> List[str]:
    currency, percentage, counts = _classify_value_columns(df)
    combined = currency + counts
    if combined:
        return combined[:3]
    return percentage[:1]


def _has_mixed_scales(df: pd.DataFrame, value_cols: Optional[List[str]] = None) -> bool:
    cols = value_cols if value_cols is not None else _numeric_columns(df)
    has_currency = any(_is_currency_column(df, c) for c in cols)
    has_percentage = any(_is_percentage_column(df, c) for c in cols)
    return has_currency and has_percentage


def _is_ranking_or_topn_question(question: Optional[str]) -> bool:
    if not question:
        return False
    q = question.lower()
    return any(kw in q for kw in RANKING_QUESTION_KEYWORDS)


def _is_comparison_question(question: Optional[str]) -> bool:
    if not question:
        return False
    q = question.lower()
    return " vs " in q or " versus " in q or " frente a " in q


def _select_primary_metric(
    df: pd.DataFrame,
    currency_cols: List[str],
    question: Optional[str] = None,
) -> Optional[str]:
    if not currency_cols:
        return None
    if question:
        q = question.lower()
        if "documento" in q or "tipo de documento" in q:
            for col in currency_cols:
                if "ventas_total" in col.lower():
                    return col
        if "diari" in q and "promedio" in q:
            for col in currency_cols:
                if "promedio_ventas_diarias" in col.lower():
                    return col
        if "últimos" in q or "ultimos" in q:
            for col in currency_cols:
                if "ventas_diarias" in col.lower():
                    return col
        if "vendedor" in q or "desempeño" in q or "desempeno" in q:
            for col in currency_cols:
                if "total_vendido" in col.lower():
                    return col
        if "sika center" in q or "calle 5" in q or "sede" in q:
            for col in currency_cols:
                if "ventas_totales" in col.lower():
                    return col
        if "comparando" in q or "comparar" in q:
            for col in currency_cols:
                if "ventas_anio_actual" in col.lower():
                    return col
        if "producto" in q and ("vendid" in q or "top" in q):
            if "cantidad" in q and "factur" not in q:
                for col in currency_cols:
                    if "cantidad" in col.lower():
                        return col
            for col in currency_cols:
                col_lower = col.lower()
                if "facturacion" in col_lower or col_lower == "ventas":
                    return col
        for col in currency_cols:
            col_lower = col.lower()
            if "ganancia" in q and "ganancia" in col_lower:
                return col
            if "facturacion" in q or "facturación" in q:
                if "facturacion" in col_lower or "facturación" in col_lower:
                    return col
            if "ventas" in q and "ventas" in col_lower:
                if col_lower in COUNT_COLUMN_NAMES:
                    continue
                return col
            if "ingreso" in q and ("ingreso" in col_lower or "revenue" in col_lower):
                return col
    return currency_cols[0]


def _avg_label_length(df: pd.DataFrame, label_col: str) -> float:
    labels = df[label_col].astype(str)
    return float(labels.str.len().mean())


def _prefers_horizontal(
    df: pd.DataFrame,
    label_col: str,
    question: Optional[str] = None,
) -> bool:
    if _is_ranking_or_topn_question(question):
        return True
    if label_col.lower() in RANKING_LABEL_COLUMNS:
        return True
    avg_len = _avg_label_length(df, label_col)
    max_len = float(df[label_col].astype(str).str.len().max())
    return avg_len > 15 or max_len > 20


def _geo_columns(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    dept = next((c for c in df.columns if c.lower() == "departamento"), None)
    city = next((c for c in df.columns if c.lower() == "ciudad"), None)
    return dept, city


def _year_month_columns(
    df: pd.DataFrame,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    año = next(
        (c for c in df.columns if str(c).lower() in ("año", "ano", "anio")),
        None,
    )
    mes = next((c for c in df.columns if str(c).lower() == "mes"), None)
    mes_name = next(
        (c for c in df.columns if str(c).lower() == "nombre_mes"),
        None,
    )
    return año, mes, mes_name


def _with_year_month_label(df: pd.DataFrame) -> pd.DataFrame:
    """Combine año + mes so multi-year monthly charts do not collapse."""
    año, mes, mes_name = _year_month_columns(df)
    if not año or not mes_name:
        return df
    out = df.copy()
    out[YEAR_MONTH_LABEL] = (
        out[mes_name].astype(str).str.strip() + " " + out[año].astype(str)
    )
    return out


def _with_geo_label(df: pd.DataFrame) -> pd.DataFrame:
    """Combine departamento + ciudad so charts do not collapse duplicate departments."""
    dept, city = _geo_columns(df)
    if not dept or not city:
        return df
    out = df.copy()
    out[GEO_LABEL] = (
        out[dept].astype(str).str.strip() + " — " + out[city].astype(str).str.strip()
    )
    return out


def _label_column(df: pd.DataFrame) -> Optional[str]:
    if GEO_LABEL in df.columns and df[GEO_LABEL].nunique(dropna=True) > 1:
        return GEO_LABEL
    for candidate in LABEL_PRIORITY:
        if candidate in df.columns and df[candidate].nunique(dropna=True) > 1:
            return candidate
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        if 1 < df[col].nunique(dropna=True) <= 50:
            return col
    return None


def _is_time_series(df: pd.DataFrame, label_col: Optional[str]) -> bool:
    if label_col and str(label_col).lower() == "fecha":
        return True
    if label_col and label_col in (
        YEAR_MONTH_LABEL,
        "Periodo",
        "periodo",
        "Nombre_Mes",
        "nombre_mes",
    ):
        return True
    año, mes, _ = _year_month_columns(df)
    if año and mes:
        return True
    if "Mes" in df.columns and label_col in ("Nombre_Mes", "nombre_mes", "Mes", "mes"):
        return True
    if label_col and set(df[label_col].dropna().unique()).issubset(set(MONTH_ORDER)):
        return True
    return False


def _sort_by_month(df: pd.DataFrame, label_col: str) -> pd.DataFrame:
    if str(label_col).lower() == "fecha" and label_col in df.columns:
        return df.sort_values(label_col)
    año, mes, _ = _year_month_columns(df)
    if año and mes:
        return df.sort_values([año, mes])
    if "Mes" in df.columns:
        return df.sort_values("Mes")
    if label_col in df.columns and set(df[label_col].dropna().unique()).issubset(
        set(MONTH_ORDER)
    ):
        sorted_df = df.copy()
        sorted_df["_month_order"] = sorted_df[label_col].map(
            lambda name: MONTH_ORDER_MAP.get(str(name), 99)
        )
        return sorted_df.sort_values("_month_order").drop(columns="_month_order")
    return df


def _formatted_bar_texts(df: pd.DataFrame, column: str) -> List[str]:
    return [format_number(value, column) for value in df[column]]


def _apply_colombian_value_axis(
    fig: go.Figure,
    *,
    horizontal: bool,
    hide_ticks: bool = False,
) -> go.Figure:
    """Avoid Plotly SI abbreviations (4.99k / 880.5M) on value axes."""
    axis_name = "xaxis" if horizontal else "yaxis"
    axis_kwargs = dict(
        tickformat=",.0f",
        separatethousands=True,
        showexponent="none",
    )
    if hide_ticks:
        axis_kwargs.update(showticklabels=False, showgrid=False, zeroline=False)
    fig.update_layout({axis_name: axis_kwargs})
    return fig


def _chart_title(question: Optional[str], metric_col: str) -> str:
    if question:
        return question[:80]
    return metric_col.replace("_", " ")


def _prepare_df(df: pd.DataFrame, plan: ChartPlan) -> pd.DataFrame:
    if plan.strategy == ChartStrategy.TIME_SERIES_VERTICAL and plan.label_col:
        return _sort_by_month(df.copy(), plan.label_col)
    if plan.strategy in (ChartStrategy.HORIZONTAL_SINGLE, ChartStrategy.DUAL_AXIS):
        return df.sort_values(plan.primary_col, ascending=True)
    return df.copy()


def _resolve_chart_plan(
    df: pd.DataFrame, question: Optional[str]
) -> Optional[ChartPlan]:
    if df is None or df.empty or len(df) < 2:
        return None

    label_col = _label_column(df)
    currency_cols, percentage_cols, _ = _classify_value_columns(df)
    all_numeric = _numeric_columns(df)
    if not all_numeric:
        return None

    if not label_col:
        if len(all_numeric) >= 1:
            return ChartPlan(ChartStrategy.LINE_FALLBACK, None, all_numeric[0])
        return None

    time_series = _is_time_series(df, label_col)
    mixed = _has_mixed_scales(df, all_numeric)
    ranking = _is_ranking_or_topn_question(question)
    comparison = _is_comparison_question(question)
    horizontal = _prefers_horizontal(df, label_col, question)

    if comparison and currency_cols:
        primary = _select_primary_metric(df, currency_cols, question) or currency_cols[0]
        return ChartPlan(ChartStrategy.VERTICAL_SINGLE, label_col, primary)

    if time_series:
        value_cols = _value_columns(df)
        if value_cols:
            metric = _select_primary_metric(df, value_cols, question) or value_cols[0]
            return ChartPlan(ChartStrategy.TIME_SERIES_VERTICAL, label_col, metric)

    if mixed:
        primary = _select_primary_metric(df, currency_cols, question)
        if primary and (ranking or horizontal):
            return ChartPlan(ChartStrategy.HORIZONTAL_SINGLE, label_col, primary)
        if primary and len(percentage_cols) == 1 and len(currency_cols) >= 1:
            return ChartPlan(
                ChartStrategy.DUAL_AXIS,
                label_col,
                primary,
                percentage_cols[0],
            )
        return None

    value_cols = _value_columns(df)
    if not value_cols:
        return None

    if len(value_cols) == 1:
        metric = value_cols[0]
        if horizontal and not time_series:
            return ChartPlan(ChartStrategy.HORIZONTAL_SINGLE, label_col, metric)
        return ChartPlan(ChartStrategy.VERTICAL_SINGLE, label_col, metric)

    if ranking or horizontal:
        primary = _select_primary_metric(df, value_cols, question) or value_cols[0]
        return ChartPlan(ChartStrategy.HORIZONTAL_SINGLE, label_col, primary)

    magnitudes = [float(df[c].max()) for c in value_cols]
    if max(magnitudes) / max(min(magnitudes), 1) > 10:
        primary = _select_primary_metric(df, value_cols, question) or value_cols[0]
        return ChartPlan(ChartStrategy.HORIZONTAL_SINGLE, label_col, primary)

    return None


def _apply_layout(
    fig: go.Figure,
    dark_mode: bool = False,
    horizontal: bool = False,
) -> go.Figure:
    template = "plotly_dark" if dark_mode else "plotly_white"
    fig.update_layout(
        template=template,
        font=dict(family="Roboto, sans-serif", size=13),
        margin=dict(l=48, r=24, t=56, b=48),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="y unified" if horizontal else "x unified",
    )
    if not horizontal:
        fig.update_xaxes(tickangle=-30)
    return fig


def _build_from_plan(
    df: pd.DataFrame,
    plan: ChartPlan,
    question: Optional[str],
    dark_mode: bool,
) -> go.Figure:
    df_plot = _prepare_df(df, plan)
    title = _chart_title(question, plan.primary_col)

    if plan.strategy == ChartStrategy.LINE_FALLBACK:
        fig = px.line(
            df_plot,
            y=plan.primary_col,
            title=title,
            markers=True,
            color_discrete_sequence=["#3b82f6"],
        )
        return _apply_layout(fig, dark_mode)

    if plan.strategy == ChartStrategy.TIME_SERIES_VERTICAL:
        bar_text = _formatted_bar_texts(df_plot, plan.primary_col)
        fig = px.bar(
            df_plot,
            x=plan.label_col,
            y=plan.primary_col,
            title=title,
            color_discrete_sequence=["#3b82f6"],
            text=bar_text,
        )
        fig.update_traces(texttemplate="%{text}", textposition="outside")
        fig.update_layout(xaxis_title="", yaxis_title="")
        fig = _apply_colombian_value_axis(fig, horizontal=False)
        return _apply_layout(fig, dark_mode, horizontal=False)

    if plan.strategy == ChartStrategy.VERTICAL_SINGLE:
        bar_text = _formatted_bar_texts(df_plot, plan.primary_col)
        fig = px.bar(
            df_plot,
            x=plan.label_col,
            y=plan.primary_col,
            title=title,
            color_discrete_sequence=["#3b82f6"],
            text=bar_text,
        )
        fig.update_traces(texttemplate="%{text}", textposition="outside")
        fig.update_layout(xaxis_title="", yaxis_title="")
        fig = _apply_colombian_value_axis(fig, horizontal=False)
        return _apply_layout(fig, dark_mode, horizontal=False)

    if plan.strategy == ChartStrategy.HORIZONTAL_SINGLE:
        bar_text = _formatted_bar_texts(df_plot, plan.primary_col)
        fig = px.bar(
            df_plot,
            y=plan.label_col,
            x=plan.primary_col,
            orientation="h",
            title=title,
            color_discrete_sequence=["#3b82f6"],
            text=bar_text,
        )
        fig.update_traces(
            texttemplate="%{text}",
            textposition="outside",
            name=plan.primary_col,
        )
        fig.update_layout(xaxis_title="", yaxis_title="")
        hide_ticks = bool(
            plan.label_col
            and plan.label_col.lower()
            in (
                "cliente",
                "tercerosnombres",
                "vendedor",
                "vendedorfactura",
                "descripcion",
            )
        )
        fig = _apply_colombian_value_axis(fig, horizontal=True, hide_ticks=hide_ticks)
        return _apply_layout(fig, dark_mode, horizontal=True)

    if plan.strategy == ChartStrategy.DUAL_AXIS and plan.secondary_col:
        labels = df_plot[plan.label_col].tolist()
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_plot[plan.primary_col],
                y=labels,
                name=plan.primary_col,
                orientation="h",
                marker_color="#3b82f6",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_plot[plan.secondary_col],
                y=labels,
                name=plan.secondary_col,
                mode="markers+lines",
                xaxis="x2",
                marker=dict(color="#f59e0b", size=8),
            )
        )
        fig.update_layout(
            title=title,
            xaxis=dict(title=plan.primary_col, side="bottom"),
            xaxis2=dict(
                title=plan.secondary_col,
                overlaying="x",
                side="top",
                showgrid=False,
            ),
            yaxis=dict(title=""),
            barmode="overlay",
        )
        return _apply_layout(fig, dark_mode, horizontal=True)

    raise ValueError(f"Unhandled chart plan: {plan}")


def _emit_plotly_code(plan: ChartPlan, question: Optional[str]) -> str:
    title = question or plan.primary_col
    label = plan.label_col

    if plan.strategy == ChartStrategy.LINE_FALLBACK:
        return (
            "import plotly.express as px\n"
            f"fig = px.line(df, y='{plan.primary_col}', title='{title}', markers=True, "
            "color_discrete_sequence=['#3b82f6'])\n"
        )

    if plan.strategy == ChartStrategy.TIME_SERIES_VERTICAL:
        prep = DF_PLOT_PREP_CODE.format(
            label_col=label,
            month_order_map=repr(MONTH_ORDER_MAP),
        )
        return (
            "import plotly.express as px\n"
            f"{prep}"
            f"fig = px.bar(df_plot, x='{label}', y='{plan.primary_col}', title='{title}', "
            "color_discrete_sequence=['#3b82f6'], text='" + plan.primary_col + "')\n"
            "fig.update_traces(texttemplate='%{y:,.0f}', textposition='outside')\n"
        )

    if plan.strategy == ChartStrategy.VERTICAL_SINGLE:
        return (
            "import plotly.express as px\n"
            "df_plot = df.copy()\n"
            f"fig = px.bar(df_plot, x='{label}', y='{plan.primary_col}', title='{title}', "
            "color_discrete_sequence=['#3b82f6'], text='" + plan.primary_col + "')\n"
            "fig.update_traces(texttemplate='%{y:,.0f}', textposition='outside')\n"
        )

    if plan.strategy == ChartStrategy.HORIZONTAL_SINGLE:
        return (
            "import plotly.express as px\n"
            f"df_plot = df.sort_values('{plan.primary_col}', ascending=True)\n"
            f"fig = px.bar(df_plot, y='{label}', x='{plan.primary_col}', orientation='h', "
            f"title='{title}', color_discrete_sequence=['#3b82f6'], text='{plan.primary_col}')\n"
            "fig.update_traces(texttemplate='%{x:,.0f}', textposition='outside')\n"
        )

    if plan.strategy == ChartStrategy.DUAL_AXIS:
        sec = plan.secondary_col
        return (
            "import plotly.graph_objects as go\n"
            f"df_plot = df.sort_values('{plan.primary_col}', ascending=True)\n"
            f"labels = df_plot['{label}'].tolist()\n"
            "fig = go.Figure()\n"
            f"fig.add_trace(go.Bar(x=df_plot['{plan.primary_col}'], y=labels, "
            f"name='{plan.primary_col}', orientation='h', marker_color='#3b82f6'))\n"
            f"fig.add_trace(go.Scatter(x=df_plot['{sec}'], y=labels, name='{sec}', "
            "mode='markers+lines', xaxis='x2'))\n"
            "fig.update_layout(xaxis2=dict(overlaying='x', side='top', showgrid=False))\n"
        )

    raise ValueError(f"Unhandled chart plan: {plan}")


def build_smart_figure(
    df: pd.DataFrame,
    question: Optional[str] = None,
    dark_mode: bool = False,
) -> Optional[go.Figure]:
    """Build a sensible chart from query results. Returns None if not chartable."""
    df = _with_year_month_label(_with_geo_label(df))
    plan = _resolve_chart_plan(df, question)
    if plan is None:
        return None
    return _build_from_plan(df, plan, question, dark_mode)


def build_plotly_code(
    df: pd.DataFrame, question: Optional[str] = None
) -> Optional[str]:
    """Return executable plotly code matching build_smart_figure heuristics."""
    df = _with_year_month_label(_with_geo_label(df))
    plan = _resolve_chart_plan(df, question)
    if plan is None:
        return None
    return _emit_plotly_code(plan, question)

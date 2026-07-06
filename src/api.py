"""
REST API for Business Data Analyzer.

Provides endpoints for programmatic access to business metrics.
"""

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedImport=false, reportDeprecated=false, reportImplicitRelativeImport=false, reportCallInDefaultInitializer=false, reportUntypedFunctionDecorator=false, reportArgumentType=false, reportExplicitAny=false

import asyncio
import os
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from business_analyzer.ai.circuit_breaker import breakers
from business_analyzer.analysis import UnifiedAnalyzer
from business_analyzer.analysis.predictive import forecast_demand, get_top_products
from business_analyzer.core.api_auth import require_api_key
from business_analyzer.core.database import Database
from config import Config

app = FastAPI(
    title="Business Data Analyzer API",
    description="Programmatic access to hardware store BI metrics",
    version="1.1.0",
)

_auth = [Depends(require_api_key)]


class AnalysisResult(BaseModel):
    status: str
    data: Dict[str, Any]
    provider_status: Dict[str, str]


class WhatIfRequest(BaseModel):
    product_id: str
    price_change_pct: float = 0.0
    cost_change_pct: float = 0.0
    volume_change_pct: float = 0.0


class WhatIfResponse(BaseModel):
    product_id: str
    original_margin_pct: float
    projected_margin_pct: float
    original_profit: float
    projected_profit: float
    assumption: str


class ForecastResponse(BaseModel):
    product_id: str
    forecast_days: int
    projected_units: int


class TopProductItem(BaseModel):
    product_id: str
    product_name: str
    total_qty: float


@app.get("/health")
async def health_check():
    """Check API and AI provider health (no auth required)."""
    provider_status = {name: breaker.state.value for name, breaker in breakers.items()}
    return {
        "status": "healthy",
        "providers": provider_status,
        "auth_required": bool(os.getenv("API_KEY", "").strip()),
    }


@app.get("/analyze", response_model=AnalysisResult, dependencies=_auth)
async def get_combined_analysis(
    limit: int = Query(1000, ge=1, le=100000),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get combined business analysis metrics."""
    provider_status = {name: breaker.state.value for name, breaker in breakers.items()}

    if not Config.has_direct_db_config() and not os.path.exists(Config.NCX_FILE_PATH):
        return {
            "status": "success",
            "data": {
                "message": "Analysis engine ready. Configure DB_HOST/DB_USER/DB_PASSWORD or NCX_FILE_PATH.",
                "requested_limit": limit,
                "date_range": {"start": start_date, "end": end_date},
            },
            "provider_status": provider_status,
        }

    def _run_analysis() -> Dict[str, Any]:
        with Database() as db:
            rows = db.fetch_data(limit=limit, start_date=start_date, end_date=end_date)
        analyzer = UnifiedAnalyzer(rows)
        return analyzer.analyze_all()

    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, _run_analysis)
        return {
            "status": "success",
            "data": data,
            "provider_status": provider_status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scenarios/what-if", response_model=WhatIfResponse, dependencies=_auth)
async def what_if_scenario(req: WhatIfRequest):
    """Run What-If scenario for a product."""

    def _run_what_if():
        excluded = Config.EXCLUDED_DOCUMENT_CODES
        placeholders = ", ".join(["%s"] * len(excluded))
        with Database() as db:
            rows = db.execute_query(
                f"""
                SELECT TOP 1
                    AVG((TotalSinIva - ValorCosto) / NULLIF(TotalSinIva, 0) * 100) as margin_pct,
                    AVG(TotalSinIva - ValorCosto) as profit
                FROM banco_datos
                WHERE ArticulosCodigo = %s
                  AND DocumentosCodigo NOT IN ({placeholders})
                """,  # nosec B608 — excluded codes from Config
                (req.product_id, *excluded),
            )
        if isinstance(rows, list) and rows:
            return rows[0]
        return None

    try:
        loop = asyncio.get_running_loop()
        row = await loop.run_in_executor(None, _run_what_if)

        if not row or row.get("margin_pct") is None:
            raise HTTPException(status_code=404, detail="Product not found")

        orig_margin = float(row["margin_pct"])
        orig_profit = float(row["profit"])

        projected_margin = orig_margin + req.price_change_pct - req.cost_change_pct
        projected_profit = orig_profit * (1 + req.volume_change_pct / 100)

        return WhatIfResponse(
            product_id=req.product_id,
            original_margin_pct=orig_margin,
            projected_margin_pct=projected_margin,
            original_profit=orig_profit,
            projected_profit=projected_profit,
            assumption=(
                f"Price {req.price_change_pct:+.1f}%, "
                f"Cost {req.cost_change_pct:+.1f}%, "
                f"Volume {req.volume_change_pct:+.1f}%"
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/forecast/top-products",
    response_model=List[TopProductItem],
    dependencies=_auth,
)
async def list_top_products(
    limit: int = Query(10, ge=1, le=100),
):
    """Top-selling products by quantity in the last 30 days."""

    def _run() -> List[Dict[str, Any]]:
        with Database() as db:
            return get_top_products(limit=limit, db=db)

    try:
        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(None, _run)
        return [
            TopProductItem(
                product_id=str(r.get("product_id", "")),
                product_name=str(r.get("product_name", "")),
                total_qty=float(r.get("total_qty") or 0),
            )
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecast/{product_id}", response_model=ForecastResponse, dependencies=_auth)
async def get_demand_forecast(
    product_id: str,
    days: int = Query(30, ge=1, le=365),
):
    """Forecast product demand using linear regression on recent sales."""

    def _run() -> int:
        with Database() as db:
            return forecast_demand(product_id, days=days, db=db)

    try:
        loop = asyncio.get_running_loop()
        units = await loop.run_in_executor(None, _run)
        return ForecastResponse(
            product_id=product_id,
            forecast_days=days,
            projected_units=units,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104

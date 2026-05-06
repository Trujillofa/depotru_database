"""
REST API for Business Data Analyzer.

Provides endpoints for programmatic access to business metrics.
"""
# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedImport=false, reportDeprecated=false, reportImplicitRelativeImport=false, reportCallInDefaultInitializer=false, reportUntypedFunctionDecorator=false, reportArgumentType=false, reportExplicitAny=false

import os
from typing import Any, Dict, Optional

import pymssql
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from business_analyzer.ai.circuit_breaker import breakers

# Import core functionality
from business_analyzer.analysis import UnifiedAnalyzer

app = FastAPI(
    title="Business Data Analyzer API",
    description="Programmatic access to hardware store BI metrics",
    version="1.0.0",
)


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


@app.get("/health")
async def health_check():
    """Check API and AI provider health."""
    provider_status = {name: breaker.state.value for name, breaker in breakers.items()}
    return {"status": "healthy", "providers": provider_status}


@app.get("/analyze", response_model=AnalysisResult)
async def get_combined_analysis(
    limit: int = Query(1000, ge=1, le=100000),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Get combined business analysis metrics.

    This endpoint currently returns a success message if no database connection
    is available, demonstrating the API structure.
    """
    try:
        # In a real scenario, we would fetch from DB here:
        # from business_analyzer.core.database import Database
        # with Database() as db:
        #     data = db.fetch_data(limit=limit, start_date=start_date, end_date=end_date)

        # Placeholder for demonstration
        mock_data = {
            "message": "Analysis engine ready. Live database connection required for real data.",
            "requested_limit": limit,
            "date_range": {"start": start_date, "end": end_date},
        }

        provider_status = {
            name: breaker.state.value for name, breaker in breakers.items()
        }

        return {
            "status": "success",
            "data": mock_data,
            "provider_status": provider_status,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scenarios/what-if", response_model=WhatIfResponse)
async def what_if_scenario(req: WhatIfRequest):
    """Run What-If scenario for a product."""
    try:
        conn = pymssql.connect(
            server=os.getenv("DB_SERVER", ""),
            user=os.getenv("DB_USER", ""),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "SmartBusiness"),
            port=os.getenv("DB_PORT", "1433"),
            login_timeout=30,
            timeout=180,
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT TOP 1
                AVG((TotalSinIva - ValorCosto) / TotalSinIva * 100) as margin_pct,
                AVG(TotalSinIva - ValorCosto) as profit
            FROM banco_datos
            WHERE ArticulosCodigo = %s
              AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
            """,
            (req.product_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row or row[0] is None:
            raise HTTPException(status_code=404, detail="Product not found")

        orig_margin = float(row[0])
        orig_profit = float(row[1])

        # Simple What-If: adjust margin by price/cost changes
        projected_margin = orig_margin + req.price_change_pct - req.cost_change_pct
        projected_profit = orig_profit * (1 + req.volume_change_pct / 100)

        return WhatIfResponse(
            product_id=req.product_id,
            original_margin_pct=orig_margin,
            projected_margin_pct=projected_margin,
            original_profit=orig_profit,
            projected_profit=projected_profit,
            assumption=f"Price {req.price_change_pct:+.1f}%, Cost {req.cost_change_pct:+.1f}%, Volume {req.volume_change_pct:+.1f}%",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104

"""
REST API for Business Data Analyzer.

Provides endpoints for programmatic access to business metrics.
"""

import os
from typing import Any, Dict, List, Optional

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104

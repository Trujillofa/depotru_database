"""
Engine B — Content-based similarity via TF-IDF on product names + brand.

Vectorises ArticulosNombre (+ marca + proveedor + categoria) with TF-IDF
(char_wb ngram) and finds the top-*top_n* most similar products using
cosine nearest-neighbour search (O(n) memory, not O(n²)).

Uses sklearn's NearestNeighbors (brute-force with cosine metric) to avoid
materialising the full pairwise similarity matrix.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set

from ...core.database import Database
from . import EngineResult

logger = logging.getLogger(__name__)

SOURCE = "text_similarity"

# We import sklearn lazily so the package can load even without it.
_SKLEARN_AVAILABLE: bool = False
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.neighbors import NearestNeighbors

    _SKLEARN_AVAILABLE = True
except ImportError:
    pass


def _fetch_product_texts(
    db: Database, active_skus: Optional[Set[str]] = None
) -> Dict[str, str]:
    """Fetch (SKU -> combined text) for all (or active) SKUs."""
    rows = db.execute_query(
        """
        SELECT DISTINCT
            ArticulosCodigo,
            ArticulosNombre,
            COALESCE(marca, '') AS marca,
            COALESCE(ArticulosReferencia, '') AS referencia,
            COALESCE(proveedor, '') AS proveedor,
            COALESCE(categoria, '') AS categoria,
            COALESCE(subcategoria, '') AS subcategoria
        FROM [SmartBusiness].[dbo].[banco_datos]
        WHERE ArticulosCodigo IS NOT NULL
          AND ArticulosCodigo <> ''
          AND ArticulosCodigo NOT IN ('0010040013','0120010001')
          AND DocumentosCodigo NOT IN ('XY','AS','TS','YX','ISC')
        """
    )
    raw: List[Dict[str, Any]] = rows if isinstance(rows, list) else []

    texts: Dict[str, str] = {}
    for r in raw:
        sku = r["ArticulosCodigo"].strip()
        if active_skus and sku not in active_skus:
            continue

        # Build a rich text field from multiple attributes
        parts = [
            str(r.get("ArticulosNombre", "") or ""),
            str(r.get("marca", "") or ""),
            str(r.get("referencia", "") or ""),
            str(r.get("proveedor", "") or ""),
            str(r.get("categoria", "") or ""),
            str(r.get("subcategoria", "") or ""),
        ]
        texts[sku] = " ".join(p.strip() for p in parts if p.strip())

    logger.info("  -> fetched %d product texts", len(texts))
    return texts


def run(
    db: Database,
    active_skus: Optional[Set[str]] = None,
    top_n: int = 50,
) -> List[EngineResult]:
    """Run TF-IDF similarity engine.

    Returns top-*top_n* similar pairs per SKU with cosine-similarity scores.
    Only pairs where BOTH SKUs are in *active_skus* are included.
    """
    if not _SKLEARN_AVAILABLE:
        logger.warning(
            "[Engine B] scikit-learn not available — skipping text similarity."
        )
        return []

    logger.info("[Engine B] Text similarity (TF-IDF on product names) …")
    t0 = time.time()

    product_texts = _fetch_product_texts(db, active_skus)
    if not product_texts:
        return []

    skus = list(product_texts.keys())
    corpus = [product_texts[s] for s in skus]

    # Fit TF-IDF
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        max_features=5000,
        min_df=2,
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform(corpus)

    elapsed = time.time() - t0
    logger.info(
        "  -> TF-IDF matrix %s, fitted in %.1f s",
        str(tfidf_matrix.shape),
        elapsed,
    )

    # Nearest-neighbour search — O(n) memory, no dense pairwise matrix
    n_neighbors = min(top_n + 1, len(skus))
    nn = NearestNeighbors(
        n_neighbors=n_neighbors,
        metric="cosine",
        algorithm="brute",
    )
    nn.fit(tfidf_matrix)
    distances, indices = nn.kneighbors(tfidf_matrix)

    logger.info(
        "  -> nearest-neighbour search done in %.1f s", time.time() - elapsed - t0
    )

    # Build results — cosine distance -> similarity (1 - distance)
    results: List[EngineResult] = []
    for i, sku_a in enumerate(skus):
        for rank in range(1, n_neighbors):  # skip self (rank 0)
            j = indices[i, rank]
            dist = distances[i, rank]
            score = round(float(1.0 - dist), 4)
            if score <= 0.0:
                continue
            sku_b = skus[j]
            results.append(
                {
                    "sku_a": sku_a,
                    "sku_b": sku_b,
                    "name_a": (
                        product_texts[sku_a].split(" ")[0]
                        if product_texts[sku_a]
                        else sku_a
                    ),
                    "name_b": (
                        product_texts[sku_b].split(" ")[0]
                        if product_texts[sku_b]
                        else sku_b
                    ),
                    "score": score,
                    "source": SOURCE,
                }
            )

    logger.info("  -> %d pairs generated", len(results))
    return results

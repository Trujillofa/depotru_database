"""inventory.sellable_qty sin Magento: stock real del ERP via catalog.stock.

Casos del documento integracion-stock-2026-11-03.md §8. Fake-only: sin BD.
"""

from unittest.mock import patch as mock_patch

import depotru_integrations.magento.client as magento_client
import depotru_tools.builtins as bff_builtins
from depotru_tools.builtins import _tool_sellable_qty_stub


class _Ctx:
    pass


def _ctx() -> _Ctx:
    return _Ctx()


_OK_RESULT = {
    "ok": True,
    "sede": "ambas",
    "results": [
        {
            "sku": "0020080002",
            "status": "ok",
            "sedes": {"neiva": "476.00000000", "florencia": None},
            "baja_rotacion": None,
        }
    ],
}


# 1. OK con Magento no configurado.
def test_sellable_qty_real_desde_j3() -> None:
    with mock_patch.object(
        magento_client.MagentoConfig, "from_env", staticmethod(lambda: None)
    ), mock_patch.object(
        bff_builtins, "catalog_stock", lambda ctx, p: dict(_OK_RESULT)
    ):
        out = _tool_sellable_qty_stub(_ctx(), {"sku": "0020080002"})

    assert out == {
        "sku": "0020080002",
        "sellable_qty": "476.00000000",
        "website_qty": "476.00000000",
        "in_stock": True,
        "status": "ok",
        "source": "j3_website_allowlist",
        "policy": "on-hand ERP en bodegas de venta web; no descuenta reservas",
    }


# 2. Cero real vs unavailable: la fila existe, saldo 0.
def test_sellable_qty_cero_real_no_es_unavailable() -> None:
    zero = {
        "ok": True,
        "results": [
            {
                "sku": "0010010018",
                "status": "ok",
                "sedes": {"neiva": "0", "florencia": None},
                "baja_rotacion": None,
            }
        ],
    }
    with mock_patch.object(
        magento_client.MagentoConfig, "from_env", staticmethod(lambda: None)
    ), mock_patch.object(bff_builtins, "catalog_stock", lambda ctx, p: dict(zero)):
        out = _tool_sellable_qty_stub(_ctx(), {"sku": "0010010018"})

    assert out["status"] == "ok"
    assert out["sellable_qty"] == "0"
    assert out["in_stock"] is False


# 3. El SKU no existe en el snapshot anual: desconocido, nunca 0.
def test_sellable_qty_sku_ausente_es_unknown() -> None:
    missing = {
        "ok": True,
        "results": [
            {
                "sku": "0000000000",
                "status": "no_encontrado",
                "sedes": {},
                "baja_rotacion": None,
            }
        ],
    }
    with mock_patch.object(
        magento_client.MagentoConfig, "from_env", staticmethod(lambda: None)
    ), mock_patch.object(bff_builtins, "catalog_stock", lambda ctx, p: dict(missing)):
        out = _tool_sellable_qty_stub(_ctx(), {"sku": "0000000000"})

    assert out == {
        "sku": "0000000000",
        "sellable_qty": None,
        "in_stock": None,
        "status": "unknown",
        "reason": "no_encontrado",
        "source": "j3",
        "policy": "sin dato: el SKU no es publicable con certeza",
    }


# 4. J3 caído: error estructurado, nunca una cifra inventada.
def test_sellable_qty_j3_caido_devuelve_error() -> None:
    def raise_it(ctx, p):
        raise RuntimeError("pymssql timeout")

    with mock_patch.object(
        magento_client.MagentoConfig, "from_env", staticmethod(lambda: None)
    ), mock_patch.object(bff_builtins, "catalog_stock", raise_it):
        out = _tool_sellable_qty_stub(_ctx(), {"sku": "0020080002"})

    assert out == {
        "sku": "0020080002",
        "sellable_qty": None,
        "in_stock": None,
        "status": "error",
        "reason": "j3_request_failed",
        "policy": "nunca inventar stock; sin dato si J3 no responde",
    }


# 5. El SKU está bloqueado por regla de stock: unknown, nunca cifra.
def test_sellable_qty_bloqueado_no_publica() -> None:
    blocked = {
        "ok": True,
        "results": [
            {
                "sku": "0020090002",
                "status": "bloqueado",
                "sedes": {},
                "baja_rotacion": None,
            }
        ],
    }
    with mock_patch.object(
        magento_client.MagentoConfig, "from_env", staticmethod(lambda: None)
    ), mock_patch.object(bff_builtins, "catalog_stock", lambda ctx, p: dict(blocked)):
        out = _tool_sellable_qty_stub(_ctx(), {"sku": "0020090002"})

    assert out["status"] == "unknown"
    assert out["reason"] == "bloqueado"
    assert out["sellable_qty"] is None

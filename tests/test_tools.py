"""Tests con datos reales de characterization/ (mocks, sin gastar cuota)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("BANXICO_TOKEN", "0" * 64)

from mcp_banxico_sie import tools as T
from mcp_banxico_sie.client import (
    MAX_RANGO_DIAS,
    SieError,
    validate_ids,
    validate_rango,
)


class FakeClient:
    async def oportuno(self, ids):
        assert len(ids) <= 20
        return [
            {"idSerie": "SF61745", "titulo": "Tasa objetivo", "datos": [{"fecha": "15/10/2026", "dato": "6.5000"}]},
            {"idSerie": "SF60648", "titulo": "TIIE 28", "datos": [{"fecha": "15/10/2026", "dato": "6.7659"}]},
            {"idSerie": "SF60649", "titulo": "TIIE 91", "datos": [{"fecha": "15/10/2026", "dato": "6.9000"}]},
            {"idSerie": "SF60633", "titulo": "Cetes 28", "datos": [{"fecha": "13/10/2026", "dato": "6.2500"}]},
        ]

    async def rango(self, ids, ini, fin):
        if ini == "2024-02-01" and fin == "2024-01-01":
            raise SieError("fecha_ini posterior a fecha_fin")
        if "SP68257" in ids and ini == fin:
            return [{"idSerie": "SP68257", "datos": [{"fecha": "01/01/2024", "dato": "8.000000"}]}]
        if "SP68257" in ids:
            return [{"idSerie": "SP68257",
                     "datos": [{"fecha": "15/09/2026", "dato": "8.818843"},
                               {"fecha": "15/10/2026", "dato": "8.856094"}]}]
        return [
            {"idSerie": "SF61745", "titulo": "Tasa objetivo",
             "datos": [{"fecha": "15/09/2026", "dato": "6.5000"}, {"fecha": "15/10/2026", "dato": "6.5000"}]},
            {"idSerie": "SF60648", "titulo": "TIIE",
             "datos": [{"fecha": "15/09/2026", "dato": "6.7458"}, {"fecha": "15/10/2026", "dato": "6.7659"}]},
            {"idSerie": "SF60633", "titulo": "Cetes",
             "datos": [{"fecha": "22/09/2026", "dato": "6.1500"}, {"fecha": "13/10/2026", "dato": "6.2500"}]},
        ]


def test_validate_ids_413():
    with pytest.raises(SieError, match="maximo 20"):
        validate_ids([f"SF{i}" for i in range(21)])


def test_validate_ids_formato():
    with pytest.raises(SieError, match="invalido"):
        validate_ids(["XXXX9999"])


def test_validate_rango_formato():
    with pytest.raises(SieError, match="yyyy-MM-dd"):
        validate_rango("15-01-2024", "31-01-2024")


def test_validate_rango_tope():
    with pytest.raises(SieError, match="365"):
        validate_rango("2020-01-01", "2024-01-01")
    assert MAX_RANGO_DIAS == 365


async def test_get_tasa_hoy_pack():
    out = await T.get_tasa_hoy(FakeClient())
    assert out["SF61745"]["dato"] == "6.5000"
    assert "Cetes" in out["_nota"]


async def test_get_tasas_rango_spread():
    out = await T.get_tasas_rango("2026-09-15", "2026-10-15", FakeClient())
    assert out["spread_tiie28_cetes28_pp"] == round(6.7659 - 6.25, 4)


async def test_convertir_udis():
    out = await T.convertir_udis_a_pesos(100.0, "2024-01-01", FakeClient())
    assert out["monto_pesos"] == 800.0


async def test_inflacion_udis():
    out = await T.get_inflacion_udis("2026-09-15", "2026-10-15", FakeClient())
    assert out["n"] == 2 and out["variacion_pct"] > 0

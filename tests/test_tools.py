"""Tests con datos reales de characterization/ (mocks, sin gastar cuota)."""
import os
import sys
from datetime import date as _date
from datetime import timedelta as _td

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
    assert "habiles" in out["_nota"]  # periodicidad explicita al LLM


async def test_convertir_udis():
    out = await T.convertir_udis_a_pesos(100.0, "2024-01-01", FakeClient())
    assert out["monto_pesos"] == 800.0


async def test_inflacion_udis():
    out = await T.get_inflacion_udis("2026-09-15", "2026-10-15", FakeClient())
    assert out["n"] == 2 and out["variacion_pct"] > 0


# ---- v2: mocks inline (sin red, sin cuota) ----

class FakeClientV2:
    async def oportuno(self, ids):
        if ids == ["SF43718", "SF60653"]:
            return [
                {"idSerie": "SF43718", "titulo": "FIX", "datos": [{"fecha": "15/10/2026", "dato": "18.5000"}]},
                {"idSerie": "SF60653", "titulo": "DOF", "datos": [{"fecha": "15/10/2026", "dato": "18.5100"}]},
            ]
        if ids == ["SF60633"]:
            return [{"idSerie": "SF60633", "titulo": "Cetes 28",
                     "datos": [{"fecha": "13/10/2026", "dato": "6.2500"}]}]
        if ids == ["SL11298"]:
            return [{"idSerie": "SL11298", "titulo": "Salario minimo",
                     "datos": [{"fecha": "01/08/2026", "dato": "315.0400"}]}]
        if ids == ["SF331451", "SF60648", "SF60649", "SF111916"]:
            return [{"idSerie": sid, "titulo": sid,
                     "datos": [{"fecha": "15/10/2026", "dato": "6.5000"}]} for sid in ids]
        raise AssertionError(f"oportuno inesperado: {ids}")

    async def rango(self, ids, ini, fin):
        d0, d1 = _date.fromisoformat(ini), _date.fromisoformat(fin)
        days = (d1 - d0).days + 1
        if "SL11298" in ids:  # mensual plano con un aumento al final: 278.80 -> 315.04
            pts = ["278.8000"] * 12 + ["315.0400"]
            return [{"idSerie": "SL11298", "datos": [
                {"fecha": f"01/{m:02d}/2026", "dato": v}
                for m, v in enumerate(pts, start=1)][:len(pts)]}]
        if "SF43707" in ids:  # semanal con coma de miles: "256,344.4"
            return [{"idSerie": "SF43707", "datos": [
                {"fecha": (d0 + _td(weeks=i)).strftime("%d/%m/%Y"),
                 "dato": f"{250000 + i * 100:,.1f}"} for i in range(53)]}]
        if "SR14138" in ids:  # mensual 3.5 -> 4.0
            return [{"idSerie": "SR14138", "datos": [
                {"fecha": f"01/{m:02d}/2026", "dato": f"{3.5 + (m - 1) * 0.05:.2f}"}
                for m in range(1, 13)]}]
        if set(ids) == {"SG59", "SG80", "SG81", "SG79", "SG55"}:
            return [{"idSerie": sid, "titulo": sid, "datos": [
                {"fecha": "01/09/2026", "dato": "1,000.0"},
                {"fecha": "01/10/2026", "dato": "1,100.0"}]} for sid in ids]
        if set(ids) == {"SF406262", "SF406263", "SF406458"}:
            return [{"idSerie": sid, "titulo": sid, "datos": [
                {"fecha": "01/09/2026", "dato": "500.0"},
                {"fecha": "01/10/2026", "dato": "550.0"}]} for sid in ids]
        if "SP68257" in ids:  # UDIS diaria: +0.001/dia
            return [{"idSerie": "SP68257", "datos": [
                {"fecha": (d0 + _td(days=i)).strftime("%d/%m/%Y"),
                 "dato": f"{8.0 + i * 0.001:.6f}"} for i in range(days)]}]
        if ids == ["SF43718"] and days > 1:  # FIX 30d: +0.01/dia
            return [{"idSerie": "SF43718", "datos": [
                {"fecha": (d0 + _td(days=i)).strftime("%d/%m/%Y"),
                 "dato": f"{18.0 + i * 0.01:.4f}"} for i in range(days)]}]
        if set(ids) == {"SF46410", "SF46406", "SF46407", "SF60632"}:
            return [{"idSerie": sid, "titulo": sid, "datos": [
                {"fecha": "15/09/2026", "dato": "20.0000"},
                {"fecha": "10/10/2026", "dato": "N/E"},  # dia sin cotizacion: se salta
                {"fecha": "15/10/2026", "dato": "20.5000"}]} for sid in ids]
        return [{"idSerie": ids[0], "datos": [{"fecha": "01/10/2026", "dato": "18.5000"}]}]


async def test_get_dolar_hoy_contexto():
    out = await T.get_dolar_hoy(FakeClientV2())
    assert out["SF43718"]["dato"] == "18.5000"
    assert out["SF60653"]["dato"] == "18.5100"
    assert out["contexto_30d"]["n"] >= 20
    assert "liquidacion" in out["_nota"]  # vigencia DOF explicada al LLM


async def test_get_divisas_rango():
    out = await T.get_divisas_rango("2026-09-15", "2026-10-15", FakeClientV2())
    assert out["SF46410"]["variacion_pct"] == 2.5
    assert out["SF46410"]["n"] == 2  # el 'N/E' no cuenta
    assert "habiles" in out["_nota"]


async def test_convertir_mxn_divisa():
    out = await T.convertir_mxn_divisa(1000.0, "usd", "2026-10-01", FakeClientV2())
    assert out["divisa"] == "USD" and out["monto_divisa"] == round(1000 / 18.5, 2)
    with pytest.raises(SieError, match="no soportada"):
        await T.convertir_mxn_divisa(1000.0, "XXX", "2026-10-01", FakeClientV2())


async def test_inflacion_ytd():
    out = await T.get_inflacion_ytd(FakeClientV2())
    assert out["n"] >= 2 and out["variacion_pct"] > 0


async def test_estimar_rendimiento_cetes():
    out = await T.estimar_rendimiento_cetes(10000.0, FakeClientV2())
    assert out["rendimiento_estimado_28d"] == round(10000 * 0.0625 * 28 / 360, 2)
    assert "semanal" in out["nota"]


async def test_ajustar_por_udis():
    out = await T.ajustar_por_udis(5000.0, "2024-01-01", "2024-06-01", FakeClientV2())
    assert out["factor"] > 1
    assert out["monto_ajustado"] == round(5000 * out["factor"], 2)


async def test_get_salario_minimo():
    out = await T.get_salario_minimo(FakeClientV2())
    assert out["valor"] == 315.04
    assert out["ultimo_incremento"]["pct"] == round((315.04 / 278.80 - 1) * 100, 2)
    assert "rezago" in out["nota"]


async def test_get_reservas_coma_miles():
    out = await T.get_reservas(FakeClientV2())
    assert out["valor_mdd"] == 250000 + 52 * 100
    assert out["variacion_semanal"]["monto_mdd"] == 100.0
    assert "variacion_anual" in out


async def test_get_curva_tiie():
    out = await T.get_curva_tiie(FakeClientV2())
    assert {k for k in out if k.startswith("SF")} == {"SF331451", "SF60648", "SF60649", "SF111916"}


async def test_get_finanzas_publicas():
    out = await T.get_finanzas_publicas("2026-09-01", "2026-10-15", FakeClientV2())
    assert out["SG80"]["max"] == 1100.0  # coma de miles sanitizada


async def test_get_spei():
    out = await T.get_spei("2026-09-01", "2026-10-15", FakeClientV2())
    assert out["SF406262"]["n"] == 2


async def test_get_expectativa_inflacion():
    out = await T.get_expectativa_inflacion(FakeClientV2())
    assert out["valor_pct"] == 4.05 and out["hace_12m"]["valor_pct"] == 3.5

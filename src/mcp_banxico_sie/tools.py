"""Tools B (tasas) + C (UDIS). Todo read-only. ES+EN docstrings."""
from __future__ import annotations

from pydantic import BaseModel, Field

from . import config
from .client import BanxicoClient, SieError


class RangoIn(BaseModel):
    fecha_ini: str = Field(..., description="Inicio yyyy-MM-dd", pattern=r"^\d{4}-\d{2}-\d{2}$")
    fecha_fin: str = Field(..., description="Fin yyyy-MM-dd", pattern=r"^\d{4}-\d{2}-\d{2}$")


# Atribucion exigida por la salvedad de uso de Banxico: toda informacion
# reproducida debe citar fuente + URL para verificacion de terceros.
FUENTE = "Banco de Mexico - https://www.banxico.org.mx/SieAPIRest/service/v1/"


def _obs_float(dato: str) -> float:
    return float(dato)


def _resumen_obs(datos: list[dict]) -> dict:
    vals = [(d["fecha"], _obs_float(d["dato"])) for d in datos if "dato" in d]
    if not vals:
        return {"n": 0, "nota": "Serie sin datos en el rango (caso fecha invertida/huecos)."}
    fechas = [v[0] for v in vals]
    nums = [v[1] for v in vals]
    return {
        "n": len(vals),
        "primera": {"fecha": fechas[0], "dato": nums[0]},
        "ultima": {"fecha": fechas[-1], "dato": nums[-1]},
        "min": min(nums),
        "max": max(nums),
        "variacion_pp": round(nums[-1] - nums[0], 4),
    }


async def get_tasa_hoy(client: BanxicoClient | None = None) -> dict:
    """Tasa de referencia hoy: objetivo + TIIE 28/91 + Cetes 28 en 1 llamada (ES: tasa hoy / EN: reference rates today)."""
    c = client or BanxicoClient()
    series = await c.oportuno([config.TASA_OBJETIVO, config.TIIE_28, config.TIIE_91, config.CETES_28])
    out = {}
    for s in series:
        d = (s.get("datos") or [{}])[0]
        out[s.get("idSerie")] = {"titulo": s.get("titulo"), "fecha": d.get("fecha"), "dato": d.get("dato")}
    out["_nota"] = "Cetes es subasta semanal: su fecha suele ir 2-5 dias atras (medido 13/10 vs 15/10). TIIE solo habiles."
    out["fuente"] = FUENTE
    return out


async def get_tasas_rango(fecha_ini: str, fecha_fin: str, client: BanxicoClient | None = None) -> dict:
    """Tasas en rango + spread TIIE28-Cetes y ultimo cambio de tasa objetivo (max 365d)."""
    c = client or BanxicoClient()
    series = await c.rango([config.TASA_OBJETIVO, config.TIIE_28, config.CETES_28], fecha_ini, fecha_fin)
    res: dict = {}
    for s in series:
        res[s.get("idSerie")] = {"titulo": s.get("titulo"), **_resumen_obs(s.get("datos") or [])}
    # spread con las ultimas observaciones disponibles de cada una
    try:
        tiie = res.get(config.TIIE_28, {}).get("ultima", {}).get("dato")
        cetes = res.get(config.CETES_28, {}).get("ultima", {}).get("dato")
        if tiie is not None and cetes is not None:
            res["spread_tiie28_cetes28_pp"] = round(float(tiie) - float(cetes), 4)
    except (ValueError, TypeError):
        pass
    res["fuente"] = FUENTE
    return res


async def get_udis_hoy(client: BanxicoClient | None = None) -> dict:
    """Valor UDIS oportuno. OJO: Banxico publica UDIS a futuro (medido +10 dias)."""
    c = client or BanxicoClient()
    series = await c.oportuno([config.UDIS])
    s = series[0] if series else {}
    d = (s.get("datos") or [{}])[0]
    return {"idSerie": config.UDIS, "titulo": s.get("titulo", "Valor de UDIS"),
            "fecha": d.get("fecha"), "dato": d.get("dato"), "fuente": FUENTE,
            "nota": "La fecha puede ser futura: es publicacion adelantada oficial, no error."}


async def convertir_udis_a_pesos(monto_udis: float, fecha: str, client: BanxicoClient | None = None) -> dict:
    """Convierte monto en UDIS a pesos con el valor de la fecha exacta (formato yyyy-MM-dd)."""
    if monto_udis <= 0:
        raise SieError("monto_udis debe ser > 0.")
    c = client or BanxicoClient()
    series = await c.rango([config.UDIS], fecha, fecha)
    datos = (series[0].get("datos") or []) if series else []
    if not datos:
        raise SieError(f"Sin valor UDIS para {fecha} (fin de serie o fecha invalida).")
    valor = float(datos[0]["dato"])
    return {"fecha": datos[0]["fecha"], "valor_udis": valor, "fuente": FUENTE,
            "monto_udis": monto_udis, "monto_pesos": round(monto_udis * valor, 2)}


async def get_inflacion_udis(fecha_ini: str, fecha_fin: str, client: BanxicoClient | None = None) -> dict:
    """Variacion % UDIS en el periodo como proxy de inflacion acumulada (serie diaria continua)."""
    c = client or BanxicoClient()
    series = await c.rango([config.UDIS], fecha_ini, fecha_fin)
    datos = (series[0].get("datos") or []) if series else []
    if len(datos) < 2:
        return {"n": len(datos), "fuente": FUENTE, "nota": "Se requieren >=2 observaciones."}
    ini = float(datos[0]["dato"])
    fin_v = float(datos[-1]["dato"])
    var_pct = round((fin_v / ini - 1) * 100, 4)
    return {"n": len(datos), "ini": datos[0], "fin": datos[-1], "variacion_pct": var_pct,
            "fuente": FUENTE, "nota": "UDIS es diaria continua (31/31 medido); ideal para acumulados."}

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


def _limpia_num(dato: str) -> str:
    return str(dato).replace(",", "").strip()  # reservas trae coma de miles: "256,344.4"


def _obs_float(dato: str) -> float:
    try:
        return float(_limpia_num(dato))
    except (ValueError, TypeError):
        raise SieError(f"Dato no numerico '{dato}' (dia sin cotizacion: fin de semana/feriado).")


def _numericas(datos: list[dict]) -> list[tuple[str, float]]:
    """Observaciones con dato numerico; salta 'N/E' y huecos (medido en divisas)."""
    vals = []
    for d in datos:
        if "dato" not in d:
            continue
        try:
            vals.append((d["fecha"], float(_limpia_num(d["dato"]))))
        except (ValueError, TypeError):
            continue
    return vals


def _resumen_obs(datos: list[dict]) -> dict:
    vals = _numericas(datos)
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
    res["_nota"] = "Tasa objetivo y TIIE diarias (habiles); Cetes subasta semanal (pocos puntos)."
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
    valor = _obs_float(datos[0]["dato"])
    return {"fecha": datos[0]["fecha"], "valor_udis": valor, "fuente": FUENTE,
            "monto_udis": monto_udis, "monto_pesos": round(monto_udis * valor, 2)}


async def get_inflacion_udis(fecha_ini: str, fecha_fin: str, client: BanxicoClient | None = None) -> dict:
    """Variacion % UDIS en el periodo como proxy de inflacion acumulada (serie diaria continua)."""
    c = client or BanxicoClient()
    series = await c.rango([config.UDIS], fecha_ini, fecha_fin)
    datos = (series[0].get("datos") or []) if series else []
    if len(datos) < 2:
        return {"n": len(datos), "fuente": FUENTE, "nota": "Se requieren >=2 observaciones."}
    ini = _obs_float(datos[0]["dato"])
    fin_v = _obs_float(datos[-1]["dato"])
    var_pct = round((fin_v / ini - 1) * 100, 4)
    return {"n": len(datos), "ini": datos[0], "fin": datos[-1], "variacion_pct": var_pct,
            "fuente": FUENTE, "nota": "UDIS es diaria continua (31/31 medido); ideal para acumulados."}


# ---- v2: finanzas cotidianas + divisas (sin jerga, sin prediccion) ----

async def get_dolar_hoy(client: BanxicoClient | None = None) -> dict:
    """Dolar hoy: FIX + DOF oportuno con contexto FIX 30 dias (promedio/min/max). / USD today with 30d context."""
    from datetime import date, timedelta
    c = client or BanxicoClient()
    series = await c.oportuno([config.DOLAR_FIX, config.DOLAR_DOF])
    out = {}
    for s in series:
        d = (s.get("datos") or [{}])[0]
        out[s.get("idSerie")] = {"titulo": s.get("titulo"), "fecha": d.get("fecha"), "dato": d.get("dato")}
    hoy = date.today()
    ctx = await c.rango([config.DOLAR_FIX], (hoy - timedelta(days=30)).isoformat(), hoy.isoformat())
    datos = (ctx[0].get("datos") or []) if ctx else []
    vals = [v[1] for v in _numericas(datos)]
    out["contexto_30d"] = (
        {"n": len(vals), "promedio": round(sum(vals) / len(vals), 4),
         "min": min(vals), "max": max(vals),
         "variacion_pp": round(vals[-1] - vals[0], 4)} if vals else {"n": 0}
    )
    out["fuente"] = FUENTE
    out["_nota"] = ("Contexto informativo, no recomendacion. FIX solo dias habiles; "
                    "DOF es fecha de liquidacion (publicacion adelantada oficial, puede ser futura).")
    return out


async def get_divisas_rango(fecha_ini: str, fecha_fin: str, client: BanxicoClient | None = None) -> dict:
    """Euro, yen, libra y dolar canadiense en rango con variacion %. / EUR/JPY/GBP/CAD range."""
    c = client or BanxicoClient()
    ids = [config.DIVISAS[k] for k in ("EUR", "JPY", "GBP", "CAD")]
    series = await c.rango(ids, fecha_ini, fecha_fin)
    res: dict = {}
    for s in series:
        datos = s.get("datos") or []
        base = _resumen_obs(datos)
        nums = _numericas(datos)
        if len(nums) >= 2:
            base["variacion_pct"] = round((nums[-1][1] / nums[0][1] - 1) * 100, 4)
        res[s.get("idSerie")] = {"titulo": s.get("titulo"), **base}
    res["fuente"] = FUENTE
    res["_nota"] = "Diarias (habiles); 'N/E' = dia sin cotizacion y no cuenta."
    return res


async def convertir_mxn_divisa(monto_mxn: float, divisa: str, fecha: str,
                               client: BanxicoClient | None = None) -> dict:
    """Convierte pesos a divisa (USD/EUR/JPY/GBP/CAD) al tipo de cambio de la fecha exacta. / MXN to FX."""
    if monto_mxn <= 0:
        raise SieError("monto_mxn debe ser > 0.")
    div = (divisa or "").strip().upper()
    if div not in config.DIVISAS:
        raise SieError(f"Divisa '{divisa}' no soportada. Usa una de: {', '.join(sorted(config.DIVISAS))}.")
    c = client or BanxicoClient()
    series = await c.rango([config.DIVISAS[div]], fecha, fecha)
    datos = (series[0].get("datos") or []) if series else []
    if not datos:
        raise SieError(f"Sin tipo de cambio {div} para {fecha} (fin de semana/feriado o fecha invalida).")
    tc = _obs_float(datos[0]["dato"])
    return {"fecha": datos[0]["fecha"], "divisa": div, "tipo_cambio": tc, "fuente": FUENTE,
            "monto_mxn": monto_mxn, "monto_divisa": round(monto_mxn / tc, 2)}


async def get_inflacion_ytd(client: BanxicoClient | None = None) -> dict:
    """Inflacion acumulada del anio en un clic: UDIS del 1 de enero a hoy. / Year-to-date UDIS inflation."""
    from datetime import date
    hoy = date.today()
    out = await get_inflacion_udis(f"{hoy.year}-01-01", hoy.isoformat(), client)
    out["fuente"] = FUENTE
    return out


async def estimar_rendimiento_cetes(monto_mxn: float, client: BanxicoClient | None = None) -> dict:
    """Estima cuanto daria el monto a 28 dias con la ultima subasta de Cetes 28. / Cetes savings estimate."""
    if monto_mxn <= 0:
        raise SieError("monto_mxn debe ser > 0.")
    c = client or BanxicoClient()
    series = await c.oportuno([config.CETES_28])
    datos = (series[0].get("datos") or []) if series else []
    if not datos:
        raise SieError("Sin dato oportuno de Cetes 28.")
    tasa = _obs_float(datos[0]["dato"])
    estimado = round(monto_mxn * (tasa / 100) * (28 / 360), 2)
    return {"fecha_subasta": datos[0]["fecha"], "tasa_pct": tasa, "fuente": FUENTE,
            "monto_mxn": monto_mxn, "rendimiento_estimado_28d": estimado,
            "nota": "Estimacion con la ultima subasta semanal (plazo 28 dias, base 360). No garantizado."}


async def ajustar_por_udis(monto: float, fecha_ini: str, fecha_fin: str,
                           client: BanxicoClient | None = None) -> dict:
    """Actualiza cualquier cantidad (renta, deuda, sueldo) por UDIS entre dos fechas. / UDIS adjustment."""
    if monto <= 0:
        raise SieError("monto debe ser > 0.")
    c = client or BanxicoClient()
    series = await c.rango([config.UDIS], fecha_ini, fecha_fin)
    datos = (series[0].get("datos") or []) if series else []
    if len(datos) < 2:
        return {"n": len(datos), "fuente": FUENTE, "nota": "Se requieren >=2 observaciones."}
    ini = _obs_float(datos[0]["dato"])
    fin_v = _obs_float(datos[-1]["dato"])
    factor = round(fin_v / ini, 6)
    return {"n": len(datos), "ini": datos[0], "fin": datos[-1], "fuente": FUENTE,
            "monto_original": monto, "factor": factor,
            "monto_ajustado": round(monto * factor, 2)}


# ---- v3: salario minimo + reservas (lenguaje simple, con fecha del dato) ----

async def get_salario_minimo(client: BanxicoClient | None = None) -> dict:
    """Salario minimo vigente + ultimo incremento ($ y %). / Current minimum wage."""
    from datetime import date, timedelta
    c = client or BanxicoClient()
    series = await c.oportuno([config.SALARIO_MINIMO])
    d = ((series[0].get("datos") or [{}])[0]) if series else {}
    hoy = date.today()
    hist = await c.rango([config.SALARIO_MINIMO],
                         (hoy - timedelta(days=365)).isoformat(), hoy.isoformat())
    nums = _numericas((hist[0].get("datos") or []) if hist else [])
    out = {"valor": _obs_float(d.get("dato", "")), "fecha": d.get("fecha"),
           "fuente": FUENTE,
           "nota": "Serie mensual con rezago (medido ~2.5 meses): la fecha indica la vigencia, no es 'de hoy'."}
    if len(nums) >= 2:
        for i in range(len(nums) - 1, 0, -1):  # ultimo cambio hacia atras
            if nums[i][1] != nums[i - 1][1]:
                out["ultimo_incremento"] = {
                    "fecha": nums[i][0], "de": nums[i - 1][1], "a": nums[i][1],
                    "monto": round(nums[i][1] - nums[i - 1][1], 2),
                    "pct": round((nums[i][1] / nums[i - 1][1] - 1) * 100, 2)}
                break
    return out


async def get_reservas(client: BanxicoClient | None = None) -> dict:
    """Reservas internacionales: ultimo dato semanal + variacion semanal y anual. / FX reserves."""
    from datetime import date, timedelta
    c = client or BanxicoClient()
    hoy = date.today()
    series = await c.rango([config.RESERVAS],
                           (hoy - timedelta(days=365)).isoformat(), hoy.isoformat())
    datos = (series[0].get("datos") or []) if series else []
    nums = _numericas(datos)
    if len(nums) < 2:
        return {"n": len(nums), "fuente": FUENTE, "nota": "Se requieren >=2 observaciones."}
    ult_f, ult = nums[-1]
    ant_f, ant = nums[-2]
    out = {"valor_mdd": ult, "fecha": ult_f, "fuente": FUENTE,
           "variacion_semanal": {"fecha_previa": ant_f, "monto_mdd": round(ult - ant, 1),
                                 "pct": round((ult / ant - 1) * 100, 3)}}
    if len(nums) >= 52:
        anual_f, anual = nums[-52]
        out["variacion_anual"] = {"fecha_base": anual_f,
                                  "monto_mdd": round(ult - anual, 1),
                                  "pct": round((ult / anual - 1) * 100, 2)}
    out["nota"] = "Millones de USD, corte semanal. Informativo, no pronostico."
    return out


# ---- v4: curva, finanzas publicas, SPEI, expectativas ----

async def get_curva_tiie(client: BanxicoClient | None = None) -> dict:
    """Curva TIIE en un lote: fondeo 1d + 28/91/182. / TIIE curve in one pack."""
    c = client or BanxicoClient()
    ids = [config.TIIE_FONDEO, config.TIIE_28, config.TIIE_91, config.TIIE_182]
    series = await c.oportuno(ids)
    out = {}
    for s in series:
        d = (s.get("datos") or [{}])[0]
        out[s.get("idSerie")] = {"titulo": s.get("titulo"), "fecha": d.get("fecha"), "dato": d.get("dato")}
    out["fuente"] = FUENTE
    out["_nota"] = "Fondeo es overnight (dia habil anterior); resto fecha de determinacion."
    return out


async def get_finanzas_publicas(fecha_ini: str, fecha_fin: str,
                                client: BanxicoClient | None = None) -> dict:
    """Gasto primario + ISR + IVA + IEPS x2 en rango (mensual). / Public finances."""
    c = client or BanxicoClient()
    ids = [config.GASTO_PRIMARIO, config.ISR, config.IVA, config.IEPS_GAS, config.IEPS_OTRO]
    series = await c.rango(ids, fecha_ini, fecha_fin)
    res: dict = {}
    for s in series:
        res[s.get("idSerie")] = {"titulo": s.get("titulo"), **_resumen_obs(s.get("datos") or [])}
    res["fuente"] = FUENTE
    res["_nota"] = "Millones de pesos, mensual con rezago. Flujos de caja del Gobierno Federal."
    return res


async def get_spei(fecha_ini: str, fecha_fin: str, client: BanxicoClient | None = None) -> dict:
    """SPEI mensual: monto/numero enviadas + monto recibidas. / SPEI transfers."""
    c = client or BanxicoClient()
    ids = [config.SPEI_ENV_MONTO, config.SPEI_ENV_NUM, config.SPEI_REC_MONTO]
    series = await c.rango(ids, fecha_ini, fecha_fin)
    res: dict = {}
    for s in series:
        res[s.get("idSerie")] = {"titulo": s.get("titulo"), **_resumen_obs(s.get("datos") or [])}
    res["fuente"] = FUENTE
    res["_nota"] = "Mensual. Montos en millones de pesos."
    return res


async def get_expectativa_inflacion(client: BanxicoClient | None = None) -> dict:
    """Inflacion que esperan los especialistas al cierre del anio (media). / Expected inflation."""
    from datetime import date, timedelta
    c = client or BanxicoClient()
    hoy = date.today()
    series = await c.rango([config.EXP_INFLACION],
                           (hoy - timedelta(days=365)).isoformat(), hoy.isoformat())
    datos = (series[0].get("datos") or []) if series else []
    nums = _numericas(datos)
    if not nums:
        return {"n": 0, "fuente": FUENTE, "nota": "Sin observaciones."}
    out = {"valor_pct": nums[-1][1], "fecha": nums[-1][0], "fuente": FUENTE,
           "nota": "Media de especialistas del sector privado al cierre del anio en curso. Expectativa, no pronostico."}
    if len(nums) >= 12:
        out["hace_12m"] = {"fecha": nums[-12][0], "valor_pct": nums[-12][1]}
    return out

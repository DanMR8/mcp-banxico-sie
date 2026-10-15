"""Cliente Banxico SIE-API con los guards que dicto la caracterizacion.

Reglas (ver characterization/results/):
- Auth: header Bmx-Token (64 chars). Sin token == token invalido (400).
- Pack hasta 20 IDs por llamada; >20 da 413.
- Forzar locale=es + JSON para parsing determinista (locale=en cambia fechas a MM/DD).
- Request yyyy-MM-dd, response dd/MM/yyyy (es).
- Fecha invertida -> 200 sin campo `datos` => "sin datos", no error.
- 400 discute por `mensaje`: Token invalido | Limite superado (+secondsToReset) | Formato fecha | Formato series.
- Cache: oportuno 12h, metadata 7d. Historico full prohibido en tools (tope rango 365d).
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime

import httpx

from . import config

log = logging.getLogger(__name__)

ID_RE = re.compile(r"^[A-Z]{1,3}[0-9]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_SERIES = 20
MAX_RANGO_DIAS = 365

# Cache simple {key: (expire_ts, value)}
_cache: dict[str, tuple[float, object]] = {}
_OPORTUNO_TTL = 12 * 3600
_METADATA_TTL = 7 * 24 * 3600


class SieError(Exception):
    """Error de negocio del API (ya mapeado a mensaje accionable)."""


def validate_ids(ids: list[str]) -> list[str]:
    ids = [i.strip().upper() for i in ids if i.strip()]
    if not ids:
        raise SieError("Debes indicar al menos 1 serie.")
    if len(ids) > MAX_SERIES:
        raise SieError(f"Solo se pueden consultar maximo {MAX_SERIES} series por llamada (HTTP 413).")
    for i in ids:
        if not ID_RE.match(i):
            raise SieError(f"ID de serie invalido '{i}'. Formato esperado SX#### (ej. SF61745).")
    # dedup preservando orden
    return list(dict.fromkeys(ids))


def validate_rango(ini: str, fin: str) -> tuple[str, str]:
    if not DATE_RE.match(ini) or not DATE_RE.match(fin):
        raise SieError("Formato de fecha incorrecto. Debe ser yyyy-MM-dd.")
    d_ini = date.fromisoformat(ini)
    d_fin = date.fromisoformat(fin)
    if d_ini > d_fin:
        raise SieError("fecha_ini posterior a fecha_fin: el API devuelve serie sin datos. Corrige el orden.")
    if (d_fin - d_ini).days > MAX_RANGO_DIAS:
        raise SieError(f"Rango maximo {MAX_RANGO_DIAS} dias (historico full prohibido: 6747 pts / 258KB medidos).")
    return ini, fin


def parse_fecha_es(s: str) -> date:
    """Response es dd/MM/yyyy con locale=es."""
    return datetime.strptime(s, "%d/%m/%Y").date()


def _cache_get(key: str):
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    _cache.pop(key, None)
    return None


def _cache_set(key: str, value: object, ttl: float):
    _cache[key] = (time.time() + ttl, value)


def _map_error(status: int, payload: dict) -> SieError:
    err = (payload.get("error") or {}) if isinstance(payload, dict) else {}
    msg = str(err.get("mensaje", ""))
    det = str(err.get("detalle", ""))
    if "Token inv" in msg:
        return SieError("Token invalido o ausente. Verifica BANXICO_TOKEN (64 chars).")
    if "mites de consultas" in msg or "mite de consultas" in msg:
        secs = err.get("secondsToReset", "?")
        return SieError(f"Limite de consultas superado. Reintenta en {secs}s. Empaqueta IDs y cachea.")
    if "Demasiadas series" in msg:
        return SieError("Demasiadas series: maximo 20 por llamada.")
    if "fecha" in msg.lower():
        return SieError(f"{msg} {det}".strip())
    if "series" in msg.lower():
        return SieError(f"{msg} {det}".strip())
    return SieError(f"Banxico HTTP {status}: {msg} {det}".strip())


class BanxicoClient:
    def __init__(self, token: str | None = None, timeout: float = 25.0):
        self.token = token or config.get_token()
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Bmx-Token": self.token,
            "User-Agent": "mcp-banxico-sie/0.1",
        }

    async def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{config.BASE_URL}{path}"
        q = {"locale": "es", **(params or {})}  # forzar es: en cambia fechas a MM/DD
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(url, headers=self._headers(), params=q)
        ctype = r.headers.get("Content-Type", "")
        payload: dict = {}
        if "json" in ctype or r.text.strip().startswith("{"):
            try:
                payload = r.json()
            except ValueError:
                payload = {}
        if r.status_code in (400, 401, 403, 413):
            raise _map_error(r.status_code, payload)
        r.raise_for_status()
        return payload

    async def metadata(self, ids: list[str]) -> list[dict]:
        ids = validate_ids(ids)
        key = "meta:" + ",".join(ids)
        hit = _cache_get(key)
        if hit is not None:
            return hit  # type: ignore[return-value]
        payload = await self._get(f"/series/{','.join(ids)}")
        series = payload.get("bmx", {}).get("series", [])
        _cache_set(key, series, _METADATA_TTL)
        return series

    async def oportuno(self, ids: list[str]) -> list[dict]:
        ids = validate_ids(ids)
        key = "opo:" + ",".join(ids)
        hit = _cache_get(key)
        if hit is not None:
            return hit  # type: ignore[return-value]
        payload = await self._get(f"/series/{','.join(ids)}/datos/oportuno")
        series = payload.get("bmx", {}).get("series", [])
        _cache_set(key, series, _OPORTUNO_TTL)
        return series

    async def rango(self, ids: list[str], ini: str, fin: str) -> list[dict]:
        ids = validate_ids(ids)
        ini, fin = validate_rango(ini, fin)
        payload = await self._get(f"/series/{','.join(ids)}/datos/{ini}/{fin}")
        # fecha invertida u huecos => serie sin `datos`; se devuelve tal cual para que la tool lo reporte
        return payload.get("bmx", {}).get("series", [])

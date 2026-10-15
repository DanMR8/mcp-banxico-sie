"""Edge cases: errores tipicos sin quemar cuota. Solo stdlib."""
import json, os, sys, time, urllib.request, urllib.error, gzip
from datetime import datetime, timezone

BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1"
out = {"started_at": datetime.now(timezone.utc).isoformat(), "tests": []}

def get(url, token, headers_extra=None):
    h = {"Accept": "application/json", "Bmx-Token": token,
         "Accept-Encoding": "gzip", "User-Agent": "mcp-banxico-sie-edge/0.1"}
    if headers_extra:
        h.update(headers_extra)
    req = urllib.request.Request(url, headers=h)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read()
            if body[:2] == b"\x1f\x8b":
                try: body = gzip.decompress(body)
                except Exception: pass
            ms = round((time.perf_counter()-t0)*1000,1)
            return r.status, dict(r.headers), body, ms, None
    except urllib.error.HTTPError as e:
        try:
            b = e.read()
            if b[:2] == b"\x1f\x8b":
                try: b = gzip.decompress(b)
                except Exception: pass
        except Exception: b = b""
        ms = round((time.perf_counter()-t0)*1000,1)
        return e.code, dict(e.headers or {}), b, ms, f"HTTP {e.code}"
    except Exception as e:
        ms = round((time.perf_counter()-t0)*1000,1)
        return None, {}, b"", ms, f"{type(e).__name__}: {e}"

def rec(name, st, hdrs, body, ms, err):
    # Decodifica con fallback latin-1 para evitar mojibake
    txt = None
    for enc in ("utf-8", "latin-1"):
        try:
            txt = body.decode(enc); break
        except Exception: continue
    if txt is None: txt = repr(body[:300])
    rl = {k: v for k, v in hdrs.items() if "bmx" in k.lower() or "reset" in k.lower() or "limit" in k.lower()}
    try:
        j = json.loads(txt)
        msg = str(j.get("error", {}).get("mensaje") or list(j.keys()))
    except Exception:
        msg = txt[:200]
    out["tests"].append({"name": name, "status": st, "ms": ms, "err": err,
                         "mensaje": msg[:300], "rate_headers": rl, "preview": txt[:600]})
    print(f"[{'OK' if st else 'ERR'}] {name} status={st} ms={ms} mensaje={msg[:160]} rl={rl}")

def main():
    token = os.environ.get("BANXICO_TOKEN","").strip()
    if len(token) != 64:
        print("Falta BANXICO_TOKEN"); return 2
    ids21 = "SF61745,SF60648,SF60649,SF60633,SP68257,SF43718,SF60653,SF46410,SF46406,SF46407,SF60632,SF43707,SP74665,SF43783,SF62628,SF43878,SP30577,SR16734,SR16796,SR16828,SR16850"
    probes = [
        ("mas_de_20_series", f"{BASE}/series/{ids21}/datos/oportuno", None),
        ("fecha_invertida", f"{BASE}/series/SF43718/datos/2024-02-01/2024-01-01", None),
        ("fecha_formato_malo", f"{BASE}/series/SF43718/datos/15-01-2024/31-01-2024", None),
        ("id_inexistente", f"{BASE}/series/XXXX9999/datos/oportuno", None),
        ("locale_en", f"{BASE}/series/SF61745?locale=en", None),
        ("mediatype_xml", f"{BASE}/series/SF61745/datos/oportuno?mediaType=xml", None),
        ("oportuno_ok_headers", f"{BASE}/series/SF61745/datos/oportuno", None),
    ]
    for name, url, hx in probes:
        st, hdrs, body, ms, err = get(url, token, hx)
        rec(name, st, hdrs, body, ms, err)
    out["finished_at"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.join("characterization","results"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = os.path.join("characterization","results",f"edge_{ts}.json")
    json.dump(out, open(jp,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nReporte: {jp}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

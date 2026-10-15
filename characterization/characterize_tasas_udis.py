"""
Fase 2 (requiere BANXICO_TOKEN): caracterizacion enfocada B) Tasas + C) UDIS.
Mide: metadatos (periodicidad/unidad), oportuno, rango 30d/1a, peso historico,
parametros incremento/decimales/locale, y errores tipicos.

Uso:
  set BANXICO_TOKEN=<64chars>  (Windows) / export BANXICO_TOKEN=... (bash)
  python scripts/characterize_tasas_udis.py

Salida: characterization/results/tasas_udis_<timestamp>.json/.md
Solo stdlib. Cuota estimada: ~10 llamadas (muy por debajo de 80/min y 200/5min).
"""
import json, os, sys, time, urllib.request, urllib.error, gzip
from datetime import datetime, timezone, date, timedelta

BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1"
# Tema B + C
SERIES = {
    "SF61745": "B tasa objetivo",
    "SF60648": "B TIIE 28d (doc)",
    "SF43783": "B TIIE 28d (ejemplo real del doc, validar cual existe)",
    "SF60649": "B TIIE 91d",
    "SF60633": "B Cetes 28d",
    "SP68257": "C UDIS",
    "SF43707": "testigo reservas (para comparar periodicidad)",
}
out = {"started_at": datetime.now(timezone.utc).isoformat(), "tests": []}

def get(url, token, timeout=25):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "Bmx-Token": token,
        "Accept-Encoding": "gzip", "User-Agent": "mcp-banxico-sie-char2/0.1"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            if body[:2] == b"\x1f\x8b":
                try: body = gzip.decompress(body)
                except Exception: pass
            return r.status, body, round((time.perf_counter()-t0)*1000,1), None
    except urllib.error.HTTPError as e:
        try:
            b = e.read()
            if b[:2] == b"\x1f\x8b":
                try: b = gzip.decompress(b)
                except Exception: pass
        except Exception: b = b""
        return e.code, b, round((time.perf_counter()-t0)*1000,1), f"HTTP {e.code}"
    except Exception as e:
        return None, b"", round((time.perf_counter()-t0)*1000,1), f"{type(e).__name__}: {e}"

def rec(name, ok, detail, extra=None):
    out["tests"].append({"name": name, "ok": ok, "detail": detail, **(extra or {})})
    print(f"[{'OK ' if ok else 'FAIL'}] {name} :: {str(detail)[:250]}")

def main():
    token = os.environ.get("BANXICO_TOKEN","").strip()
    if len(token) != 64:
        print("Falta BANXICO_TOKEN de 64 chars. Consiguelo en https://www.banxico.org.mx/SieAPIRest/service/v1/token (captcha, 'Generar token').")
        print("Luego:  set BANXICO_TOKEN=...  y re-ejecuta.")
        return 2
    hoy = date.today()
    ini30 = (hoy - timedelta(days=30)).isoformat()
    ini365 = (hoy - timedelta(days=365)).isoformat()
    fin = hoy.isoformat()

    # 1. Metadatos en bloque (1 llamada): revela periodicidad, unidad, fechas disponible
    st, body, ms, err = get(f"{BASE}/series/{','.join(['SF61745','SF60648','SF43783','SF60649','SF60633','SP68257']) }", token)
    try:
        j = json.loads(body.decode("utf-8","replace"))
        series = j.get("bmx",{}).get("series",[])
        desc = []
        for s in series:
            desc.append({k: s.get(k) for k in ("idSerie","titulo","periodicidad","unidad","fechaInicio","fechaFin") if k in s})
        rec("metadata_bloque_BC", st==200, f"status={st} ms={ms} series={len(series)}", {"meta": desc, "raw_preview": body[:600].decode("utf-8","replace")})
    except Exception as e:
        rec("metadata_bloque_BC", False, f"status={st} err={err or e} preview={body[:300]}")

    # 2. Oportuno conjunto tasas+udis (1 llamada): el caso de uso "dame todo hoy"
    st, body, ms, err = get(f"{BASE}/series/SF61745,SF60648,SF60633,SP68257/datos/oportuno", token)
    try:
        j = json.loads(body.decode("utf-8","replace"))
        res = [(s.get("idSerie"), (s.get("datos") or [{}])[0]) for s in j.get("bmx",{}).get("series",[])]
        rec("oportuno_pack", st==200, f"status={st} ms={ms} datos={res}", {"preview": body[:800].decode("utf-8","replace")})
    except Exception as e:
        rec("oportuno_pack", False, f"status={st} {err or e}")

    # 3. Rangos 30d por serie (mide huecos finde/dias inhabiles + N observaciones)
    for sid in ["SF61745","SF60648","SF60633","SP68257"]:
        st, body, ms, err = get(f"{BASE}/series/{sid}/datos/{ini30}/{fin}", token)
        try:
            j = json.loads(body.decode("utf-8","replace"))
            d = (j.get("bmx",{}).get("series",[{}])[0].get("datos") or [])
            rec(f"rango30d_{sid}", st==200, f"n={len(d)} ms={ms} primero={d[0] if d else None} ultimo={d[-1] if d else None} size_kb={round(len(body)/1024,1)}",
                {"n": len(d), "ejemplo": d[:2]})
        except Exception as e:
            rec(f"rango30d_{sid}", False, f"status={st} {err or e} preview={body[:300]}")

    # 4. Rango 1 anio solo UDIS vs solo Tasa objetivo (compara densidad diaria vs eventual)
    for sid in ["SP68257","SF61745"]:
        st, body, ms, err = get(f"{BASE}/series/{sid}/datos/{ini365}/{fin}", token)
        try:
            j = json.loads(body.decode("utf-8","replace"))
            d = (j.get("bmx",{}).get("series",[{}])[0].get("datos") or [])
            rec(f"rango1a_{sid}", st==200, f"n={len(d)} ms={ms} size_kb={round(len(body)/1024,1)}",
                {"n": len(d)})
        except Exception as e:
            rec(f"rango1a_{sid}", False, f"status={st} {err or e}")

    # 5. Parametros de transformacion (incremento/decimal) sobre 1 rango chico
    st, body, ms, err = get(f"{BASE}/series/SF60648/datos/{ini30}/{fin}?incremento=PorcObsAnt", token)
    rec("incremento_PorcObsAnt", st==200, f"status={st} ms={ms} preview={body[:400].decode('utf-8','replace')}")
    st, body, ms, err = get(f"{BASE}/series/SP68257/datos/{ini30}/{fin}?decimales=sinCeros", token)
    rec("decimales_sinCeros", st==200, f"status={st} ms={ms} preview={body[:400].decode('utf-8','replace')}")

    # 6. Historico completo SOLO tasa objetivo (para dimensionar; NO hacerlo con todas)
    st, body, ms, err = get(f"{BASE}/series/SF61745/datos", token)
    try:
        j = json.loads(body.decode("utf-8","replace"))
        d = (j.get("bmx",{}).get("series",[{}])[0].get("datos") or [])
        rec("historico_SF61745", st==200, f"n={len(d)} size_kb={round(len(body)/1024,1)} ms={ms} (define si el MCP debe prohibir historico full)",
            {"n": len(d), "size_kb": round(len(body)/1024,1)})
    except Exception as e:
        rec("historico_SF61745", False, f"status={st} {err or e}")

    out["finished_at"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.join("characterization","results"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = os.path.join("characterization","results",f"tasas_udis_{ts}.json")
    json.dump(out, open(jp,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    md = [f"# Fase 2 Tasas+UDIS — {ts}", ""]
    for t in out["tests"]:
        md.append(f"- [{'x' if t['ok'] else ' '}] **{t['name']}**: {t['detail']}")
    mp = jp.replace(".json",".md")
    open(mp,"w",encoding="utf-8").write("\n".join(md))
    print(f"\nReporte: {jp}\n         {mp}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

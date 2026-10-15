"""
Caracterizacion SIE-API Banxico (fase 1: sin token + estructura).
Solo stdlib. No quema cuota. Genera reporte JSON + MD.

Uso:
  python scripts/characterize_sie.py
  BANXICO_TOKEN=<64chars> python scripts/characterize_sie.py  (fase 2 con token)

Salidas:
  characterization/results/characterization_<timestamp>.json
  characterization/results/characterization_<timestamp>.md
"""
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1"
POPULAR = {
    "SF43707": "Reservas Internacionales",
    "SF61745": "Tasa objetivo",
    "SF60648": "TIIE 28d (doc, puede ser SF43783 en ejemplo)",
    "SF60649": "TIIE 91d",
    "SF60633": "Cetes 28d",
    "SF43718": "FIX",
    "SF60653": "Liquidacion",
    "SF46410": "Euro",
    "SF46406": "Yen",
    "SF46407": "Libra",
    "SF60632": "CAD",
    "SP68257": "UDIS",
}

results = {"started_at": datetime.now(timezone.utc).isoformat(), "tests": []}


def record(name, ok, detail=None, latency_ms=None, extra=None):
    entry = {"name": name, "ok": ok, "detail": detail, "latency_ms": latency_ms}
    if extra:
        entry.update(extra)
    results["tests"].append(entry)
    status = "OK " if ok else "FAIL"
    print(f"[{status}] {name} ({latency_ms}ms) :: {str(detail)[:220]}")


def http_get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {"Accept": "application/json", "Accept-Encoding": "gzip", "User-Agent": "mcp-banxico-sie-characterization/0.1"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            # Try gzip decode if needed
            ctype = resp.headers.get("Content-Type", "")
            cenc = resp.headers.get("Content-Encoding", "")
            if cenc == "gzip":
                import gzip
                try:
                    body = gzip.decompress(body)
                except Exception:
                    pass
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return resp.status, dict(resp.headers), body[:20000], ms, None
    except urllib.error.HTTPError as e:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        try:
            b = e.read()[:20000]
            # Descomprime gzip también en errores (Banxico lo envía siempre)
            import gzip
            try:
                # e.headers puede ser None en algunos casos
                cenc = (e.headers.get("Content-Encoding", "") if e.headers else "")
                if b[:2] == b"\x1f\x8b" or cenc == "gzip":
                    b = gzip.decompress(b)
            except Exception:
                pass
        except Exception:
            b = b""
        return e.code, dict(e.headers or {}), b, ms, f"HTTPError {e.code}"
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return None, {}, b"", ms, f"{type(e).__name__}: {e}"


def check_tls():
    try:
        ctx = ssl.create_default_context()
        # Banxico exige TLS 1.3 desde 2023. Verificamos que el handshake negocie >=1.2 y reporte version.
        import socket
        host = "www.banxico.org.mx"
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                ver = ssock.version()
                record("tls_handshake", ver in ("TLSv1.2", "TLSv1.3"), f"negotiated={ver}")
                return ver
    except Exception as e:
        record("tls_handshake", False, f"{type(e).__name__}: {e}")
        return None


def main():
    token = os.environ.get("BANXICO_TOKEN", "").strip()
    has_token = len(token) == 64
    results["has_token"] = has_token
    results["base"] = BASE

    print(f"BASE={BASE} has_token={has_token} (len={len(token)})")
    check_tls()

    # 1. Sin token: debe fallar con 401/403 o mensaje de token requerido. Caracteriza error.
    for label, url in [
        ("sin_token_metadata", f"{BASE}/series/SF43718"),
        ("sin_token_oportuno", f"{BASE}/series/SF43718/datos/oportuno"),
        ("sin_token_rango", f"{BASE}/series/SF43718/datos/2024-01-01/2024-01-31"),
    ]:
        st, hdrs, body, ms, err = http_get(url)
        try:
            j = json.loads(body.decode("utf-8", "replace")[:5000])
        except Exception:
            j = {"raw": body[:500].decode("utf-8", "replace")}
        record(label, True, f"status={st} err={err} body_keys={list(j.keys())[:5]}", ms,
               extra={"status": st, "body_preview": str(j)[:800]})

    # 2. Token invalido: caracteriza mensaje de token invalido vs sin token
    bad = "0" * 64
    st, hdrs, body, ms, err = http_get(
        f"{BASE}/series/SF43718/datos/oportuno",
        headers={"Accept": "application/json", "Bmx-Token": bad, "User-Agent": "mcp-banxico-sie-characterization/0.1"},
    )
    try:
        j = json.loads(body.decode("utf-8", "replace")[:5000])
    except Exception:
        j = {"raw": body[:500].decode("utf-8", "replace")}
    record("token_invalido", True, f"status={st} body={str(j)[:300]}", ms,
           extra={"status": st, "body_preview": str(j)[:800]})

    # 3. Formatos e idioma sin gastar mucho: solo si hay token, si no se documenta como pendiente
    if not has_token:
        record("con_token_metadata_FIX", False, "PENDIENTE: define BANXICO_TOKEN de 64 chars para fase 2")
        record("con_token_oportuno_multi", False, "PENDIENTE fase 2")
        record("con_token_rango", False, "PENDIENTE fase 2")
        record("con_token_historico_pesado", False, "PENDIENTE fase 2 (solo 1 serie, mide N observaciones)")
        record("con_token_errores", False, "PENDIENTE fase 2: id inexistente, fecha invertida, >20 series")
    else:
        H = {"Accept": "application/json", "Bmx-Token": token, "User-Agent": "mcp-banxico-sie-characterization/0.1"}
        probes = [
            ("con_token_metadata_FIX", f"{BASE}/series/SF43718"),
            ("con_token_oportuno_multi", f"{BASE}/series/SF43718,SF61745,SP68257/datos/oportuno"),
            ("con_token_rango", f"{BASE}/series/SF43718/datos/2024-01-01/2024-01-31"),
            ("con_token_locale_en", f"{BASE}/series/SF43718?locale=en"),
            ("con_token_incremento", f"{BASE}/series/SF43718/datos/2024-01-01/2024-03-01?incremento=PorcObsAnt"),
            ("con_token_id_inexistente", f"{BASE}/series/XXXX9999/datos/oportuno"),
            ("con_token_fecha_invertida", f"{BASE}/series/SF43718/datos/2024-02-01/2024-01-01"),
        ]
        for label, url in probes:
            st, hdrs, body, ms, err = http_get(url, headers=H)
            preview = body[:1500].decode("utf-8", "replace")
            # Intenta medir estructura
            struct = {}
            try:
                j = json.loads(body.decode("utf-8", "replace"))
                bmx = j.get("bmx", {})
                series = bmx.get("series", [])
                struct = {"top_keys": list(j.keys()), "n_series": len(series)}
                if series:
                    s0 = series[0]
                    struct["s0_keys"] = list(s0.keys())
                    datos = s0.get("datos", [])
                    struct["n_datos_s0"] = len(datos)
                    if datos:
                        struct["ejemplo_dato"] = datos[0]
                    if "error" in s0 or "error" in j:
                        struct["error"] = str(s0.get("error") or j.get("error"))[:300]
            except Exception as e:
                struct = {"parse": f"no-json: {e}", "preview": preview[:400]}
            # Headers de rate limit
            rl = {k: v for k, v in hdrs.items() if "bmx" in k.lower() or "reset" in k.lower() or "limit" in k.lower()}
            record(label, st == 200 or "error" in str(struct).lower(), f"status={st} struct={struct} rl={rl}", ms,
                   extra={"status": st, "struct": struct, "rate_headers": rl, "body_preview": preview[:800]})

        # Historico completo: SOLO 1 serie liviana para medir orden de magnitud (puede ser grande)
        st, hdrs, body, ms, err = http_get(f"{BASE}/series/SF61745/datos", headers=H)
        try:
            j = json.loads(body.decode("utf-8", "replace"))
            n = len(j.get("bmx", {}).get("series", [{}])[0].get("datos", []))
            size_kb = round(len(body) / 1024, 1)
            record("con_token_historico_pesado", st == 200, f"status={st} n_datos={n} size_kb={size_kb} ms={ms}", ms,
                   extra={"status": st, "n_datos": n, "size_kb": size_kb})
        except Exception as e:
            record("con_token_historico_pesado", False, f"status={st} parse_fail={e}", ms)

    # 4. Guarda reporte
    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    results["popular_map"] = POPULAR
    outdir = os.path.join("characterization", "results")
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = os.path.join(outdir, f"characterization_{ts}.json")
    mdp = os.path.join(outdir, f"characterization_{ts}.md")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    # MD resumen
    lines = [f"# Caracterizacion SIE-API — {ts}", "", f"has_token={has_token}", ""]
    for t in results["tests"]:
        lines.append(f"- [{'x' if t['ok'] else ' '}] **{t['name']}** ({t.get('latency_ms')}ms): {t.get('detail')}")
    lines += ["", "## Mapa popular", ""]
    for k, v in POPULAR.items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Siguiente paso", "Si has_token=false: consigue token en https://www.banxico.org.mx/SieAPIRest/service/v1/token (captcha) y re-ejecuta con BANXICO_TOKEN.",
              "Fase 2 medira tamanos, periodicidades, huecos (fines de semana), e incrementos."]
    with open(mdp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReporte: {jp}\n         {mdp}")


if __name__ == "__main__":
    sys.exit(main())

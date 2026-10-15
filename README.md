# mcp-banxico-sie — SIE-API de Banxico como herramientas MCP

![Python](https://img.shields.io/badge/python-3.11-blue)
![MCP](https://img.shields.io/badge/MCP-stdio%20%2B%20streamable--http-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
[![CI](https://github.com/DanMR8/mcp-banxico-sie/actions/workflows/ci.yml/badge.svg)](https://github.com/DanMR8/mcp-banxico-sie/actions)

**[English version →](README.en.md)**

**Dale a tu asistente IA acceso en vivo a las tasas y UDIS oficiales de Banxico.**
Servidor MCP en Python para la [SIE-API de Banxico](https://www.banxico.org.mx/SieAPIRest/service/v1/):
tasa objetivo, TIIE, Cetes 28, UDIS y conversión a pesos — con manejo de cuotas,
caché y errores accionables.

```powershell
# Claude Desktop, MCP Inspector o cualquier cliente MCP
$env:BANXICO_TOKEN="tu-token-64"   # https://www.banxico.org.mx/SieAPIRest/service/v1/token
python -m mcp_banxico_sie.server   # stdio local: 5 tools, cero configuración extra
```

## Qué puedes preguntar

- *"¿Cuál es la tasa objetivo y la TIIE 28 hoy?"* → `get_tasa_hoy` (4 series en 1 llamada)
- *"Spread TIIE–Cetes del último trimestre"* → `get_tasas_rango` (con último cambio de tasa objetivo)
- *"¿Cuánto son 10,000 UDIS en pesos al 1 de octubre?"* → `convertir_udis_a_pesos`
- *"Inflación acumulada del último mes según UDIS"* → `get_inflacion_udis`

## Las 5 tools (solo lectura)

| Tool | Qué hace |
|---|---|
| `get_tasa_hoy` | Tasa objetivo (SF61745) + TIIE 28/91 (SF60648/SF60649) + Cetes 28 (SF60633) en 1 llamada |
| `get_tasas_rango` | Rango ≤365 días + spread TIIE28−Cetes28 y último cambio de tasa objetivo |
| `get_udis_hoy` | UDIS oportuna SP68257 (la fecha futura es publicación adelantada oficial) |
| `convertir_udis_a_pesos` | Monto UDIS → pesos a fecha exacta `yyyy-MM-dd` |
| `get_inflacion_udis` | Variación % UDIS del periodo como proxy de inflación |

## Por qué este MCP

| Diferenciador | Detalle |
|---|---|
| Orientado a tarea, no wrappers 1:1 | Cada tool resuelve una pregunta real (pack oportuno, spread, proxy de inflación) |
| Diseñado desde evidencia | 3 scripts de caracterización + hallazgos JSON dictaron cada guard del cliente |
| Quota-aware | Pack ≤20 IDs, caché (oportuno 12 h, metadata 7 d), contador client-side, tope 365 días |
| Rarezas del API ya manejadas | Cetes semanal con lag de 2–5 días, UDIS publicada a futuro, fecha invertida → "sin datos" |
| Transporte dual | stdio local (Claude Desktop, Inspector) + Streamable HTTP remoto (Docker) |

## Instalación (`.venv` + `pip`, sin `uv`)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Token (64 caracteres, gratis con captcha; se genera una vez y se reusa):
https://www.banxico.org.mx/SieAPIRest/service/v1/token → `$env:BANXICO_TOKEN`
(jamás en código; ver `.env.example`).
Cuotas: oportuna 80/min–40k/día, histórica 200/5min–10k/día. La implementación
ya considera los [límites oficiales de consulta](https://www.banxico.org.mx/SieAPIRest/service/v1/doc/limiteConsultas):
pack ≤20 IDs, caché y tope de rango de 365 días.

## Uso

```powershell
.\.venv\Scripts\Activate.ps1
$env:BANXICO_TOKEN="tu-token-64"
python -m mcp_banxico_sie.server                 # stdio (Claude Desktop, Inspector)
$env:MCP_TRANSPORT="http"; $env:PORT="8000"; python -m mcp_banxico_sie.server  # remoto Streamable HTTP
```

**Claude Desktop / Inspector (local):** usa `mcp.json` como referencia — apunta al
Python del `.venv`; solo reemplaza el token.
**Remoto (Docker):** `docker build -t mcp-banxico-sie .`, sirve con `MCP_TRANSPORT=http`.

## Calidad

- Tests con datos reales del API (mocks, sin gastar cuota): `python -m pytest tests/ -q`
- Lint: `ruff check src/ tests/` · CI en cada push (`/.github/workflows/ci.yml`)
- Estructura: `src/mcp_banxico_sie/{config,client,tools,server}.py`, evidencia en `characterization/`

## Fuente de datos

Datos: Banco de México, [SIE-API](https://www.banxico.org.mx/SieAPIRest/service/v1/),
reproducidos conforme a su [salvedad de uso](https://www.banxico.org.mx/footer-es/salvedad-politicas-uso-banco-.html)
(con atribución en cada respuesta). Proyecto independiente, no afiliado ni respaldado por Banxico.

## Licencia

MIT — ver `LICENSE`.

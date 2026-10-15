# mcp-banxico-sie — Banxico SIE-API as MCP Tools

![Python](https://img.shields.io/badge/python-3.11-blue)
![MCP](https://img.shields.io/badge/MCP-stdio%20%2B%20streamable--http-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**[Versión en español →](README.md)**

**Give your AI assistant live access to Banxico's official rates and UDI values.**
Python MCP server for [Banxico's SIE-API](https://www.banxico.org.mx/SieAPIRest/service/v1/):
policy rate, TIIE, 28-day Cetes, UDIS and MXN conversion — with quota handling,
caching and actionable errors.

```powershell
# Claude Desktop, MCP Inspector, or any MCP client
$env:BANXICO_TOKEN="your-64-char-token"   # https://www.banxico.org.mx/SieAPIRest/service/v1/token
python -m mcp_banxico_sie.server          # local stdio: 5 tools, zero extra setup
```

## What you can ask

- *"What are today's policy rate and 28-day TIIE?"* → `get_tasa_hoy` (4 series in 1 call)
- *"TIIE–Cetes spread for the last quarter"* → `get_tasas_rango` (with last policy-rate change)
- *"How much are 10,000 UDIS in pesos on October 1st?"* → `convertir_udis_a_pesos`
- *"Accumulated inflation last month per UDIS"* → `get_inflacion_udis`

## The 5 tools (read-only)

| Tool | What it does |
|---|---|
| `get_tasa_hoy` | Policy rate (SF61745) + TIIE 28/91 (SF60648/SF60649) + 28-day Cetes (SF60633) in 1 call |
| `get_tasas_rango` | Range up to 365 days + TIIE28−Cetes28 spread and last policy-rate change |
| `get_udis_hoy` | Latest UDIS value SP68257 (a future date is official advance publication) |
| `convertir_udis_a_pesos` | UDIS amount → MXN on exact date `yyyy-MM-dd` |
| `get_inflacion_udis` | UDIS % change over the period as an inflation proxy |

## Why this MCP

| Differentiator | Detail |
|---|---|
| Task-oriented, not 1:1 wrappers | Each tool answers a real question (timely pack, spread, inflation proxy) |
| Evidence-driven design | 3 characterization scripts + JSON findings shaped every client guard |
| Quota-aware | Pack of ≤20 IDs, caching (timely 12 h, metadata 7 d), client-side counter, 365-day cap |
| API quirks already handled | Weekly Cetes with 2–5 day lag, future-dated UDIS, inverted range → "no data" |
| Dual transport | Local stdio (Claude Desktop, Inspector) + remote Streamable HTTP (Docker) |

## Setup (`.venv` + `pip`, no `uv`)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Token (64 chars, free with captcha; generated once and reused):
https://www.banxico.org.mx/SieAPIRest/service/v1/token → `$env:BANXICO_TOKEN`
(never in code; see `.env.example`).
Quotas: timely 80/min–40k/day, historic 200/5min–10k/day. The implementation
follows the [official query limits](https://www.banxico.org.mx/SieAPIRest/service/v1/doc/limiteConsultas):
≤20 IDs per pack, caching, and a 365-day range cap.

## Usage

```powershell
.\.venv\Scripts\Activate.ps1
$env:BANXICO_TOKEN="your-64-char-token"
python -m mcp_banxico_sie.server                 # stdio (Claude Desktop, Inspector)
$env:MCP_TRANSPORT="http"; $env:PORT="8000"; python -m mcp_banxico_sie.server  # remote Streamable HTTP
```

**Claude Desktop / Inspector (local):** use `mcp.json` as reference — it points to
the `.venv` Python; just replace the token.
**Remote (Docker):** `docker build -t mcp-banxico-sie .`, serve with `MCP_TRANSPORT=http`.

## Quality

- Tests with real API data (mocks, no quota spent): `python -m pytest tests/ -q`
- Lint: `ruff check src/ tests/` · CI on every push (`/.github/workflows/ci.yml`)
- Layout: `src/mcp_banxico_sie/{config,client,tools,server}.py`, evidence in `characterization/`

## Data source

Data: Banco de México, [SIE-API](https://www.banxico.org.mx/SieAPIRest/service/v1/),
reproduced under its [use disclaimer](https://www.banxico.org.mx/footer-es/salvedad-politicas-uso-banco-.html)
(with attribution in every response). Independent project, not affiliated with
or endorsed by Banxico.

## License

MIT — see `LICENSE`.

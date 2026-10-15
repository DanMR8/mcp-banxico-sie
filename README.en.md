# mcp-banxico-sie

Python MCP (Model Context Protocol) server for querying key macroeconomic indicators from Banco de México ([SIE-API](https://www.banxico.org.mx/SieAPIRest/service/v1/)): policy rate, TIIE, 28-day Cetes, UDIS and inflation-variation estimates.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-stdio%20%7C%20Streamable--HTTP-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
[![CI](https://github.com/DanMR8/mcp-banxico-sie/actions/workflows/ci.yml/badge.svg)](https://github.com/DanMR8/mcp-banxico-sie/actions)

**[Versión en español →](README.md)**

---

## Highlights

- **Use-case-oriented tools:** No 1:1 endpoint exposure. It groups queries to answer real financial questions (e.g. TIIE–Cetes spread or direct UDI/MXN conversions).
- **Strict quota control (quota-aware):** Per-call series packing against the SIE ($\le$ 20 series per request), in-memory cache (12 h for timely series, 7 d for metadata) and time-range caps ($\le$ 365 days).
- **Banxico edge-case handling:** Tolerates the weekly Cetes auction lag (2–5 days) and reports the advance UDIS publication with a clarifying note instead of failing.
- **Dual transport:** Native `stdio` support (local clients from any vendor) and `streamable-http` (remote container deployments).

---

## MCP client setup

Works with any MCP client (Claude Desktop, Cursor, Codex, OpenCode, MCP Inspector, ...).
Add the server to your client's `mcpServers` configuration:

### Via local virtual environment

```json
{
  "mcpServers": {
    "banxico-sie": {
      "command": "C:\\path\\to\\project\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_banxico_sie.server"],
      "env": {
        "BANXICO_TOKEN": "your_64_char_token"
      }
    }
  }
}
```

*(On macOS/Linux, replace the executable path with `/path/to/project/.venv/bin/python`)*.

> **SIE token:** You can get one free and instantly from the [Banxico developer portal](https://www.banxico.org.mx/SieAPIRest/service/v1/token).

---

## Available tools

| Tool | Parameters | Description / Series queried |
| --- | --- | --- |
| `get_tasa_hoy` | *None* | Timely single-batch query: Target Rate (`SF61745`), 28-day TIIE (`SF60648`), 91-day TIIE (`SF60649`) and 28-day Cetes (`SF60633`). |
| `get_tasas_rango` | `fecha_ini`, `fecha_fin` | Historical range ($\le$ 365 days). Summarizes each series (min/max/change) and computes the 28-day TIIE vs. Cetes spread. |
| `get_udis_hoy` | *None* | Current UDI value (`SP68257`), handling Banxico's official advance publication. |
| `convertir_udis_a_pesos` | `monto_udis`, `fecha` (`YYYY-MM-DD`) | Converts a UDIS amount to national currency at the official value on the given date. |
| `get_inflacion_udis` | `fecha_ini`, `fecha_fin` | Computes the UDI percentage change over the period as an inflation estimate. |

---

## Local install and run

### Prerequisites

* Python 3.11 or higher.
* An active Banxico API token.

### 1. Clone and prepare the environment

```bash
git clone https://github.com/DanMR8/mcp-banxico-sie.git
cd mcp-banxico-sie

# Create virtual environment
python -m venv .venv

# Activate on Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Or on Linux/macOS:
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### 2. Set environment variables

Copy the template and add your token:

```bash
cp .env.example .env
```

Or export it in your terminal:

```bash
# PowerShell
$env:BANXICO_TOKEN="your_token_here"

# Bash/Zsh
export BANXICO_TOKEN="your_token_here"
```

### 3. Run the server

**stdio mode (local MCP-capable clients):**

```bash
python -m mcp_banxico_sie.server
```

**Streamable HTTP mode (remote or containers):**

```bash
# PowerShell
$env:MCP_TRANSPORT="http"
$env:PORT="8000"
python -m mcp_banxico_sie.server

# Bash/Zsh
MCP_TRANSPORT=http PORT=8000 python -m mcp_banxico_sie.server
```

---

## Docker run

To run the server as an isolated HTTP service:

```bash
docker build -t mcp-banxico-sie .
docker run -d -p 8000:8000 -e BANXICO_TOKEN="your_token" -e MCP_TRANSPORT="http" mcp-banxico-sie
```

---

## Technical and architecture decisions

1. **Request batching:** Banxico's API accepts up to 20 series identifiers in a single REST call (`/series/{id1},{id2}/datos`). The client uses this to resolve tools like `get_tasa_hoy` in one network transaction.
2. **Async-series resilience:** Cetes rates update weekly by auction while TIIE is daily. The client normalizes and aligns the time series to avoid failures when a series has no record on the exact queried date.
3. **Quota handling:** Local in-memory TTLs mitigate request consumption against the official SIE caps (80 req/min for timely series; 200 req/5 min for historic series). See [official query limits](https://www.banxico.org.mx/SieAPIRest/service/v1/doc/limiteConsultas).
4. **Zero-quota testing:** The test suite uses a fake client with real API values (inline mocks, no network), so full CI runs via `pytest` without spending token quota.

---

## Development and testing

Run the test suite:

```bash
pytest tests/ -v
```

Style check:

```bash
ruff check src/ tests/
```

---

## Legal attribution

Financial data from Banco de México via the Sistema de Información Económica ([SIE-API](https://www.banxico.org.mx/SieAPIRest/service/v1/)). This is an independent open-source implementation with no official affiliation or sponsorship from Banxico. Data is used under Banco de México's terms and [use disclaimer](https://www.banxico.org.mx/footer-es/salvedad-politicas-uso-banco-.html).

## License

Distributed under the MIT license — see `LICENSE`.

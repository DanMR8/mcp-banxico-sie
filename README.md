# mcp-banxico-sie

Servidor MCP (Model Context Protocol) en Python para consultar indicadores macroeconómicos clave del Banco de México ([SIE-API](https://www.banxico.org.mx/SieAPIRest/service/v1/)): tasa objetivo, TIIE, Cetes 28, UDIS y cálculo de variaciones inflacionarias.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-stdio%20%7C%20Streamable--HTTP-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
[![CI](https://github.com/DanMR8/mcp-banxico-sie/actions/workflows/ci.yml/badge.svg)](https://github.com/DanMR8/mcp-banxico-sie/actions)

**[English version →](README.en.md)**

---

## Características principales

- **Herramientas orientadas a casos de uso:** No expone endpoints 1:1. Agrupa consultas para responder preguntas financieras reales (ej. spread TIIE-Cetes o conversiones directas UDI/MXN).
- **Control estricto de cuotas (Quota-aware):** Agrupación de series por llamada al SIE ($\le$ 20 series por petición), caché en memoria (12 h para series oportunas, 7 d para metadatos) y límites de rango temporal ($\le$ 365 días).
- **Manejo de edge cases de Banxico:** Tolera el desfase de las subastas semanales de Cetes (lag de 2 a 5 días) y reporta la publicación adelantada de UDIS con nota aclaratoria en lugar de fallar.
- **Doble transporte:** Soporte nativo para `stdio` (clientes locales de cualquier proveedor) y `streamable-http` (despliegues remotos en contenedor).

---

## Conexión con clientes MCP

Compatible con cualquier cliente MCP (Claude Desktop, Cursor, Codex, OpenCode, MCP Inspector, ...).
Agrega el servidor a la configuración `mcpServers` de tu cliente:

### Vía entorno virtual local

```json
{
  "mcpServers": {
    "banxico-sie": {
      "command": "C:\\ruta\\al\\proyecto\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_banxico_sie.server"],
      "env": {
        "BANXICO_TOKEN": "tu_token_de_64_caracteres"
      }
    }
  }
}
```

*(En macOS/Linux, reemplaza la ruta del ejecutable por `/ruta/al/proyecto/.venv/bin/python`)*.

> **Token del SIE:** Puedes tramitarlo de forma gratuita e instantánea en el [portal de desarrolladores de Banxico](https://www.banxico.org.mx/SieAPIRest/service/v1/token).

---

## Herramientas disponibles (Tools)

| Herramienta | Parámetros | Descripción / Series consultadas |
| --- | --- | --- |
| `get_tasa_hoy` | *Ninguno* | Consulta oportuna en un solo lote: Tasa Objetivo (`SF61745`), TIIE 28 (`SF60648`), TIIE 91 (`SF60649`) y Cetes 28 (`SF60633`). |
| `get_tasas_rango` | `fecha_ini`, `fecha_fin` | Rango histórico ($\le$ 365 días). Resume cada serie (min/max/variación) y calcula el spread TIIE 28 vs. Cetes 28. |
| `get_udis_hoy` | *Ninguno* | Valor vigente de la UDI (`SP68257`), gestionando la publicación oficial anticipada de Banxico. |
| `convertir_udis_a_pesos` | `monto_udis`, `fecha` (`YYYY-MM-DD`) | Convierte un importe en UDIS a moneda nacional según el valor oficial en la fecha indicada. |
| `get_inflacion_udis` | `fecha_ini`, `fecha_fin` | Calcula la variación porcentual de la UDI en el periodo seleccionado como estimación de inflación. |

---

## Instalación y ejecución local

### Requisitos previos

* Python 3.11 o superior.
* Token activo de la API de Banxico.

### 1. Clonar y preparar entorno

```bash
git clone https://github.com/DanMR8/mcp-banxico-sie.git
cd mcp-banxico-sie

# Crear entorno virtual
python -m venv .venv

# Activar en Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# O en Linux/macOS:
source .venv/bin/activate

# Instalar dependencias en modo editable
pip install -e ".[dev]"
```

### 2. Configurar variables de entorno

Copia la plantilla y coloca tu token:

```bash
cp .env.example .env
```

O expórtala en tu terminal:

```bash
# PowerShell
$env:BANXICO_TOKEN="tu_token_aqui"

# Bash/Zsh
export BANXICO_TOKEN="tu_token_aqui"
```

### 3. Ejecutar el servidor

**Modo stdio (clientes locales con soporte MCP):**

```bash
python -m mcp_banxico_sie.server
```

**Modo HTTP Streamable (remoto o contenedores):**

```bash
# PowerShell
$env:MCP_TRANSPORT="http"
$env:PORT="8000"
python -m mcp_banxico_sie.server

# Bash/Zsh
MCP_TRANSPORT=http PORT=8000 python -m mcp_banxico_sie.server
```

---

## Ejecución con Docker

Para correr el servidor como servicio HTTP aislado:

```bash
docker build -t mcp-banxico-sie .
docker run -d -p 8000:8000 -e BANXICO_TOKEN="tu_token" -e MCP_TRANSPORT="http" mcp-banxico-sie
```

---

## Decisiones técnicas y arquitectura

1. **Agrupación de peticiones (Batching):** La API de Banxico permite solicitar hasta 20 identificadores de series en una sola llamada REST (`/series/{id1},{id2}/datos`). El cliente aprovecha esta capacidad para resolver herramientas como `get_tasa_hoy` en una única transacción de red.
2. **Resiliencia ante series asíncronas:** Las tasas de Cetes se actualizan semanalmente mediante subasta, mientras que la TIIE es diaria. El cliente normaliza y alinea las series temporales para evitar fallos cuando una serie no presenta registro en la fecha exacta consultada.
3. **Manejo de cuotas:** Se aplican tiempos de vida (TTL) locales en memoria para mitigar el consumo de peticiones contra los techos oficiales del SIE (80 peticiones/min para series oportunas; 200 peticiones/5 min para series históricas). Ver [límites oficiales de consulta](https://www.banxico.org.mx/SieAPIRest/service/v1/doc/limiteConsultas).
4. **Pruebas sin consumo de cuota:** La suite de pruebas usa un cliente falso con valores reales del API (mocks inline, sin red), permitiendo ejecutar el CI completo vía `pytest` sin agotar el token.

---

## Desarrollo y pruebas

Ejecutar suite de pruebas:

```bash
pytest tests/ -v
```

Revisión de estilo:

```bash
ruff check src/ tests/
```

---

## Atribución legal

Información financiera obtenida del Banco de México a través del Sistema de Información Económica ([SIE-API](https://www.banxico.org.mx/SieAPIRest/service/v1/)). Este proyecto es una implementación independiente de código abierto y no cuenta con afiliación oficial ni patrocinio de Banxico. El uso de los datos se realiza conforme a los términos y [salvedades de uso](https://www.banxico.org.mx/footer-es/salvedad-politicas-uso-banco-.html) del Banco de México.

## Licencia

Distribuido bajo la licencia MIT — ver `LICENSE`.

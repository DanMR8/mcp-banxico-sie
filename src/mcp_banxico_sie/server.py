"""Servidor MCP: stdio local + Streamable HTTP remoto. Logging solo a stderr."""
from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger(__name__)

try:
    from mcp.server import MCPServer  # SDK v2
    _V2 = True
except ImportError:  # fallback SDK v1
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore
    _V2 = False

from . import tools as T
from .client import BanxicoClient

mcp = MCPServer("banxico-sie", version="0.1.0")


def _register():
    # Registro compatible v1/v2: decorador @mcp.tool() con docstring como descripcion
    @mcp.tool()
    async def get_tasa_hoy() -> dict:
        """Tasa de referencia hoy: objetivo + TIIE 28/91 + Cetes 28. / Reference rates today."""
        return await T.get_tasa_hoy(BanxicoClient())

    @mcp.tool()
    async def get_tasas_rango(fecha_ini: str, fecha_fin: str) -> dict:
        """Tasas en rango + spread TIIE-Cetes (max 365d, yyyy-MM-dd). / Rate range with spread."""
        return await T.get_tasas_rango(fecha_ini, fecha_fin, BanxicoClient())

    @mcp.tool()
    async def get_udis_hoy() -> dict:
        """Valor UDIS oportuno (puede ser fecha futura oficial). / Latest UDIS value."""
        return await T.get_udis_hoy(BanxicoClient())

    @mcp.tool()
    async def convertir_udis_a_pesos(monto_udis: float, fecha: str) -> dict:
        """Convierte UDIS a pesos a fecha exacta yyyy-MM-dd. / Convert UDIS to MXN."""
        return await T.convertir_udis_a_pesos(monto_udis, fecha, BanxicoClient())

    @mcp.tool()
    async def get_inflacion_udis(fecha_ini: str, fecha_fin: str) -> dict:
        """Variacion % UDIS en periodo (proxy inflacion). / UDIS inflation proxy."""
        return await T.get_inflacion_udis(fecha_ini, fecha_fin, BanxicoClient())


_register()


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:  # streamable-http via uvicorn (produccion: mcp.http_app())
        import uvicorn

        app = mcp.streamable_http_app() if hasattr(mcp, "streamable_http_app") else mcp.sse_app()
        uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()

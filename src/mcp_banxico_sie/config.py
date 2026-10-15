"""Config central. Token solo por env, nunca hardcodeado."""
import os

BASE_URL = os.environ.get(
    "BANXICO_BASE_URL",
    "https://www.banxico.org.mx/SieAPIRest/service/v1",
).rstrip("/")


def get_token() -> str:
    tok = os.environ.get("BANXICO_TOKEN", "").strip()
    if len(tok) != 64:
        raise RuntimeError(
            "Falta BANXICO_TOKEN de 64 chars. "
            "Consiguelo en https://www.banxico.org.mx/SieAPIRest/service/v1/token "
            "y define $env:BANXICO_TOKEN / export BANXICO_TOKEN."
        )
    return tok


# IDs canonicos B+C (caracterizacion 20261015). SF43783 es duplicado legacy de TIIE28, se documenta pero no se usa.
TASA_OBJETIVO = "SF61745"
TIIE_28 = "SF60648"
TIIE_91 = "SF60649"
CETES_28 = "SF60633"
UDIS = "SP68257"
TIIE_28_LEGACY = "SF43783"

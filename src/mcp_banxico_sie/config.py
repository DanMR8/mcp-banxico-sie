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

# Divisas v2 (catalogo oficial SIE-API). FIX es la referencia para USD.
DOLAR_FIX = "SF43718"
DOLAR_DOF = "SF60653"
DIVISAS = {
    "USD": DOLAR_FIX,
    "EUR": "SF46410",
    "JPY": "SF46406",
    "GBP": "SF46407",
    "CAD": "SF60632",
}

# v3: salario minimo + reservas (caracterizacion 20261015).
SALARIO_MINIMO = "SL11298"
RESERVAS = "SF43707"

# v4: curva TIIE, finanzas publicas, SPEI, expectativas (20261015).
# SF43878 descartada: duplicado verificado de TIIE_91 (SF60649).
TIIE_FONDEO = "SF331451"
TIIE_182 = "SF111916"
GASTO_PRIMARIO = "SG59"
ISR = "SG80"
IVA = "SG81"
IEPS_GAS = "SG79"
IEPS_OTRO = "SG55"
SPEI_ENV_MONTO = "SF406262"
SPEI_ENV_NUM = "SF406263"
SPEI_REC_MONTO = "SF406458"
EXP_INFLACION = "SR14138"

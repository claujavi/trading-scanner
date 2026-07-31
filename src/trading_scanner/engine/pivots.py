"""Estructura de tendencia por pivotes (HPH/HPL vs LPH/LPL) sobre velas
diarias — reemplaza el bit binario de criterio_sma200. Ver
docs/spec_criterio_pivotes.md para la definición numérica completa.

Función pura: no toca red ni Schwab, solo opera sobre el DataFrame de velas
diarias que el sistema ya descarga."""

from typing import Literal, Optional

import pandas as pd
import polars as pl

from ..indicators.volume import calc_atr
from ..models import ScanConfig

Relacion = Literal["Higher", "Lower", "Equal"]


def _to_pandas(df: pl.DataFrame) -> pd.DataFrame:
    if isinstance(df, pl.DataFrame):
        return df.to_pandas()
    return df


def _detectar_pivotes(valores: list[float], ventana_l: int, es_alto: bool) -> list[float]:
    """Pivotes fractales: la barra i es un pivote si es estrictamente mayor
    (alto) o menor (bajo) que las `ventana_l` barras anteriores Y las
    `ventana_l` barras siguientes. Devuelve los valores en orden
    cronológico (más antiguo primero). Un pivote en la barra i solo puede
    calcularse una vez existen las `ventana_l` barras posteriores — mismo
    lag estructural documentado en la spec."""
    n = len(valores)
    pivotes = []
    for i in range(ventana_l, n - ventana_l):
        vecinos = valores[i - ventana_l:i] + valores[i + 1:i + ventana_l + 1]
        if es_alto:
            if valores[i] > max(vecinos):
                pivotes.append(valores[i])
        else:
            if valores[i] < min(vecinos):
                pivotes.append(valores[i])
    return pivotes


def _comparar(actual: float, anterior: float, atr: float, tolerancia_atr: float) -> Relacion:
    margen = tolerancia_atr * atr
    diferencia = actual - anterior
    if diferencia > margen:
        return "Higher"
    if diferencia < -margen:
        return "Lower"
    return "Equal"


def _racha(
    pivotes: list[float], minimos: int, atr: float, tolerancia_atr: float
) -> Optional[Relacion]:
    """Confirma si los últimos `minimos` pivotes forman una racha
    consistente (todos "Higher" entre sí consecutivamente, o todos
    "Lower"). None si no hay pivotes suficientes o la racha es mixta
    (incluye algún "Equal")."""
    if len(pivotes) < minimos:
        return None
    ultimos = pivotes[-minimos:]
    relaciones = [
        _comparar(ultimos[j], ultimos[j - 1], atr, tolerancia_atr)
        for j in range(1, len(ultimos))
    ]
    if all(r == "Higher" for r in relaciones):
        return "Higher"
    if all(r == "Lower" for r in relaciones):
        return "Lower"
    return None


def detect_estructura_pivotes(df_d: Optional[pl.DataFrame], config: ScanConfig) -> Optional[str]:
    """"ALCISTA" si los pivotes altos Y bajos más recientes confirman HPH+HPL,
    "BAJISTA" si confirman LPH+LPL, None en cualquier otro caso (datos
    insuficientes o estructura mixta) — None es "criterio no calculable",
    no penaliza el score (Regla 2), no hace fallback a ningún otro dato."""
    if df_d is None or len(df_d) == 0:
        return None

    pdf = _to_pandas(df_d)
    for col in ("high", "low", "close"):
        if col not in pdf.columns:
            return None

    atr_serie = calc_atr(df_d, config.atr_periodo).to_list()
    if not atr_serie:
        return None
    atr = atr_serie[-1]
    if atr is None or atr <= 0:
        return None

    ventana_l = config.pivote_ventana_l
    minimos = config.pivote_minimos_consecutivos
    tolerancia_atr = config.pivote_tolerancia_atr

    pivotes_altos = _detectar_pivotes(pdf["high"].astype(float).tolist(), ventana_l, es_alto=True)
    pivotes_bajos = _detectar_pivotes(pdf["low"].astype(float).tolist(), ventana_l, es_alto=False)

    racha_altos = _racha(pivotes_altos, minimos, atr, tolerancia_atr)
    racha_bajos = _racha(pivotes_bajos, minimos, atr, tolerancia_atr)

    if racha_altos == "Higher" and racha_bajos == "Higher":
        return "ALCISTA"
    if racha_altos == "Lower" and racha_bajos == "Lower":
        return "BAJISTA"
    return None

from datetime import date

from src.trading_scanner.optimizer.cli_3bp import ultimo_dia_mes_cerrado


def test_mitad_de_mes_devuelve_fin_del_mes_anterior():
    assert ultimo_dia_mes_cerrado(date(2026, 9, 21)) == date(2026, 8, 31)


def test_primer_dia_del_mes_tambien_devuelve_mes_anterior():
    assert ultimo_dia_mes_cerrado(date(2026, 9, 1)) == date(2026, 8, 31)


def test_enero_cruza_de_anio():
    assert ultimo_dia_mes_cerrado(date(2026, 1, 15)) == date(2025, 12, 31)


def test_mes_anterior_bisiesto():
    assert ultimo_dia_mes_cerrado(date(2028, 3, 10)) == date(2028, 2, 29)

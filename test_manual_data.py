#!/usr/bin/env python
"""
Prueba manual rápida: flujo de datos desde Schwab → indicadores
"""
import sys
from rich.console import Console
from rich.table import Table
import polars as pl

from src.trading_scanner.fetchers.schwab_history import get_history
from src.trading_scanner.indicators.trend import calc_ema
from src.trading_scanner.indicators.volume import calc_atr_pct

console = Console()

try:
    console.print("\n[bold cyan]1. Descargando últimas 30 velas diarias de AAPL...[/]")
    df = get_history("AAPL", "d", 30)
    console.print(f"✓ Descargadas {len(df)} velas")

    console.print("\n[bold cyan]2. Primeras 3 velas (más antiguas):[/]")
    table_first = Table(title="AAPL Daily — Primeras 3 velas")
    table_first.add_column("timestamp", style="cyan")
    table_first.add_column("open", justify="right")
    table_first.add_column("high", justify="right")
    table_first.add_column("low", justify="right")
    table_first.add_column("close", justify="right")
    table_first.add_column("volume", justify="right")
    
    for row in df.head(3).to_dicts():
        ts = str(row["timestamp"])
        table_first.add_row(
            ts,
            f"{row['open']:.2f}",
            f"{row['high']:.2f}",
            f"{row['low']:.2f}",
            f"{row['close']:.2f}",
            f"{row['volume']:,}"
        )
    console.print(table_first)

    console.print("\n[bold cyan]3. Últimas 3 velas (más recientes):[/]")
    table_last = Table(title="AAPL Daily — Últimas 3 velas")
    table_last.add_column("timestamp", style="cyan")
    table_last.add_column("open", justify="right")
    table_last.add_column("high", justify="right")
    table_last.add_column("low", justify="right")
    table_last.add_column("close", justify="right")
    table_last.add_column("volume", justify="right")
    
    for row in df.tail(3).to_dicts():
        ts = str(row["timestamp"])
        table_last.add_row(
            ts,
            f"{row['open']:.2f}",
            f"{row['high']:.2f}",
            f"{row['low']:.2f}",
            f"{row['close']:.2f}",
            f"{row['volume']:,}"
        )
    console.print(table_last)

    console.print("\n[bold cyan]4. Verificando orden (timestamp ascendente):[/]")
    timestamps = df["timestamp"].to_list()
    is_sorted = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
    if is_sorted:
        console.print("[green]✓ Velas ordenadas de más antigua a más reciente[/]")
    else:
        console.print("[red]✗ ADVERTENCIA: Velas NO están ordenadas correctamente[/]")

    console.print("\n[bold cyan]5. Calculando EMA 9 y EMA 21...[/]")
    ema9 = calc_ema(df, 9)
    ema21 = calc_ema(df, 21)
    console.print(f"✓ EMA calculadas ({len(ema9)} valores cada una)")

    console.print("\n[bold cyan]6. Últimos 5 valores de EMA 9:[/]")
    table_ema9 = Table(title="EMA 9")
    table_ema9.add_column("índice", justify="right")
    table_ema9.add_column("valor", justify="right")
    for i, val in enumerate(ema9.tail(5).to_list()):
        idx = len(ema9) - 5 + i
        table_ema9.add_row(str(idx), f"{val:.4f}")
    console.print(table_ema9)

    console.print("\n[bold cyan]7. Últimos 5 valores de EMA 21:[/]")
    table_ema21 = Table(title="EMA 21")
    table_ema21.add_column("índice", justify="right")
    table_ema21.add_column("valor", justify="right")
    for i, val in enumerate(ema21.tail(5).to_list()):
        idx = len(ema21) - 5 + i
        table_ema21.add_row(str(idx), f"{val:.4f}")
    console.print(table_ema21)

    console.print("\n[bold cyan]8. Calculando ATR% (período 14)...[/]")
    atr_pct = calc_atr_pct(df, 14)
    last_atr_pct = atr_pct.to_list()[-1] if len(atr_pct) > 0 else None
    console.print(f"✓ Último valor ATR%: [yellow]{last_atr_pct:.4f}%[/]")

    console.print("\n[bold green]✓ PRUEBA MANUAL COMPLETADA EXITOSAMENTE[/]\n")

except Exception as e:
    console.print(f"\n[bold red]✗ Error: {e}[/]")
    import traceback
    traceback.print_exc()
    sys.exit(1)

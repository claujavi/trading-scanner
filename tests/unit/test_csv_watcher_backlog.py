import shutil
from pathlib import Path

from trading_scanner.ingest.csv_watcher import CSVWatcher

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_procesar_backlog_mueve_csv_preexistente_a_processed(tmp_path):
    """Un CSV soltado en input/ mientras el servidor estaba caído nunca
    dispara on_created (watchdog solo ve eventos con el proceso vivo) —
    procesar_backlog() cubre ese caso escaneando lo que ya está en disco."""
    input_folder = tmp_path / "input"
    input_folder.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scan.csv", input_folder / "sample_scan.csv")

    watcher = CSVWatcher(input_folder)
    watcher.start()
    try:
        procesados = watcher.procesar_backlog()
    finally:
        watcher.stop()

    assert procesados == 1
    assert not (input_folder / "sample_scan.csv").exists()
    movidos = list((input_folder / "processed").glob("sample_scan*.csv"))
    assert len(movidos) == 1


def test_procesar_backlog_sin_csv_no_hace_nada(tmp_path):
    input_folder = tmp_path / "input"
    input_folder.mkdir()

    watcher = CSVWatcher(input_folder)
    watcher.start()
    try:
        procesados = watcher.procesar_backlog()
    finally:
        watcher.stop()

    assert procesados == 0


def test_procesar_backlog_funciona_sin_haber_llamado_start(tmp_path):
    """procesar_backlog crea su propio handler si se llama antes de start()
    (ej. un test o un script que no necesita el Observer de filesystem)."""
    input_folder = tmp_path / "input"
    input_folder.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scan.csv", input_folder / "sample_scan.csv")

    watcher = CSVWatcher(input_folder)
    procesados = watcher.procesar_backlog()

    assert procesados == 1
    assert not (input_folder / "sample_scan.csv").exists()

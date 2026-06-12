import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .csv_parser import parse_csv

console = Console()


def wait_for_stable(path: Path, timeout_sec: int = 10) -> None:
    last_size, elapsed = -1, 0
    while elapsed < timeout_sec:
        time.sleep(0.5)
        current_size = path.stat().st_size
        if current_size == last_size and current_size > 0:
            return
        last_size, elapsed = current_size, elapsed + 0.5
    raise TimeoutError(f"CSV no estabilizado en {timeout_sec}s: {path}")


class CsvWatchHandler(FileSystemEventHandler):
    def __init__(self, input_folder: Path, processed_folder: Path):
        self.input_folder = input_folder
        self.processed_folder = processed_folder

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_file(Path(event.src_path))

    def on_moved(self, event):
        if event.is_directory:
            return
        self._handle_file(Path(event.dest_path))

    def _handle_file(self, path: Path) -> None:
        if path.suffix.lower() != ".csv":
            return

        try:
            wait_for_stable(path)
        except Exception as exc:
            console.log(f"[red]Error estabilizando CSV {path.name}: {exc}[/red]")
            return

        try:
            tickers = parse_csv(path)
            console.log(
                f"[green]CSV procesado:{path.name} -> {len(tickers)} tickers parseados[/green]"
            )
        except Exception as exc:
            console.log(f"[red]Error parseando CSV {path.name}: {exc}[/red]")
            return

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        destination = self.processed_folder / f"{path.stem}_{timestamp}{path.suffix}"
        self.processed_folder.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(path), str(destination))
            console.log(f"[blue]CSV movido a:[/blue] {destination}")
        except Exception as exc:
            console.log(f"[red]Error moviendo CSV {path.name}: {exc}[/red]")


class CSVWatcher:
    def __init__(self, input_folder: Path, processed_folder: Optional[Path] = None):
        self.input_folder = input_folder
        self.processed_folder = processed_folder or input_folder / "processed"
        self.observer = Observer()
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.input_folder.mkdir(parents=True, exist_ok=True)
        self.processed_folder.mkdir(parents=True, exist_ok=True)
        handler = CsvWatchHandler(self.input_folder, self.processed_folder)
        self.observer.schedule(handler, str(self.input_folder), recursive=False)
        self.observer.start()
        console.log(f"[green]CSV watcher iniciado en {self.input_folder}[/green]")

    def stop(self) -> None:
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            console.log(f"[yellow]CSV watcher detenido[/yellow]")

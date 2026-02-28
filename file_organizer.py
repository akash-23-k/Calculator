#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║         FILE ORGANIZER  v2.0             ║
║   Interactive CLI  |  Zero config needed ║
╚══════════════════════════════════════════╝

Install the pretty UI (one-time, optional):
    pip install rich

Run interactively:
    python file_organizer.py

Run headless (for cron / Task Scheduler):
    python file_organizer.py --auto /path/to/folder
    python file_organizer.py --auto /path/to/folder --dry-run
    python file_organizer.py --auto /path/to/folder --undo

Scheduling:
    # Linux/macOS cron — every day at 8 AM
    0 8 * * * python3 /path/to/file_organizer.py --auto /path/to/folder >> /path/to/cron.log 2>&1

    # Windows Task Scheduler
    schtasks /create /tn "FileOrganizer" /sc daily /st 08:00 ^
             /tr "python C:\\path\\file_organizer.py --auto C:\\Users\\You\\Downloads"
"""

import os, sys, json, shutil, logging, argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ── Try to import Rich; fall back to plain ANSI ───────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.progress import (
        Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    )
    from rich import box
    RICH = True
except ImportError:
    RICH = False

# ── ANSI colours (plain fallback) ─────────────────────────────────────────────
RST = "\033[0m";  BOLD = "\033[1m";   DIM  = "\033[2m"
CYN = "\033[96m"; GRN  = "\033[92m";  YLW  = "\033[93m"
RED = "\033[91m"; MAG  = "\033[95m"


# ═══════════════════════════════════════════════════════════════════════════════
#  EXTENSION → CATEGORY MAP
# ═══════════════════════════════════════════════════════════════════════════════
EXTENSION_MAP: dict[str, str] = {
    ".jpg":"Images",  ".jpeg":"Images", ".png":"Images",  ".gif":"Images",
    ".bmp":"Images",  ".svg":"Images",  ".webp":"Images", ".ico":"Images",  ".tiff":"Images",
    ".pdf":"Documents", ".doc":"Documents", ".docx":"Documents", ".xls":"Documents",
    ".xlsx":"Documents",".ppt":"Documents", ".pptx":"Documents", ".odt":"Documents",
    ".ods":"Documents", ".txt":"Documents", ".rtf":"Documents",  ".csv":"Documents",
    ".mp4":"Videos",  ".mkv":"Videos",  ".mov":"Videos",  ".avi":"Videos",
    ".wmv":"Videos",  ".flv":"Videos",  ".webm":"Videos", ".m4v":"Videos",
    ".mp3":"Audio",   ".wav":"Audio",   ".flac":"Audio",  ".aac":"Audio",
    ".ogg":"Audio",   ".m4a":"Audio",   ".wma":"Audio",
    ".zip":"Archives",".tar":"Archives",".gz":"Archives", ".rar":"Archives",
    ".7z":"Archives", ".bz2":"Archives",".xz":"Archives",
    ".py":"Code",  ".js":"Code",  ".ts":"Code",  ".html":"Code", ".css":"Code",
    ".java":"Code",".cpp":"Code", ".c":"Code",   ".h":"Code",   ".cs":"Code",
    ".go":"Code",  ".rs":"Code",  ".rb":"Code",  ".php":"Code",  ".sh":"Code",
    ".bat":"Code", ".json":"Code",".xml":"Code", ".yaml":"Code", ".yml":"Code",
    ".exe":"Executables",".msi":"Executables",".dmg":"Executables",
    ".deb":"Executables",".rpm":"Executables",
    ".ttf":"Fonts",".otf":"Fonts",".woff":"Fonts",".woff2":"Fonts",
}

ICONS = {
    "Images":"🖼️ ","Documents":"📄 ","Videos":"🎬 ","Audio":"🎵 ",
    "Archives":"🗜️ ","Code":"💻 ","Executables":"⚙️ ","Fonts":"🔤 ","Others":"📦 ",
}

UNDO_FILE = ".organizer_undo.json"


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
def setup_logger(log_path: Path | None) -> logging.Logger:
    logger = logging.getLogger("FileOrganizer")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    if log_path:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def resolve_collision(dest: Path) -> Path:
    """Append _1, _2 … until the filename is free."""
    if not dest.exists():
        return dest
    stem, suffix, parent, n = dest.stem, dest.suffix, dest.parent, 1
    while True:
        candidate = parent / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def scan_files(folder: Path) -> list[Path]:
    script = Path(__file__).resolve().name
    return sorted([
        f for f in folder.iterdir()
        if f.is_file() and f.name not in (script, UNDO_FILE)
    ])


def categorise(files: list[Path]) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        groups[EXTENSION_MAP.get(f.suffix.lower(), "Others")].append(f)
    return dict(groups)


def save_undo(folder: Path, moves: list[dict]):
    with (folder / UNDO_FILE).open("w", encoding="utf-8") as fp:
        json.dump({"timestamp": datetime.now().isoformat(), "moves": moves}, fp, indent=2)


def load_undo(folder: Path) -> list[dict] | None:
    p = folder / UNDO_FILE
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as fp:
        return json.load(fp).get("moves", [])


# ═══════════════════════════════════════════════════════════════════════════════
#  UI HELPERS  (Rich or plain ANSI)
# ═══════════════════════════════════════════════════════════════════════════════
def ui_print(msg: str, style: str = "", console=None):
    if RICH and console:
        console.print(f"[{style}]{msg}[/{style}]" if style else msg)
    else:
        color = {"yellow":YLW,"green":GRN,"red":RED,"cyan":CYN,
                 "dim":DIM,"bold":BOLD,"magenta":MAG}.get(style,"")
        print(f"{color}{msg}{RST}")


def banner(console=None):
    if RICH and console:
        console.print(Panel.fit(
            "[bold cyan]FILE ORGANIZER[/bold cyan]  [dim]v2.0[/dim]\n"
            "[dim]Scan · Preview · Move · Undo[/dim]",
            border_style="cyan", padding=(0, 4)
        ))
    else:
        print(f"{CYN}{BOLD}")
        print("╔══════════════════════════════╗")
        print("║    FILE ORGANIZER  v2.0      ║")
        print("╚══════════════════════════════╝")
        print(RST)


def show_preview(groups: dict[str, list[Path]], console=None):
    if RICH and console:
        t = Table(title="📋  Preview — files to be organised",
                  box=box.ROUNDED, border_style="cyan", show_lines=True)
        t.add_column("Category",  style="bold magenta", no_wrap=True)
        t.add_column("File",      style="white")
        t.add_column("Ext",       style="dim cyan", justify="center")
        for cat, files in sorted(groups.items()):
            icon = ICONS.get(cat, "📦 ")
            for i, f in enumerate(files):
                label = f"{icon}{cat}" if i == 0 else ""
                t.add_row(label, f.name, f.suffix.lower() or "—")
        console.print(t)
    else:
        print(f"\n{BOLD}📋  Preview{RST}")
        print(DIM + "─" * 48 + RST)
        for cat, files in sorted(groups.items()):
            print(f"\n{MAG}{BOLD}  {ICONS.get(cat,'📦 ')}{cat}  ({len(files)}){RST}")
            for f in files:
                print(f"{DIM}    • {f.name}{RST}")


def show_summary(moved, skipped, errors, elapsed, dry_run, console=None):
    color  = "yellow" if dry_run else "green"
    c_ansi = YLW if dry_run else GRN
    mode   = "DRY-RUN PREVIEW" if dry_run else "COMPLETE ✅"

    if RICH and console:
        t = Table(box=box.SIMPLE_HEAVY, border_style=color, show_header=False)
        t.add_column("k", style="bold"); t.add_column("v", justify="right")
        t.add_row("Status",     f"[{color}]{mode}[/{color}]")
        t.add_row("Moved",      str(moved))
        t.add_row("Skipped",    str(skipped))
        t.add_row("Errors",     f"[red]{errors}[/red]" if errors else "0")
        t.add_row("Time",       f"{elapsed:.2f}s")
        if dry_run:
            t.add_row("[yellow]Note[/yellow]", "No files were actually moved")
        console.print(Panel(t, title="Summary", border_style=color))
    else:
        print(f"\n{BOLD}── Summary {'─'*35}{RST}")
        print(f"{c_ansi}  Status : {mode}{RST}")
        print(f"  Moved  : {moved}")
        print(f"  Errors : {RED+str(errors)+RST if errors else '0'}")
        print(f"  Time   : {elapsed:.2f}s")
        if dry_run:
            print(f"{YLW}  (No files were actually moved){RST}")


def plain_bar(done: int, total: int):
    pct = done / total
    w   = 38
    bar = "█" * int(w * pct) + "░" * (w - int(w * pct))
    sys.stdout.write(f"\r  [{bar}] {done}/{total}  ")
    sys.stdout.flush()


def ask_input(prompt: str, choices: list[str] | None = None, default: str = "") -> str:
    if RICH:
        return Prompt.ask(prompt, choices=choices, default=default)
    hint = f" [{'/'.join(choices)}]" if choices else ""
    dflt = f" (default: {default})" if default else ""
    val  = input(f"{CYN}{prompt}{hint}{dflt}: {RST}").strip()
    return val or default


def ask_confirm(prompt: str, default: bool = True) -> bool:
    if RICH:
        return Confirm.ask(prompt, default=default)
    ans = input(f"{CYN}{prompt} [{'Y/n' if default else 'y/N'}]: {RST}").strip().lower()
    return (ans in ("y", "yes")) if ans else default


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE — ORGANISE
# ═══════════════════════════════════════════════════════════════════════════════
def organise(
    folder: Path,
    dry_run: bool,
    logger: logging.Logger,
    console=None,
) -> tuple[int, int, int, list[dict]]:

    files  = scan_files(folder)
    groups = categorise(files)
    total  = len(files)

    if total == 0:
        ui_print("No files found in the directory.", "yellow", console)
        return 0, 0, 0, []

    show_preview(groups, console)

    moved, errors = 0, 0
    undo_moves: list[dict] = []

    if RICH and console:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=36),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console, transient=True,
        ) as prog:
            label = "[DRY-RUN] Previewing…" if dry_run else "Organising…"
            task  = prog.add_task(label, total=total)
            for cat, cat_files in sorted(groups.items()):
                dest_dir = folder / cat
                for f in cat_files:
                    ok = _move_file(f, dest_dir, dry_run, logger, undo_moves)
                    if ok: moved  += 1
                    else:  errors += 1
                    prog.advance(task)
    else:
        print()
        for cat, cat_files in sorted(groups.items()):
            dest_dir = folder / cat
            for f in cat_files:
                ok = _move_file(f, dest_dir, dry_run, logger, undo_moves)
                if ok: moved  += 1
                else:  errors += 1
                plain_bar(moved + errors, total)
        print()

    return moved, 0, errors, undo_moves


def _move_file(
    f: Path, dest_dir: Path, dry_run: bool,
    logger: logging.Logger, undo_moves: list[dict]
) -> bool:
    dest = resolve_collision(dest_dir / f.name)
    note = f" (renamed → {dest.name})" if dest.name != f.name else ""

    if dry_run:
        logger.info(f"[DRY-RUN] {f.name} → {dest_dir.name}/{dest.name}")
        undo_moves.append({"src": str(f), "dst": str(dest)})
        return True
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(dest))
        logger.info(f"Moved: {f.name} → {dest_dir.name}/{dest.name}{note}")
        undo_moves.append({"src": str(f), "dst": str(dest)})
        return True
    except Exception as e:
        logger.error(f"Failed '{f.name}': {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE — UNDO
# ═══════════════════════════════════════════════════════════════════════════════
def undo_last(folder: Path, console=None):
    moves = load_undo(folder)
    if not moves:
        ui_print("No undo log found. Nothing to undo.", "yellow", console)
        return

    count, errors = 0, 0
    for m in reversed(moves):
        src, dst = Path(m["src"]), Path(m["dst"])
        if dst.exists():
            try:
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src))
                count += 1
            except Exception as e:
                errors += 1
                ui_print(f"Could not undo '{dst.name}': {e}", "red", console)

    # Clean up empty category folders
    for m in moves:
        cat_dir = Path(m["dst"]).parent
        try:
            if cat_dir.is_dir() and not any(cat_dir.iterdir()):
                cat_dir.rmdir()
        except Exception:
            pass

    (folder / UNDO_FILE).unlink(missing_ok=True)
    ui_print(f"Undo complete — {count} file(s) restored, {errors} error(s).", "green", console)


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERACTIVE MENU
# ═══════════════════════════════════════════════════════════════════════════════
def interactive(console=None):
    if not RICH:
        print(f"{YLW}Tip: run  pip install rich  for a prettier experience.{RST}\n")

    banner(console)

    while True:
        if RICH and console:
            console.print("\n[bold cyan]What would you like to do?[/bold cyan]")
            console.print("  [bold]1[/bold]  Organise a folder")
            console.print("  [bold]2[/bold]  Preview only (dry-run)")
            console.print("  [bold]3[/bold]  Undo last organise")
            console.print("  [bold]4[/bold]  Exit\n")
        else:
            print(f"\n{CYN}{BOLD}What would you like to do?{RST}")
            for n, label in [("1","Organise a folder"),("2","Preview only (dry-run)"),
                              ("3","Undo last organise"),("4","Exit")]:
                print(f"  {BOLD}{n}{RST}  {label}")
            print()

        choice = ask_input("Choice", choices=["1","2","3","4"], default="1")

        if choice == "4":
            ui_print("Bye! 👋", "dim", console); break

        # ── Folder path ───────────────────────────────────────────────────────
        raw    = ask_input("📁  Folder path (drag & drop works too)")
        folder = Path(raw.strip("'\"")).expanduser().resolve()
        if not folder.is_dir():
            ui_print(f"'{folder}' is not a valid directory.", "red", console)
            continue

        if choice == "3":
            undo_last(folder, console)
            continue

        dry_run = choice == "2"

        # ── Log file ──────────────────────────────────────────────────────────
        want_log = ask_confirm("📝  Save a log file?", default=False)
        log_path = None
        if want_log:
            log_name = ask_input("   Log filename", default="organizer.log")
            log_path = folder / log_name

        logger = setup_logger(log_path)
        start  = datetime.now()

        moved, skipped, errors, undo_moves = organise(folder, dry_run, logger, console)

        elapsed = (datetime.now() - start).total_seconds()
        show_summary(moved, skipped, errors, elapsed, dry_run, console)

        if not dry_run and undo_moves:
            save_undo(folder, undo_moves)
            ui_print("💾  Undo log saved — choose option 3 anytime to reverse.", "dim", console)

        if log_path:
            ui_print(f"📄  Log saved → {log_path}", "dim", console)

        if not ask_confirm("\n🔄  Do something else?", default=False):
            ui_print("Bye! 👋", "dim", console); break


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="File Organizer v2 — interactive menu or headless mode.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--auto",     metavar="FOLDER", help="Headless mode (no menu).")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--undo",     action="store_true")
    parser.add_argument("--log-file", metavar="PATH")
    args   = parser.parse_args()
    console = Console() if RICH else None

    if args.auto:
        # ── Headless / cron mode ──────────────────────────────────────────────
        folder = Path(args.auto).expanduser().resolve()
        logger = setup_logger(Path(args.log_file) if args.log_file else None)
        if args.undo:
            undo_last(folder, console)
            return
        start = datetime.now()
        moved, skipped, errors, undo_moves = organise(folder, args.dry_run, logger, console)
        elapsed = (datetime.now() - start).total_seconds()
        show_summary(moved, skipped, errors, elapsed, args.dry_run, console)
        if not args.dry_run and undo_moves:
            save_undo(folder, undo_moves)
    else:
        # ── Interactive menu ──────────────────────────────────────────────────
        interactive(console)


if __name__ == "__main__":
    main()

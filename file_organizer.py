import os
import sys
import json
import shutil
import logging
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# default formats

DEFAULT_EXTENSION_MAP: dict[str, str] = {
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images",
    ".gif": "Images", ".bmp": "Images", ".svg": "Images",
    ".webp": "Images", ".ico": "Images", ".tiff": "Images",
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".ppt": "Documents",
    ".pptx": "Documents", ".odt": "Documents", ".ods": "Documents",
    ".txt": "Documents", ".rtf": "Documents", ".csv": "Documents",
    # Videos
    ".mp4": "Videos", ".mkv": "Videos", ".mov": "Videos",
    ".avi": "Videos", ".wmv": "Videos", ".flv": "Videos",
    ".webm": "Videos", ".m4v": "Videos",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio",
    ".aac": "Audio", ".ogg": "Audio", ".m4a": "Audio",
    ".wma": "Audio",
    # Archives
    ".zip": "Archives", ".tar": "Archives", ".gz": "Archives",
    ".rar": "Archives", ".7z": "Archives", ".bz2": "Archives",
    ".xz": "Archives",
    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code", ".html": "Code",
    ".css": "Code", ".java": "Code", ".cpp": "Code", ".c": "Code",
    ".h": "Code", ".cs": "Code", ".go": "Code", ".rs": "Code",
    ".rb": "Code", ".php": "Code", ".sh": "Code", ".bat": "Code",
    ".json": "Code", ".xml": "Code", ".yaml": "Code", ".yml": "Code",
    # Executables
    ".exe": "Executables", ".msi": "Executables", ".dmg": "Executables",
    ".deb": "Executables", ".rpm": "Executables", ".appimage": "Executables",
    # Fonts
    ".ttf": "Fonts", ".otf": "Fonts", ".woff": "Fonts", ".woff2": "Fonts",
}

#logger setup

def setup_logger(log_file: str | None, dry_run: bool) -> logging.Logger:
    """Configure a logger that writes to console and optionally a file."""
    logger = logging.getLogger("FileOrganizer")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s  [%(levelname)-7s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (optional)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    mode_label = "[DRY-RUN] " if dry_run else ""
    logger.info(f"{mode_label}File Organizer started.")

    return logger


# ──────────────────────────────────────────────
#  CORE LOGIC
# ──────────────────────────────────────────────
def resolve_collision(destination: Path) -> Path:
    """
    If `destination` already exists, append _1, _2, … until we find a free name.
    E.g.  report.pdf → report_1.pdf → report_2.pdf
    """
    if not destination.exists():
        return destination

    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 1

    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def load_extension_map(config_path: str | None) -> dict[str, str]:
    """Load extension map from a JSON config file, falling back to the default."""
    if config_path:
        config_file = Path(config_path)
        if not config_file.is_file():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        with config_file.open(encoding="utf-8") as f:
            custom_map = json.load(f)
        # Normalise keys to lowercase with leading dot
        return {
            (k if k.startswith(".") else f".{k}").lower(): v
            for k, v in custom_map.items()
        }
    return DEFAULT_EXTENSION_MAP


def organize_folder(
    target_dir: Path,
    extension_map: dict[str, str],
    dry_run: bool,
    logger: logging.Logger,
) -> dict[str, int]:
    """
    Scan `target_dir` (non-recursively) and move files into subfolders.

    Returns a summary dict: {"moved": n, "skipped": n, "errors": n}
    """
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target is not a directory: {target_dir}")

    summary: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)

    # Collect only files (ignore subdirectories and this script itself)
    script_name = Path(__file__).resolve().name
    files = [
        f for f in target_dir.iterdir()
        if f.is_file() and f.name != script_name
    ]

    if not files:
        logger.info("No files found in the target directory.")
        return dict(summary)

    logger.info(f"Found {len(files)} file(s) in '{target_dir}'.")

    for file_path in sorted(files):
        ext = file_path.suffix.lower()
        category = extension_map.get(ext, "Others")

        dest_dir = target_dir / category
        dest_file = resolve_collision(dest_dir / file_path.name)

        collision_note = (
            f"  (renamed → '{dest_file.name}')"
            if dest_file.name != file_path.name
            else ""
        )

        if dry_run:
            logger.info(
                f"[DRY-RUN] Would move: '{file_path.name}' "
                f"→ {category}/{dest_file.name}{collision_note}"
            )
            summary["moved"] += 1
        else:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(dest_file))
                logger.info(
                    f"Moved: '{file_path.name}' "
                    f"→ {category}/{dest_file.name}{collision_note}"
                )
                summary["moved"] += 1
                category_counts[category] += 1
            except PermissionError as e:
                logger.error(f"Permission denied — '{file_path.name}': {e}")
                summary["errors"] += 1
            except Exception as e:
                logger.error(f"Failed to move '{file_path.name}': {e}")
                summary["errors"] += 1

    # Per-category breakdown (actual run only)
    if not dry_run and category_counts:
        logger.info("── Category breakdown ──────────────────────")
        for cat, count in sorted(category_counts.items()):
            logger.info(f"  {cat:<20} {count:>4} file(s)")

    return dict(summary)


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Organize files in a folder into subfolders by extension.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "directory",
        help="Path to the folder to organize.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would happen without moving any files.",
    )
    parser.add_argument(
        "--log-file",
        metavar="PATH",
        default=None,
        help="Path to a log file (in addition to console output).",
    )
    parser.add_argument(
        "--config",
        metavar="JSON_FILE",
        default=None,
        help="Path to a custom JSON extension→category mapping file.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    target_dir = Path(args.directory).resolve()
    logger = setup_logger(args.log_file, args.dry_run)

    try:
        extension_map = load_extension_map(args.config)
        start = datetime.now()

        summary = organize_folder(
            target_dir=target_dir,
            extension_map=extension_map,
            dry_run=args.dry_run,
            logger=logger,
        )

        elapsed = (datetime.now() - start).total_seconds()
        mode = "DRY-RUN preview" if args.dry_run else "Run"

        logger.info("── Summary ─────────────────────────────────")
        logger.info(f"  {mode} completed in {elapsed:.2f}s")
        logger.info(f"  Files moved   : {summary.get('moved', 0)}")
        logger.info(f"  Errors        : {summary.get('errors', 0)}")
        if args.dry_run:
            logger.info("  (No files were actually moved — dry-run mode)")

    except (FileNotFoundError, NotADirectoryError) as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()

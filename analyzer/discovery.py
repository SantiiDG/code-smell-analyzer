"""
Motor de descubrimiento de archivos y filtrado de directorios/extensiones ignoradas.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator, Iterable, Optional, Set

from analyzer.constants import (
    ALL_SUPPORTED_EXTENSIONS,
    BINARY_EXTENSIONS,
    IGNORED_DIRS,
    IGNORED_FILE_SUFFIXES,
    LANGUAGE_EXTENSIONS,
)


def is_ignored_directory(dir_name: str, extra_excludes: Set[str]) -> bool:
    """Verifica si un nombre de directorio debe ser excluido del escaneo."""
    if dir_name in IGNORED_DIRS or dir_name in extra_excludes:
        return True
    return dir_name.endswith(".egg-info")


def is_ignored_path(path: Path, extra_excludes: Optional[Set[str]] = None) -> bool:
    """Determina si una ruta corresponde a un archivo binario, minificado o carpeta ignorada."""
    excludes = extra_excludes or set()
    if any(is_ignored_directory(part, excludes) for part in path.parts):
        return True

    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    name_lower = path.name.lower()
    if name_lower in excludes:
        return True

    return any(name_lower.endswith(suffix) for suffix in IGNORED_FILE_SUFFIXES)


def resolve_target_extensions(lang: str) -> Set[str]:
    """Resuelve el conjunto de extensiones de archivo correspondientes al filtro de lenguaje."""
    normalized = lang.strip().lower()
    if normalized == "all":
        return ALL_SUPPORTED_EXTENSIONS

    mapped = LANGUAGE_EXTENSIONS.get(normalized)
    if mapped:
        return mapped

    clean_ext = f".{normalized.lstrip('.')}"
    return {clean_ext}


def _filter_matching_files(
    current_dir: str,
    filenames: Iterable[str],
    valid_extensions: Set[str],
    extra_excludes: Set[str],
) -> Generator[Path, None, None]:
    """Filtra archivos de un directorio según su extensión y reglas de exclusión."""
    base_path = Path(current_dir)
    for filename in filenames:
        file_path = base_path / filename
        if is_ignored_path(file_path, extra_excludes):
            continue
        if file_path.suffix.lower() in valid_extensions:
            yield file_path


def discover_files(
    root: Path,
    lang: str = "all",
    extra_excludes: Optional[Set[str]] = None,
) -> Generator[Path, None, None]:
    """Recorre recursivamente una ruta devolviendo todos los archivos analizables."""
    excludes = extra_excludes or set()
    if root.is_file():
        if not is_ignored_path(root, excludes):
            yield root
        return

    valid_extensions = resolve_target_extensions(lang)
    for current_dir, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not is_ignored_directory(d, excludes)]
        yield from _filter_matching_files(current_dir, filenames, valid_extensions, excludes)

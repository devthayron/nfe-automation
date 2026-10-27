import os
import re
from itertools import islice
from pathlib import Path

from importer.config import ANOS, CANCELED_SUFFIX, XML_ROOT

# Pares encontrados na mesma pasta, por exemplo:
# 3526...1234.xml <-> 3526...1234_CANCELADA.xml
# Só são registrados quando o nome-base é uma chave de acesso de 44 dígitos.
# Estes dicionários são mutados com .clear(); nunca reatribua (X = {}).
PAIRED_NORMAL_TO_CANCELLED: dict[Path, Path] = {}
PAIRED_CANCELLED_TO_NORMAL: dict[Path, Path] = {}


def is_canceled_path(path: Path) -> bool:
    """Considera cancelada a NF-e cujo nome termina em _CANCELADA."""
    return path.stem.upper().endswith(CANCELED_SUFFIX)


def filename_access_key(path: Path) -> str | None:
    """Retorna a chave de 44 dígitos do nome do arquivo, se houver."""
    stem = path.stem
    if is_canceled_path(path):
        stem = stem[: -len(CANCELED_SUFFIX)]
    return stem if re.fullmatch(r"\d{44}", stem) else None


def _register_pairs(root: Path, xml_names: list[str]) -> None:
    """Registra pares normal/cancelado presentes na mesma pasta."""
    names_by_casefold = {name.casefold(): name for name in xml_names}

    for name in xml_names:
        cancelled_path = root / name
        if not is_canceled_path(cancelled_path):
            continue

        key_from_name = filename_access_key(cancelled_path)
        if key_from_name is None:
            continue

        normal_name = (
            f"{cancelled_path.stem[: -len(CANCELED_SUFFIX)]}{cancelled_path.suffix}"
        )
        actual_normal_name = names_by_casefold.get(normal_name.casefold())
        if actual_normal_name is None:
            continue

        normal_path = root / actual_normal_name
        PAIRED_NORMAL_TO_CANCELLED[normal_path] = cancelled_path
        PAIRED_CANCELLED_TO_NORMAL[cancelled_path] = normal_path


def are_cancellation_pair(path_a: Path, path_b: Path) -> bool:
    """True se os dois caminhos forem o par normal/cancelado identificado."""
    return (
        PAIRED_NORMAL_TO_CANCELLED.get(path_a) == path_b
        or PAIRED_NORMAL_TO_CANCELLED.get(path_b) == path_a
    )


def iter_xml_files():
    """
    Percorre os XMLs sem armazenar todos os caminhos.
    Registra pares normal/_CANCELADA na mesma pasta e entrega os cancelados
    primeiro, para que possam ser processados antes do arquivo normal pareado.
    """
    PAIRED_NORMAL_TO_CANCELLED.clear()
    PAIRED_CANCELLED_TO_NORMAL.clear()
    years = {str(year) for year in ANOS}

    for root_str, dirs, files in os.walk(XML_ROOT):
        dirs[:] = [
            directory
            for directory in dirs
            if not (re.fullmatch(r"\d{4}", directory) and directory not in years)
        ]

        root = Path(root_str)
        xml_names = [name for name in files if name.lower().endswith(".xml")]
        _register_pairs(root, xml_names)

        # Os cancelados vêm antes dos normais dentro da mesma pasta. Se o
        # cancelado for inválido, ele não será marcado como processado e o
        # arquivo normal continuará elegível para importação.
        xml_names.sort(
            key=lambda name: (not is_canceled_path(Path(name)), name.casefold())
        )
        for name in xml_names:
            yield root / name


def batched(iterable, size):
    iterator = iter(iterable)
    while batch := list(islice(iterator, size)):
        yield batch

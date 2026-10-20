import logging
import tempfile
from pathlib import Path, PurePosixPath

import streamlit as st

from parser.nfe_parser import NFeParser

logger = logging.getLogger(__name__)

CANCELED_SUFFIX = "_CANCELADA"


def _safe_filename(name):
    """Retorna somente o nome final do arquivo."""
    return PurePosixPath(name.replace("\\", "/")).name


def process_xmls(files):
    nfes = []
    seen = set()
    duplicated = 0
    failed = 0
    canceled = 0

    for file in files:
        filename = _safe_filename(file.name)
        stem = Path(filename).stem

        # Ignora arquivos cujo nome termina com _CANCELADA.
        if stem.upper().endswith(CANCELED_SUFFIX.upper()):
            canceled += 1
            logger.info("XML cancelado ignorado: %s", file.name)
            continue

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / filename
            path.write_bytes(file.getvalue())

            try:
                parser = NFeParser(str(path))
                parser.read_nfe()
                nfe = parser.extract_data()
            except Exception:
                failed += 1
                logger.exception("Falha ao processar XML: %s", file.name)
                st.warning(f"Não foi possível processar o arquivo '{file.name}'.")
                continue

        if not nfe:
            failed += 1
            logger.warning("Falha ao extrair NF-e: %s", file.name)
            st.warning(f"Não foi possível processar o arquivo '{file.name}'.")
            continue

        if nfe.ch_nfe in seen:
            duplicated += 1
            logger.warning(
                "XML duplicado ignorado: NF-e %s (%s)",
                nfe.n_nf,
                file.name,
            )
            st.toast(
                f"NF-e {nfe.n_nf} já foi selecionada. "
                "O arquivo duplicado foi ignorado.",
                icon="⚠️",
            )
            continue

        seen.add(nfe.ch_nfe)
        nfes.append(nfe)

    logger.info(
        "Processamento concluído: %d arquivo(s), %d NF-e(s), "
        "%d cancelada(s) ignorada(s), %d duplicada(s), %d falha(s).",
        len(files),
        len(nfes),
        canceled,
        duplicated,
        failed,
    )

    if canceled:
        st.toast(f"{canceled} arquivo(s) cancelado(s) ignorado(s).")

    return nfes

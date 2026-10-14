import logging
import tempfile
from pathlib import Path, PurePosixPath

import streamlit as st

from parser.nfe_parser import NFeParser

logger = logging.getLogger(__name__)


def _safe_filename(name):
    """Returns only the final file name.

    In folder uploads, `name` comes with the relative path (e.g. "pasta/sub/a.xml")
    and is not sanitized by Streamlit.
    """
    return PurePosixPath(name.replace("\\", "/")).name


def process_xmls(files):
    nfes = []
    seen = set()
    duplicated = 0
    failed = 0

    for file in files:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / _safe_filename(file.name)
            path.write_bytes(file.getvalue())

            parser = NFeParser(str(path))
            parser.read_nfe()
            nfe = parser.extract_data()

        if not nfe:
            failed += 1
            logger.warning("Falha ao processar XML: %s", file.name)

            st.warning(f"Não foi possível processar o arquivo '{file.name}'.")
            continue

        if nfe.ch_nfe in seen:
            duplicated += 1
            logger.warning("XML duplicado ignorado: NF-e %s (%s)", nfe.n_nf, file.name)

            st.toast(
                f"NF-e {nfe.n_nf} já foi selecionada. O arquivo duplicado foi ignorado.",
                icon="⚠️",
            )
            continue

        seen.add(nfe.ch_nfe)
        nfes.append(nfe)

    logger.info(
        "Processamento concluído: %d arquivo(s), %d NF-e(s) processada(s), "
        "%d duplicada(s), %d falha(s).",
        len(files),
        len(nfes),
        duplicated,
        failed,
    )

    return nfes

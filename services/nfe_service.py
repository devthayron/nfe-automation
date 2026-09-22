import logging
import tempfile
from pathlib import Path

import streamlit as st

from parser.nfe_parser import NFeParser

logger = logging.getLogger(__name__)


def process_xmls(files):
    nfes = []
    xmls = {}
    duplicated = 0
    failed = 0

    for file in files:
        content = file.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / file.name
            path.write_bytes(content)

            parser = NFeParser(str(path))
            parser.read_nfe()
            nfe = parser.extract_data()

        if not nfe:
            failed += 1
            logger.warning("Falha ao processar XML: %s", file.name)

            st.warning(f"Não foi possível processar o arquivo '{file.name}'.")
            continue

        if nfe.ch_nfe in xmls:
            duplicated += 1
            logger.warning("XML duplicado ignorado: NF-e %s (%s)", nfe.n_nf, file.name)

            st.toast(
                f"NF-e {nfe.n_nf} já foi selecionada. O arquivo duplicado foi ignorado.",
                icon="⚠️",
            )
            continue

        nfes.append(nfe)

        xmls[nfe.ch_nfe] = {"name": file.name, "content": content.decode("utf-8")}

    logger.info(
        "Processamento concluído: %d arquivo(s), %d NF-e(s) processada(s), "
        "%d duplicada(s), %d falha(s).",
        len(files),
        len(nfes),
        duplicated,
        failed,
    )

    return nfes, xmls

import tempfile
from pathlib import Path

import streamlit as st

from parser.nfe_parser import NFeParser


def process_xmls(files):
    nfes = []
    xmls = {}

    for file in files:
        content = file.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / file.name
            path.write_bytes(content)

            parser = NFeParser(str(path))
            parser.read_nfe()
            nfe = parser.extract_data()

        if not nfe:
            st.warning(f"Não foi possível processar o arquivo '{file.name}'.")
            continue

        if nfe.ch_nfe in xmls:
            st.warning(
                f"NF-e {nfe.n_nf} já foi selecionada. O arquivo duplicado foi ignorado."
            )
            continue

        nfes.append(nfe)

        xmls[nfe.ch_nfe] = {
            "name": file.name,
            "content": content.decode("utf-8"),
        }

    return nfes, xmls

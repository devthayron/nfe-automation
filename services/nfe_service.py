import tempfile
from pathlib import Path

import streamlit as st

from parser.nfe_parser import NFeParser


def processar_xmls(arquivos):
    nfes = []
    xmls = {}

    for arquivo in arquivos:
        conteudo = arquivo.getvalue()

        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / arquivo.name
            caminho.write_bytes(conteudo)

            parser = NFeParser(str(caminho))
            parser.ler_nfe()
            nfe = parser.extrair_dados()

        if not nfe:
            st.warning(f"Não foi possível processar o arquivo '{arquivo.name}'.")
            continue

        if nfe.ch_nfe in xmls:
            st.warning(
                f"NF-e {nfe.n_nf} já foi selecionada. O arquivo duplicado foi ignorado."
            )
            continue

        nfes.append(nfe)

        xmls[nfe.ch_nfe] = {
            "nome": arquivo.name,
            "conteudo": conteudo.decode("utf-8"),
        }

    return nfes, xmls

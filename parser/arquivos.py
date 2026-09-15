from pathlib import Path

from parser.nfe_parser import NFeParser


def carregar_nfes(pasta="data"):
    nfes = []

    for caminho in sorted(Path(pasta).glob("*.xml")):
        parser = NFeParser(str(caminho))
        parser.ler_nfe()

        nfe = parser.extrair_dados()

        if nfe:
            nfes.append(nfe)
    return nfes

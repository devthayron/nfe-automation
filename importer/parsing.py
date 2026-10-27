import signal
from pathlib import Path

from parser.nfe_parser import NFeParser


def ignore_sigint():
    """Só o processo principal trata Ctrl+C."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def parse_file(path_str):
    """
    Roda nos processos filhos (precisa ficar no nível do módulo).
    Retorna (caminho, NFe | None, bytes do XML | None, erro | None).
    """
    try:
        raw = Path(path_str).read_bytes()
        parser = NFeParser(path_str, raw=raw)
        parser.read_nfe()
        nfe = parser.extract_data()

        if nfe is None:
            return path_str, None, None, "Falha ao extrair a NF-e"

        return path_str, nfe, raw, None

    except Exception as exc:
        return path_str, None, None, f"{type(exc).__name__}: {exc}"

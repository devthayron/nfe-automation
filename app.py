import streamlit as st

from excel import generate_dataframe
from interface import display_filters, display_report
from logger import setup_logging
from services.nfe_service import process_xmls

setup_logging()

about = """
    Aplicação para processamento de XMLs de NF-e Modelo 55 e geração
    de relatórios estruturados para consulta e análise.
    
    Os arquivos XML são processados temporariamente e não são armazenados pela aplicação.

    **Status:** Em fase de testes.
"""


def main():

    st.set_page_config(
        page_title="NF-e Automation", layout="wide", menu_items={"About": about}
    )

    st.title("Relatório de NF-e")
    st.caption("Leitura e extração de dados de XMLs de NF-e (Modelo 55)")
    st.sidebar.header("Origem dos dados")

    files = st.sidebar.file_uploader(
        "Selecione a pasta com os XMLs",
        type="xml",
        accept_multiple_files="directory",
    )

    st.sidebar.caption(
        "Os arquivos XML são processados **temporariamente** e não são armazenados."
    )

    if not files:
        st.info("Selecione a pasta com os XMLs para gerar o relatório.")
        return

    nfes = process_xmls(files)

    if not nfes:
        st.error("Nenhuma NF-e válida foi encontrada.")
        return

    df = generate_dataframe(nfes)
    df = display_filters(df)

    display_report(df, len(nfes))


if __name__ == "__main__":
    main()

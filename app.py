import streamlit as st

from excel import generate_dataframe
from interface import display_filters, display_report, display_xml
from services.nfe_service import process_xmls

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
        "Selecione os arquivos XML", type="xml", accept_multiple_files=True
    )

    st.sidebar.caption(
        "Os arquivos XML são processados **temporariamente** e não são armazenados."
    )

    if not files:
        st.info("Selecione os arquivos XML para gerar o relatório.")
        return

    nfes, xmls = process_xmls(files)

    if not nfes:
        st.error("Nenhuma NF-e válida foi encontrada.")
        return

    df = generate_dataframe(nfes)
    df = display_filters(df)

    report_tab, xml_tab = st.tabs(["Relatório", "XML da NF-e"])

    with report_tab:
        display_report(df, len(nfes))

    with xml_tab:
        display_xml(nfes, xmls)


if __name__ == "__main__":
    main()

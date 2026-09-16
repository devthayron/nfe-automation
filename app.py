import streamlit as st

from excel import gerar_df
from interface import exibir_filtros, exibir_relatorio, exibir_xml
from services.nfe_service import processar_xmls

about = """ 
    Aplicação para processamento de XMLs de NFs modelo 55 e geração de relatórios estruturados para consulta e análise.

    **Status:** Em fase de testes.
    """


def main():

    st.set_page_config(
        page_title="NF-e Automation",
        layout="wide",
        menu_items={"About": about},
    )

    st.title("Relatório de NF-e")

    st.sidebar.header("Origem dos dados")

    arquivos = st.sidebar.file_uploader(
        "Selecione os arquivos XML", type="xml", accept_multiple_files=True
    )

    if not arquivos:
        st.info("Selecione os arquivos XML para gerar o relatório.")
        return

    nfes, xmls = processar_xmls(arquivos)

    if not nfes:
        st.error("Nenhuma NF-e válida foi encontrada.")
        return

    df = gerar_df(nfes)
    df = exibir_filtros(df)

    aba_relatorio, aba_xml = st.tabs(["Relatório", "XML da NF-e"])

    with aba_relatorio:
        exibir_relatorio(df, len(nfes))

    with aba_xml:
        exibir_xml(nfes, xmls)


if __name__ == "__main__":
    main()

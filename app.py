import tempfile
from pathlib import Path

import streamlit as st

from excel import gerar_df
from parser.nfe_parser import NFeParser

st.set_page_config(page_title="NF-e Automation", layout="wide")

st.title("Relatório de NF-e")


def processar_arquivos(arquivos):
    nfes = []
    xmls = {}

    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)

        for arquivo in arquivos:
            conteudo = arquivo.getvalue()

            caminho = pasta / arquivo.name
            caminho.write_bytes(conteudo)

            parser = NFeParser(str(caminho))
            parser.ler_nfe()

            nfe = parser.extrair_dados()

            if nfe:
                nfes.append(nfe)

                # A própria chave da NF-e identifica o XML
                xmls[nfe.ch_nfe] = conteudo.decode("utf-8")

    return nfes, xmls


st.sidebar.header("Origem dos dados")

arquivos = st.sidebar.file_uploader(
    "Selecione os arquivos XML", type="xml", accept_multiple_files=True
)

if not arquivos:
    st.info("Selecione os arquivos XML para gerar o relatório.")
    st.stop()


nfes, xmls = processar_arquivos(arquivos)

if not nfes:
    st.error("Nenhuma NF-e válida foi encontrada.")
    st.stop()


df = gerar_df(nfes)


st.sidebar.header("Filtros")


def filtro_multiselect(df, coluna, label):
    valores = df[coluna].dropna().astype(str).unique().tolist()

    valores.sort()

    selecionados = st.sidebar.multiselect(label, valores)

    if selecionados:
        df = df[df[coluna].astype(str).isin(selecionados)]

    return df


df = filtro_multiselect(df, "REGIÃO", "Região")

df = filtro_multiselect(df, "Loja", "Loja")


aba_relatorio, aba_xml = st.tabs(["Relatório", "XML da NF-e"])


with aba_relatorio:
    col1, col2, col3 = st.columns(3)

    col1.metric("XMLs", len(nfes))

    col2.metric("Itens", len(df))

    col3.metric("Fornecedores", df["CNPJ_Fornecedor"].nunique())

    with tempfile.NamedTemporaryFile(suffix=".xlsx") as arquivo_temp:
        df.to_excel(arquivo_temp.name, index=False)

        with open(arquivo_temp.name, "rb") as arquivo:
            st.download_button(
                label="Exportar para Excel",
                data=arquivo,
                file_name="relatorio_nfe.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            )

    st.subheader("Relatório")

    st.dataframe(df, use_container_width=True, hide_index=True)


with aba_xml:
    st.subheader("XML da NF-e")

    opcoes_nfe = {str(nfe.n_nf): nfe.ch_nfe for nfe in nfes}

    numero_nfe = st.selectbox("Selecione a NF-e", list(opcoes_nfe.keys()))

    chave_nfe = opcoes_nfe[numero_nfe]

    with st.expander("Visualizar XML"):
        st.code(xmls[chave_nfe], language="xml")

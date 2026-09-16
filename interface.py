import tempfile

import streamlit as st


def aplicar_filtro(df, coluna, label):
    """Aplica um filtro ao DataFrame."""
    valores = sorted(df[coluna].dropna().astype(str).unique())

    selecionados = st.sidebar.multiselect(label, valores)

    if selecionados:
        df = df[df[coluna].astype(str).isin(selecionados)]

    return df


def exibir_filtros(df):
    """Exibe os filtros disponíveis."""
    st.sidebar.header("Filtros")

    df = aplicar_filtro(df, "REGIÃO", "Região")
    df = aplicar_filtro(df, "Loja", "Loja")

    return df


def gerar_excel(df):
    """Gera o arquivo Excel para download."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as arquivo_temp:
        df.to_excel(arquivo_temp.name, index=False)

        with open(arquivo_temp.name, "rb") as arquivo:
            return arquivo.read()


def exibir_relatorio(df, quantidade_nfes):
    """Exibe o relatório e a opção de exportação."""
    col1, col2, col3 = st.columns(3)

    col1.metric("XMLs", quantidade_nfes)
    col2.metric("Itens", len(df))
    col3.metric("Fornecedores", df["CNPJ_Fornecedor"].nunique())

    excel = gerar_excel(df)

    st.download_button(
        label="Exportar para Excel",
        data=excel,
        file_name="relatorio_nfe.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.subheader("Relatório")

    st.dataframe(df, use_container_width=True, hide_index=True)


def exibir_xml(nfes, xmls):
    """Exibe o XML da NF-e selecionada."""
    st.subheader("XML da NF-e")

    opcoes_nfe = {f"NF: {nfe.n_nf}": nfe.ch_nfe for nfe in nfes}

    identificacao = st.selectbox("Selecione a NF-e", list(opcoes_nfe.keys()))

    chave_nfe = opcoes_nfe[identificacao]

    with st.expander("Visualizar XML"):
        st.code(xmls[chave_nfe]["conteudo"], language="xml")

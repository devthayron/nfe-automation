import tempfile

import streamlit as st


def apply_filter(df, column, label):
    """Applies a filter to the DataFrame."""

    values = sorted(df[column].dropna().astype(str).unique())

    selected = st.sidebar.multiselect(label, values)

    if selected:
        df = df[df[column].astype(str).isin(selected)]

    return df


def display_filters(df):
    """Displays the available filters."""

    st.sidebar.header("Filtros")

    df = apply_filter(df, "REGIÃO", "Região")
    df = apply_filter(df, "Loja", "Loja")

    return df


def generate_excel(df):
    """Generates the Excel file for download."""

    with tempfile.NamedTemporaryFile(suffix=".xlsx") as temp_file:
        df.to_excel(temp_file.name, index=False)

        with open(temp_file.name, "rb") as file:
            return file.read()


def display_report(df, nfe_count):
    """Displays the report and the export option."""
    col1, col2, col3 = st.columns(3)

    col1.metric("XMLs", nfe_count)
    col2.metric("Itens", len(df))
    col3.metric("Fornecedores", df["CNPJ_Fornecedor"].nunique())

    col1, col2 = st.columns([5, 0.8])

    col1.subheader("Relatório")

    excel = generate_excel(df)

    col2.download_button(
        label="Exportar para Excel",
        data=excel,
        file_name="relatorio_nfe.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
        width="stretch",
    )

    st.dataframe(df, width="stretch", hide_index=True)

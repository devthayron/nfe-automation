import os
from datetime import timedelta

import streamlit as st
from dotenv import load_dotenv

from excel import generate_dataframe
from interface import display_report
from logger import setup_logging
from services.nfe_service import process_xmls

load_dotenv()  # lê o .env (DATABASE_URL) antes de qualquer os.getenv
setup_logging()

MAX_ROWS = 200_000

about = """
    Aplicação para processamento de XMLs de NF-e Modelo 55 e geração
    de relatórios estruturados para consulta e análise.
    
    Os arquivos XML são processados temporariamente e não são armazenados pela aplicação.

    **Status:** Em fase de testes.
"""


@st.cache_resource
def get_engine():
    from sqlalchemy import create_engine

    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


@st.cache_data(show_spinner=False)
def get_date_range():
    from services.db_service import get_date_range as _get_date_range

    return _get_date_range(get_engine())


@st.cache_data(show_spinner="Lendo o banco...")
def load_report_from_db(inicio, fim):
    from services.db_service import load_dataframe_from_db

    return load_dataframe_from_db(get_engine(), inicio, fim, MAX_ROWS)


def load_from_folder():
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
        return None

    nfes = process_xmls(files)

    if not nfes:
        st.error("Nenhuma NF-e válida foi encontrada.")
        return None

    return generate_dataframe(nfes)


def load_from_db():
    try:
        first, last = get_date_range()
    except Exception as exc:
        st.error(f"Não foi possível conectar ao banco: {exc}")
        return None

    if first is None:
        st.warning("O banco não tem NF-es.")
        return None

    # Por padrão, o último mês com NF-es no banco.
    periodo = st.sidebar.date_input(
        "Período de emissão",
        value=(max(first, last - timedelta(days=30)), last),
        min_value=first,
        max_value=last,
    )

    if st.sidebar.button("Recarregar banco"):
        load_report_from_db.clear()
        get_date_range.clear()

    if len(periodo) != 2:
        st.info("Selecione a data inicial e a final.")
        return None

    df = load_report_from_db(*periodo)

    if df.empty:
        st.warning("Nenhum item de NF-e no período selecionado.")
        return None

    if len(df) >= MAX_ROWS:
        st.warning(
            f"O resultado foi limitado a {MAX_ROWS:,} itens. "
            "Reduza o período para ver tudo."
        )

    return df


def main():

    st.set_page_config(
        page_title="NF-e Automation",
        layout="wide",
        menu_items={"About": about},
    )

    st.title("Relatório de NF-e")
    st.caption("Leitura e extração de dados de XMLs de NF-e (Modelo 55)")
    st.sidebar.header("Origem dos dados")

    # A opção de banco só aparece onde DATABASE_URL está configurada
    # (por exemplo, não aparece no Streamlit Cloud público).
    origens = ["Pasta de XMLs"]
    if os.getenv("DATABASE_URL"):
        origens.append("Banco de dados")

    origem = st.sidebar.radio("Origem", origens) if len(origens) > 1 else origens[0]

    df = load_from_folder() if origem == "Pasta de XMLs" else load_from_db()

    if df is None:
        return

    # df = display_filters(df)

    display_report(df, df["chave_acesso"].nunique())


if __name__ == "__main__":
    main()

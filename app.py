import calendar
import os
from datetime import date, datetime

import streamlit as st
from dotenv import load_dotenv

from interface import display_report
from logger import setup_logging
from services.nfe_service import process_xmls
from services.report_service import generate_dataframe

load_dotenv()
setup_logging()

MAX_ROWS = 10_000

MESES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

about = """
    Aplicação para processamento de XMLs de NF-e Modelo 55 e geração
    de relatórios estruturados para consulta e análise.

    Os arquivos XML selecionados em uma pasta são processados temporariamente
    pela aplicação. Na origem Banco de dados, os dados são consultados no PostgreSQL.

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
    # Permite atualizar o intervalo de datas e invalidar os relatórios em cache.
    if st.sidebar.button("Recarregar banco"):
        load_report_from_db.clear()
        get_date_range.clear()

    try:
        first, last = get_date_range()
    except Exception as exc:
        st.error(f"Não foi possível conectar ao banco: {exc}")
        return None

    if first is None or last is None:
        st.warning("O banco não tem NF-es.")
        return None

    # O serviço normalmente retorna date; também aceita datetime por segurança.
    if isinstance(first, datetime):
        first = first.date()
    if isinstance(last, datetime):
        last = last.date()

    # Anos em ordem decrescente, do mais recente ao mais antigo.
    anos = list(range(last.year, first.year - 1, -1))
    ano = st.sidebar.selectbox("Ano de emissão", options=anos)

    # Só oferece os meses que intersectam o intervalo de datas existente no banco.
    meses_disponiveis = []
    for mes in range(1, 13):
        primeiro_dia = date(ano, mes, 1)
        ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
        if ultimo_dia >= first and primeiro_dia <= last:
            meses_disponiveis.append(mes)

    if not meses_disponiveis:
        st.warning("Não há meses disponíveis para o ano selecionado.")
        return None

    # O padrão é o mês mais recente disponível no ano escolhido.
    mes = st.sidebar.selectbox(
        "Mês de emissão",
        options=meses_disponiveis,
        format_func=lambda valor: MESES[valor],
        index=len(meses_disponiveis) - 1,
        key=f"mes_emissao_{ano}",
    )

    # Consulta sempre um mês completo. O db_service trata o limite final
    inicio = date(ano, mes, 1)
    fim = date(ano, mes, calendar.monthrange(ano, mes)[1])
    st.sidebar.caption(f"Período consultado: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}")

    df = load_report_from_db(inicio, fim)

    if df.empty:
        st.warning("Nenhum item de NF-e no mês selecionado.")
        return None

    if len(df) >= MAX_ROWS:
        st.warning(
            f"O resultado foi limitado a {MAX_ROWS:,} itens. "
            "O mês pode conter mais registros; os dados exibidos podem estar incompletos."
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

    # A opção de banco só aparece quando DATABASE_URL está configurada.
    origens = ["Pasta de XMLs"]
    if os.getenv("DATABASE_URL"):
        origens.append("Banco de dados")

    origem = st.sidebar.radio("Origem", origens) if len(origens) > 1 else origens[0]
    df = load_from_folder() if origem == "Pasta de XMLs" else load_from_db()

    if df is None:
        return

    display_report(df, df["chave_acesso"].nunique())


if __name__ == "__main__":
    main()

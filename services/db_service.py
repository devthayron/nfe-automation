from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text

from services.report_service import TAX_COLUMNS

TIMEZONE = "America/Fortaleza"

# (coluna no relatório, expressão SQL). Mantém nomes e ordem compatíveis com
# excel.generate_dataframe para display_report funcionar nas duas origens.
BASE_COLUMNS = [
    ("UF_Loja", "d.uf"),
    ("CNPJ_Loja", "d.cnpj"),
    ("CNPJ_Fornecedor", "e.cnpj"),
    ("Fornecedor", "e.nome"),
    ("UF_Fornecedor", "e.uf"),
    ("chave_acesso", "n.ch_nfe"),
    ("nNF", "n.n_nf"),
    ("serie", "n.serie"),
    ("dhEmi", "to_char(n.dh_emi AT TIME ZONE :tz, 'DD/MM/YYYY HH24:MI:SS')"),
    ("nItem", "i.n_item"),
    ("cProd", "i.c_prod"),
    ("cEAN", "i.c_ean"),
    ("xProd", "i.x_prod"),
    ("NCM", "i.ncm"),
    ("CEST", "i.cest"),
    ("CFOP", "i.cfop"),
    ("uCom", "i.u_com"),
    ("qCom", "i.q_com"),
    ("vUnCom", "i.v_un_com"),
    ("vProd", "i.v_prod"),
    ("vDesc", "i.v_desc"),
]


def _tax_expression(tax, field, numeric):
    """Lê um campo do JSONB de impostos (numérico ou texto)."""
    expr = f"i.impostos->'{tax}'->>'{field}'"
    return f"({expr})::numeric" if numeric else expr


def _build_sql():
    columns = list(BASE_COLUMNS) + [
        (column, _tax_expression(tax, field, numeric))
        for tax, field, column, numeric in TAX_COLUMNS
    ]
    select = ",\n    ".join(f'{expr} AS "{name}"' for name, expr in columns)

    return text(
        f"""
        SELECT
            {select}
        FROM nfe_item i
        JOIN nfe n ON n.id = i.nfe_id
        LEFT JOIN pessoa e ON e.id = n.emit_id
        LEFT JOIN pessoa d ON d.id = n.dest_id
        WHERE n.cancelado = false
          AND n.dh_emi >= (CAST(:inicio AS timestamp) AT TIME ZONE :tz)
          AND n.dh_emi <  ((CAST(:fim AS timestamp) + interval '1 day') AT TIME ZONE :tz)
        ORDER BY n.dh_emi, n.id, i.n_item
        LIMIT :limite
        """
    )


SQL = _build_sql()


def get_date_range(engine):
    """Retorna a menor e a maior data de emissão em horário local, ou (None, None)."""
    with engine.connect() as conn:
        first, last = conn.execute(
            text("SELECT min(dh_emi), max(dh_emi) FROM nfe WHERE cancelado = false")
        ).one()

    if first is None or last is None:
        return None, None

    tz = ZoneInfo(TIMEZONE)
    return first.astimezone(tz).date(), last.astimezone(tz).date()


def get_xml(engine, ch_nfe: str) -> bytes | None:
    """Devolve os bytes originais do XML de uma NF-e, ou None se não existir."""
    with engine.connect() as conn:
        data = conn.execute(
            text(
                "SELECT x.xml FROM nfe_xml x "
                "JOIN nfe n ON n.id = x.nfe_id WHERE n.ch_nfe = :ch"
            ),
            {"ch": ch_nfe},
        ).scalar()

    return bytes(data) if data is not None else None


def load_dataframe_from_db(engine, inicio, fim, limite=200_000):
    """Carrega os itens emitidos entre as datas (inclusive), somente para leitura."""
    with engine.connect() as conn:
        # coerce_float=False mantém os valores numéricos como Decimal.
        return pd.read_sql_query(
            SQL,
            conn,
            params={
                "inicio": inicio,
                "fim": fim,
                "tz": TIMEZONE,
                "limite": limite,
            },
            coerce_float=False,
        )

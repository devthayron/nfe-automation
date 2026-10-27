from decimal import Decimal, InvalidOperation

import pandas as pd

# (imposto no JSON, campo no JSON, coluna no relatório, é numérico?)
TAX_COLUMNS = [
    ("ICMS", "grupo", "ICMS_grupo", False),
    ("ICMS", "orig", "ICMS_orig", False),
    ("ICMS", "CST", "ICMS_CST", False),
    ("ICMS", "CSOSN", "ICMS_CSOSN", False),
    ("ICMS", "vBC", "ICMS_vBC", True),
    ("ICMS", "pICMS", "ICMS_pICMS", True),
    ("ICMS", "vICMS", "ICMS_vICMS", True),
    ("ICMS", "vBCST", "ICMS_vBCST", True),
    ("ICMS", "pICMSST", "ICMS_pICMSST", True),
    ("ICMS", "vICMSST", "ICMS_vICMSST", True),
    ("PIS", "grupo", "PIS_grupo", False),
    ("PIS", "CST", "PIS_CST", False),
    ("PIS", "vBC", "PIS_vBC", True),
    ("PIS", "pPIS", "PIS_pPIS", True),
    ("PIS", "vPIS", "PIS_vPIS", True),
    ("PIS", "qBCProd", "PIS_qBCProd", True),
    ("PIS", "vAliqProd", "PIS_vAliqProd", True),
    ("COFINS", "grupo", "COFINS_grupo", False),
    ("COFINS", "CST", "COFINS_CST", False),
    ("COFINS", "vBC", "COFINS_vBC", True),
    ("COFINS", "pCOFINS", "COFINS_pCOFINS", True),
    ("COFINS", "vCOFINS", "COFINS_vCOFINS", True),
    ("COFINS", "qBCProd", "COFINS_qBCProd", True),
    ("COFINS", "vAliqProd", "COFINS_vAliqProd", True),
    ("IPI", "grupo", "IPI_grupo", False),
    ("IPI", "CST", "IPI_CST", False),
    ("IPI", "vBC", "IPI_vBC", True),
    ("IPI", "pIPI", "IPI_pIPI", True),
    ("IPI", "vIPI", "IPI_vIPI", True),
    ("IPI", "qUnid", "IPI_qUnid", True),
    ("IPI", "vUnid", "IPI_vUnid", True),
    ("IBSCBS", "CST", "IBSCBS_CST", False),
    ("IBSCBS", "cClassTrib", "IBSCBS_cClassTrib", False),
]


def _to_decimal(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _tax_columns(impostos):
    row = {}

    for tax, field, column, numeric in TAX_COLUMNS:
        group = impostos.get(tax)
        value = group.get(field) if isinstance(group, dict) else None
        row[column] = _to_decimal(value) if numeric else value

    return row


def generate_dataframe(nfes):
    rows = []

    for nfe in nfes:
        for item in nfe.items:
            product = item.product

            rows.append(
                {
                    "UF_Loja": nfe.dest.uf,
                    "CNPJ_Loja": nfe.dest.cnpj,
                    # FORNECEDOR
                    "CNPJ_Fornecedor": nfe.emit.cnpj,
                    "Fornecedor": nfe.emit.x_nome,
                    "UF_Fornecedor": nfe.emit.uf,
                    # NF-e
                    "chave_acesso": nfe.ch_nfe,
                    "nNF": str(nfe.n_nf),
                    "serie": str(nfe.serie),
                    "dhEmi": nfe.dh_emi.strftime("%d/%m/%Y %H:%M:%S"),
                    # ITEM
                    "nItem": item.n_item,
                    "cProd": product.c_prod,
                    "cEAN": product.c_ean,
                    "xProd": product.x_prod,
                    "NCM": product.ncm,
                    "CEST": product.cest,
                    "CFOP": product.cfop,
                    "uCom": product.u_com,
                    "qCom": product.q_com,
                    "vUnCom": product.v_un_com,
                    "vProd": product.v_prod,
                    "vDesc": product.v_desc,
                    # IMPOSTOS (lidos do JSON)
                    **_tax_columns(item.impostos),
                }
            )

    return pd.DataFrame(rows)


def generate_excel(nfes, path="data/nfes.xlsx"):
    df = generate_dataframe(nfes)
    df.to_excel(path, index=False)

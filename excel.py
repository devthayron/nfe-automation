import pandas as pd


def generate_dataframe(nfes):
    rows = []

    for nfe in nfes:
        for item in nfe.items:
            product = item.product
            taxation = item.taxation

            icms = taxation.icms if taxation else None
            pis = taxation.pis if taxation else None
            cofins = taxation.cofins if taxation else None
            ipi = taxation.ipi if taxation else None
            ibs_cbs = taxation.ibs_cbs if taxation else None

            rows.append(
                {
                    # REGIÃO / LOJA
                    "REGIÃO": None,
                    "UF_Loja": str(nfe.dest.uf),
                    "Codigo_Loja": None,
                    "Loja": None,
                    "CNPJ_Loja": str(nfe.dest.cnpj),
                    # FORNECEDOR
                    "CNPJ_Fornecedor": str(nfe.emit.cnpj),
                    "Fornecedor": nfe.emit.x_nome,
                    "UF_Fornecedor": str(nfe.emit.uf),
                    # NF-e
                    "chave_acesso": str(nfe.ch_nfe),
                    "nNF": nfe.n_nf,
                    "serie": nfe.serie,
                    "dhEmi": nfe.dh_emi.strftime("%d/%m/%Y %H:%M:%S"),
                    # ITEM
                    "nItem": item.n_item,
                    "cProd": str(product.c_prod),
                    "cEAN": (str(product.c_ean) if product.c_ean is not None else None),
                    "xProd": product.x_prod,
                    "NCM": str(product.ncm),
                    "CEST": (str(product.cest) if product.cest is not None else None),
                    "CFOP": str(product.cfop),
                    "uCom": str(product.u_com),
                    "qCom": product.q_com,
                    "vUnCom": product.v_un_com,
                    "vProd": product.v_prod,
                    "vDesc": product.v_desc,
                    # ICMS
                    "ICMS_CST_CSOSN": (
                        str(icms.cst_csosn)
                        if icms and icms.cst_csosn is not None
                        else None
                    ),
                    "ICMS_orig": icms.orig if icms else None,
                    "ICMS_vBC": icms.v_bc if icms else None,
                    "ICMS_pICMS": icms.p_icms if icms else None,
                    "ICMS_vICMS": icms.v_icms if icms else None,
                    "ICMS_vBCST": icms.v_bc_st if icms else None,
                    "ICMS_pICMSST": icms.p_icms_st if icms else None,
                    "ICMS_vICMSST": icms.v_icms_st if icms else None,
                    # PIS
                    "PIS_CST": (str(pis.cst) if pis and pis.cst is not None else None),
                    "PIS_vBC": pis.v_bc if pis else None,
                    "PIS_pPIS": pis.p_pis if pis else None,
                    "PIS_vPIS": pis.v_pis if pis else None,
                    # COFINS
                    "COFINS_CST": (
                        str(cofins.cst) if cofins and cofins.cst is not None else None
                    ),
                    "COFINS_vBC": cofins.v_bc if cofins else None,
                    "COFINS_pCOFINS": cofins.p_cofins if cofins else None,
                    "COFINS_vCOFINS": (cofins.v_cofins if cofins else None),
                    # IPI
                    "IPI_CST": (str(ipi.cst) if ipi and ipi.cst is not None else None),
                    "IPI_vBC": ipi.v_bc if ipi else None,
                    "IPI_pIPI": ipi.p_ipi if ipi else None,
                    "IPI_vIPI": ipi.v_ipi if ipi else None,
                    # IBS / CBS
                    "IBSCBS_CST": (
                        str(ibs_cbs.cst)
                        if ibs_cbs and ibs_cbs.cst is not None
                        else None
                    ),
                    "IBSCBS_cClassTrib": (
                        str(ibs_cbs.c_class_trib)
                        if ibs_cbs and ibs_cbs.c_class_trib is not None
                        else None
                    ),
                }
            )

    return pd.DataFrame(rows)


def generate_excel(nfes, path="data/nfes.xlsx"):
    df = generate_dataframe(nfes)
    df.to_excel(path, index=False)

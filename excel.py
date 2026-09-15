import pandas as pd


def gerar_df(nfes):

    linhas = []

    for nfe in nfes:
        for item in nfe.itens:
            produto = item.produto
            tributacao = item.tributacao

            icms = tributacao.icms if tributacao else None
            pis = tributacao.pis if tributacao else None
            cofins = tributacao.cofins if tributacao else None
            ipi = tributacao.ipi if tributacao else None
            ibs_cbs = tributacao.ibs_cbs if tributacao else None

            linhas.append(
                {
                    # REGIÃO / LOJA
                    "REGIÃO": None,
                    "UF_Loja": str(nfe.destinatario.uf),
                    "Codigo_Loja": None,
                    "Loja": None,
                    "CNPJ_Loja": str(nfe.destinatario.cnpj),
                    # FORNECEDOR
                    "CNPJ_Fornecedor": str(nfe.emitente.cnpj),
                    "Fornecedor": nfe.emitente.x_nome,
                    "UF_Fornecedor": str(nfe.emitente.uf),
                    # NF-e
                    "chave_acesso": str(nfe.ch_nfe),
                    "nNF": nfe.n_nf,
                    "serie": nfe.serie,
                    "dhEmi": nfe.dh_emi.strftime("%d/%m/%Y %H:%M:%S"),
                    # ITEM
                    "nItem": item.n_item,
                    "cProd": str(produto.c_prod),
                    "cEAN": (str(produto.c_ean) if produto.c_ean is not None else None),
                    "xProd": produto.x_prod,
                    "NCM": str(produto.ncm),
                    "CEST": (str(produto.cest) if produto.cest is not None else None),
                    "CFOP": str(produto.cfop),
                    "uCom": str(produto.u_com),
                    "qCom": produto.q_com,
                    "vUnCom": produto.v_un_com,
                    "vProd": produto.v_prod,
                    "vDesc": produto.v_desc,
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
                    "COFINS_vCOFINS": cofins.v_cofins if cofins else None,
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

    return pd.DataFrame(linhas)


def gerar_excel(nfes, caminho="data/nfes.xlsx"):
    df = gerar_df(nfes)
    df.to_excel(caminho, index=False)

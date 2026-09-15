from datetime import datetime
from decimal import Decimal

from nfelib.nfe.bindings.v4_0.proc_nfe_v4_00 import NfeProc

from schemas.nfe import (
    COFINS,
    IBSCBS,
    ICMS,
    IPI,
    PIS,
    ItemNFe,
    NFe,
    Pessoa,
    Produto,
    Tributacao,
)


class NFeParser:
    def __init__(self, caminho: str):
        self.caminho = caminho
        self.nfe_proc = None
        self.inf_nfe = None
        self.inf_prot = None

    def ler_nfe(self):
        try:
            self.nfe_proc = NfeProc.from_path(self.caminho)

            self.inf_nfe = self.nfe_proc.NFe.infNFe
            self.inf_prot = self.nfe_proc.protNFe.infProt

        except Exception as e:  # noqa: BLE001
            print(f"Erro ao ler XML da NFe: {e}")

    def extrair_nfe(self):
        ide = self.inf_nfe.ide

        return {
            "ch_nfe": str(self.inf_prot.chNFe),
            "n_nf": int(ide.nNF),
            "serie": int(ide.serie),
            "dh_emi": datetime.fromisoformat(str(ide.dhEmi)),
        }

    def extrair_emitente(self):
        emit = self.inf_nfe.emit

        return Pessoa(
            cnpj=str(emit.CNPJ),
            x_nome=str(emit.xNome),
            uf=str(emit.enderEmit.UF.value),
        )

    def extrair_destinatario(self):
        dest = self.inf_nfe.dest

        return Pessoa(
            cnpj=str(dest.CNPJ),
            x_nome=str(dest.xNome),
            uf=str(dest.enderDest.UF.value),
        )

    def extrair_produto(self, produto):
        v_desc = getattr(produto, "vDesc", None)

        return Produto(
            c_prod=str(produto.cProd),
            c_ean=str(produto.cEAN) if produto.cEAN else None,
            x_prod=str(produto.xProd),
            ncm=str(produto.NCM),
            cest=str(produto.CEST) if produto.CEST else None,
            cfop=str(produto.CFOP),
            u_com=str(produto.uCom),
            q_com=Decimal(str(produto.qCom)),
            v_un_com=Decimal(str(produto.vUnCom)),
            v_prod=Decimal(str(produto.vProd)),
            v_desc=Decimal(str(v_desc)) if v_desc else Decimal(0),
        )

    def encontrar_grupo(self, estrutura):
        for grupo in vars(estrutura).values():
            if grupo is not None:
                return grupo

        return None

    def converter_decimal(self, valor):
        if valor is None:
            return None

        return Decimal(str(valor))

    def extrair_icms(self, imposto):
        icms = imposto.ICMS

        if icms is None:
            return None

        grupo = self.encontrar_grupo(icms)

        if grupo is None:
            return None

        cst = getattr(grupo, "CST", None)
        csosn = getattr(grupo, "CSOSN", None)

        if cst is not None:
            cst_csosn = str(cst.value)
        elif csosn is not None:
            cst_csosn = str(csosn.value)
        else:
            cst_csosn = None

        orig = getattr(grupo, "orig", None)
        v_bc = getattr(grupo, "vBC", None)
        p_icms = getattr(grupo, "pICMS", None)
        v_icms = getattr(grupo, "vICMS", None)
        v_bc_st = getattr(grupo, "vBCST", None)
        p_icms_st = getattr(grupo, "pICMSST", None)
        v_icms_st = getattr(grupo, "vICMSST", None)

        return ICMS(
            orig=int(orig.value) if orig is not None else None,
            cst_csosn=cst_csosn,
            v_bc=self.converter_decimal(v_bc),
            p_icms=self.converter_decimal(p_icms),
            v_icms=self.converter_decimal(v_icms),
            v_bc_st=self.converter_decimal(v_bc_st),
            p_icms_st=self.converter_decimal(p_icms_st),
            v_icms_st=self.converter_decimal(v_icms_st),
        )

    def extrair_pis(self, imposto):
        pis = imposto.PIS

        if pis is None:
            return None

        grupo = self.encontrar_grupo(pis)

        if grupo is None:
            return None

        nome_grupo = type(grupo).__name__

        if nome_grupo not in {"Pisaliq", "Pisoutr", "Pisnt"}:
            print(f"Tipo de PIS não tratado: {nome_grupo}")

        cst = getattr(grupo, "CST", None)
        v_bc = getattr(grupo, "vBC", None)
        p_pis = getattr(grupo, "pPIS", None)
        v_pis = getattr(grupo, "vPIS", None)

        return PIS(
            cst=str(cst.value) if cst is not None else None,
            v_bc=self.converter_decimal(v_bc),
            p_pis=self.converter_decimal(p_pis),
            v_pis=self.converter_decimal(v_pis),
        )

    def extrair_cofins(self, imposto):
        cofins = imposto.COFINS

        if cofins is None:
            return None

        grupo = self.encontrar_grupo(cofins)

        if grupo is None:
            return None

        nome_grupo = type(grupo).__name__

        if nome_grupo not in {"Cofinsaliq", "Cofinsoutr", "Cofinsnt"}:
            print(f"Tipo de COFINS não tratado: {nome_grupo}")

        cst = getattr(grupo, "CST", None)
        v_bc = getattr(grupo, "vBC", None)
        p_cofins = getattr(grupo, "pCOFINS", None)
        v_cofins = getattr(grupo, "vCOFINS", None)

        return COFINS(
            cst=str(cst.value) if cst is not None else None,
            v_bc=self.converter_decimal(v_bc),
            p_cofins=self.converter_decimal(p_cofins),
            v_cofins=self.converter_decimal(v_cofins),
        )

    def extrair_ipi(self, imposto):
        ipi = imposto.IPI

        if ipi is None:
            return None

        if ipi.IPITrib is not None:
            grupo = ipi.IPITrib

            cst = getattr(grupo, "CST", None)
            v_bc = getattr(grupo, "vBC", None)
            p_ipi = getattr(grupo, "pIPI", None)
            v_ipi = getattr(grupo, "vIPI", None)

            return IPI(
                cst=str(cst.value) if cst is not None else None,
                v_bc=self.converter_decimal(v_bc),
                p_ipi=self.converter_decimal(p_ipi),
                v_ipi=self.converter_decimal(v_ipi),
            )

        elif ipi.IPINT is not None:
            grupo = ipi.IPINT

            cst = getattr(grupo, "CST", None)

            return IPI(
                cst=str(cst.value) if cst is not None else None,
            )
        else:
            print(f"Tipo de IPI não tratado: {type(grupo).__name__}")
            return None

    def extrair_ibs_cbs(self, imposto):
        ibs_cbs = imposto.IBSCBS

        if ibs_cbs is None:
            return None

        cst = getattr(ibs_cbs, "CST", None)
        c_class_trib = getattr(ibs_cbs, "cClassTrib", None)

        return IBSCBS(
            cst=str(cst) if cst is not None else None,
            c_class_trib=str(c_class_trib) if c_class_trib is not None else None,
        )

    def extrair_tributacao(self, imposto):
        tributacao = Tributacao()

        if imposto.ICMS:
            tributacao.icms = self.extrair_icms(imposto)

        if imposto.PIS:
            tributacao.pis = self.extrair_pis(imposto)

        if imposto.COFINS:
            tributacao.cofins = self.extrair_cofins(imposto)

        if imposto.IPI:
            tributacao.ipi = self.extrair_ipi(imposto)

        if imposto.IBSCBS:
            tributacao.ibs_cbs = self.extrair_ibs_cbs(imposto)

        return tributacao

    def extrair_itens(self):
        itens = []

        for item in self.inf_nfe.det:
            itens.append(
                ItemNFe(
                    n_item=int(item.nItem),
                    produto=self.extrair_produto(item.prod),
                    tributacao=self.extrair_tributacao(item.imposto),
                )
            )

        return itens

    def extrair_dados(self):
        try:
            dados_nfe = self.extrair_nfe()

            return NFe(
                **dados_nfe,
                emitente=self.extrair_emitente(),
                destinatario=self.extrair_destinatario(),
                itens=self.extrair_itens(),
            )

        except AttributeError as e:
            print(f"Estrutura da NFe incompleta: {e}")
            return None

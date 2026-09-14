from datetime import datetime
from decimal import Decimal

from nfelib.nfe.bindings.v4_0.proc_nfe_v4_00 import NfeProc

from schemas.nfe import (
    ICMS,
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
            "chave": str(self.inf_prot.chNFe),
            "numero": int(ide.nNF),
            "serie": int(ide.serie),
            "data_emissao": datetime.fromisoformat(str(ide.dhEmi)),
        }

    def extrair_emitente(self):
        emit = self.inf_nfe.emit

        return Pessoa(
            cnpj=str(emit.CNPJ),
            razao_social=str(emit.xNome),
            uf=str(emit.enderEmit.UF.value),
        )

    def extrair_destinatario(self):
        dest = self.inf_nfe.dest

        return Pessoa(
            cnpj=str(dest.CNPJ),
            razao_social=str(dest.xNome),
            uf=str(dest.enderDest.UF.value),
        )

    def extrair_produto(self, produto):
        desconto = getattr(produto, "vDesc", None)

        return Produto(
            codigo=str(produto.cProd),
            ean=str(produto.cEAN) if produto.cEAN else None,
            descricao=str(produto.xProd),
            ncm=str(produto.NCM),
            cest=str(produto.CEST) if produto.CEST else None,
            cfop=str(produto.CFOP),
            unidade=str(produto.uCom),
            quantidade=Decimal(str(produto.qCom)),
            valor_unitario=Decimal(str(produto.vUnCom)),
            valor_produto=Decimal(str(produto.vProd)),
            desconto=Decimal(str(desconto)) if desconto else Decimal(0),
        )

    def encontrar_grupo_icms(self, icms):
        for grupo in vars(icms).values():
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

        grupo = self.encontrar_grupo_icms(icms)

        if grupo is None:
            return None

        cst_csosn = None

        if hasattr(grupo, "CST") and grupo.CST is not None:
            cst_csosn = str(grupo.CST.value)
        elif hasattr(grupo, "CSOSN") and grupo.CSOSN is not None:
            cst_csosn = str(grupo.CSOSN.value)

        origem = getattr(grupo, "orig", None)
        v_bc = getattr(grupo, "vBC", None)
        p_icms = getattr(grupo, "pICMS", None)
        v_icms = getattr(grupo, "vICMS", None)

        base_calculo_st = getattr(grupo, "vBCST", None)
        aliquota_st = getattr(grupo, "pICMSST", None)
        valor_st = getattr(grupo, "vICMSST", None)

        return ICMS(
            origem=int(origem.value) if origem is not None else None,
            cst_csosn=cst_csosn,
            base_calculo=self.converter_decimal(v_bc),
            aliquota=self.converter_decimal(p_icms),
            valor=self.converter_decimal(v_icms),
            base_calculo_st=self.converter_decimal(base_calculo_st),
            aliquota_st=self.converter_decimal(aliquota_st),
            valor_st=self.converter_decimal(valor_st),
        )

    def extrair_pis(self, imposto):
        pass

    def extrair_cofins(self, imposto):
        pass

    def extrair_ipi(self, imposto):
        pass

    def extrair_ibs_cbs(self, imposto):
        pass

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
                    numero=int(item.nItem),
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

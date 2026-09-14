from datetime import datetime
from decimal import Decimal

from nfelib.nfe.bindings.v4_0.proc_nfe_v4_00 import NfeProc

from schemas.nfe import ItemNFe, NFe, Pessoa, Produto


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

        except Exception as e:
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

    def extrair_itens(self):
        itens = []

        for item in self.inf_nfe.det:
            itens.append(
                ItemNFe(
                    numero=int(item.nItem),
                    produto=self.extrair_produto(item.prod),
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

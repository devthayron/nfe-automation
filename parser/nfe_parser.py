import logging
from datetime import datetime
from decimal import Decimal

from nfelib.nfe.bindings.v4_0.proc_nfe_v4_00 import NfeProc

from schemas.nfe import (
    NFe,
    NFeItem,
    Person,
    Product,
)

from .tax_parser import TaxParser

logger = logging.getLogger(__name__)


class NFeParser:
    def __init__(self, path: str):
        self.path = path
        self.nfe_proc = None
        self.inf_nfe = None
        self.inf_prot = None
        self.tax_parser = TaxParser()

    def read_nfe(self):
        try:
            nfe_proc = NfeProc.from_path(self.path)
            inf_nfe = nfe_proc.NFe.infNFe
            inf_prot = getattr(
                getattr(nfe_proc, "protNFe", None),
                "infProt",
                None,
            )

        except Exception as exc:
            logger.exception("Erro ao ler XML da NF-e")
            raise ValueError("Não foi possível ler a estrutura da NF-e.") from exc

        mod = inf_nfe.ide.mod.value

        if mod != "55":
            raise ValueError(
                f"Modelo de documento não suportado: {mod!r}. "
                "Este parser aceita somente NF-e modelo 55."
            )

        self.nfe_proc = nfe_proc
        self.inf_nfe = inf_nfe
        self.inf_prot = inf_prot

    @staticmethod
    def _get_value(obj, field, default=None):
        """Retorna um campo quando ele existe e possui valor."""
        value = getattr(obj, field, None)
        return value if value not in (None, "") else default

    @staticmethod
    def _extract_document(person):
        """Obtém CNPJ ou CPF, preservando o documento como texto."""
        cnpj = getattr(person, "CNPJ", None)
        cpf = getattr(person, "CPF", None)

        if cnpj:
            return str(cnpj)

        if cpf:
            return str(cpf)

        return None

    @staticmethod
    def _extract_uf(address):
        if address is None:
            return None

        uf = getattr(address, "UF", None)
        if uf is None:
            return None

        return str(getattr(uf, "value", uf))

    def _extract_nfe(self):
        ide = self.inf_nfe.ide

        protocol_key = (
            getattr(self.inf_prot, "chNFe", None) if self.inf_prot is not None else None
        )
        inf_nfe_id = getattr(self.inf_nfe, "Id", None)

        # A chave pode estar no protocolo ou no atributo Id da infNFe.
        ch_nfe = protocol_key or (
            str(inf_nfe_id)[3:]
            if inf_nfe_id and str(inf_nfe_id).startswith("NFe")
            else None
        )

        dh_emi = self._get_value(ide, "dhEmi")
        if dh_emi is None:
            dh_emi = self._get_value(ide, "dEmi")

        if dh_emi is None:
            raise ValueError("A NF-e não possui data de emissão.")

        if ch_nfe is None:
            raise ValueError("Não foi possível obter a chave da NF-e.")

        return {
            "ch_nfe": str(ch_nfe),
            "n_nf": str(ide.nNF),
            "serie": str(ide.serie),
            "dh_emi": datetime.fromisoformat(str(dh_emi)),
        }

    def _extract_emit(self):
        emit = self.inf_nfe.emit

        return Person(
            cnpj=self._extract_document(emit),
            x_nome=str(self._get_value(emit, "xNome", "")),
            uf=self._extract_uf(getattr(emit, "enderEmit", None)),
        )

    def _extract_dest(self):
        dest = self.inf_nfe.dest

        return Person(
            cnpj=self._extract_document(dest),
            x_nome=str(self._get_value(dest, "xNome", "")),
            uf=self._extract_uf(getattr(dest, "enderDest", None)),
        )

    def _extract_product(self, product):
        v_desc = self._get_value(product, "vDesc")

        return Product(
            c_prod=str(self._get_value(product, "cProd", "")),
            c_ean=self._get_value(product, "cEAN"),
            x_prod=str(self._get_value(product, "xProd", "")),
            ncm=self._get_value(product, "NCM"),
            cest=self._get_value(product, "CEST"),
            cfop=str(self._get_value(product, "CFOP", "")),
            u_com=str(self._get_value(product, "uCom", "")),
            q_com=Decimal(str(product.qCom)),
            v_un_com=Decimal(str(product.vUnCom)),
            v_prod=Decimal(str(product.vProd)),
            v_desc=Decimal(str(v_desc)) if v_desc is not None else None,
        )

    def _extract_items(self):
        items = []

        for item in self.inf_nfe.det:
            items.append(
                NFeItem(
                    n_item=int(item.nItem),
                    product=self._extract_product(item.prod),
                    taxation=self.tax_parser._extract_taxation(item.imposto),
                )
            )

        return items

    def extract_data(self):
        """Extrai os dados da NF-e para os schemas da aplicação."""
        if self.inf_nfe is None:
            self.read_nfe()

        try:
            nfe_data = self._extract_nfe()

            return NFe(
                **nfe_data,
                emit=self._extract_emit(),
                dest=self._extract_dest(),
                items=self._extract_items(),
            )

        except (AttributeError, TypeError, ValueError) as exc:
            logger.warning(
                "Não foi possível extrair a NF-e %s: %s",
                self.path,
                exc,
            )
            return None

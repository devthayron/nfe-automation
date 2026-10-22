import logging
from datetime import datetime
from decimal import Decimal

from schemas.nfe import NFe, NFeItem, Person, Product

from .tax_extractor import extract_impostos, to_obj
from .xml_utils import child, children, find_first, parse_xml, parse_xml_bytes, text

logger = logging.getLogger(__name__)


def _dec(el, name):
    value = text(el, name)
    return Decimal(value) if value is not None else None


class NFeParser:
    def __init__(self, path: str, raw: bytes | None = None):
        self.path = path
        self.raw = raw  # bytes do XML, se já foram lidos (evita ler duas vezes)
        self.root = None
        self.inf_nfe = None
        self.inf_prot = None

    def read_nfe(self):
        try:
            root = (
                parse_xml_bytes(self.raw)
                if self.raw is not None
                else parse_xml(self.path)
            )
        except Exception as exc:
            logger.exception("Erro ao ler XML da NF-e")
            raise ValueError("Não foi possível ler a estrutura da NF-e.") from exc

        inf_nfe = find_first(root, "infNFe")
        if inf_nfe is None:
            raise ValueError("XML sem o grupo infNFe.")

        mod = text(inf_nfe, "ide", "mod")
        if mod != "55":
            raise ValueError(
                f"Modelo de documento não suportado: {mod!r}. "
                "Este parser aceita somente NF-e modelo 55."
            )

        self.root = root
        self.inf_nfe = inf_nfe
        self.inf_prot = find_first(root, "infProt")

    # ------------------------------------------------------------ cabeçalho

    def _extract_nfe(self):
        ide = child(self.inf_nfe, "ide")

        # A chave pode estar no protocolo ou no atributo Id da infNFe.
        ch_nfe = text(self.inf_prot, "chNFe") if self.inf_prot is not None else None
        if not ch_nfe:
            inf_id = self.inf_nfe.get("Id") or ""
            ch_nfe = inf_id[3:] if inf_id.startswith("NFe") else None

        if not ch_nfe:
            raise ValueError("Não foi possível obter a chave da NF-e.")

        dh_emi = text(ide, "dhEmi") or text(ide, "dEmi")
        if dh_emi is None:
            raise ValueError("A NF-e não possui data de emissão.")

        return {
            "ch_nfe": ch_nfe,
            "n_nf": text(ide, "nNF"),
            "serie": text(ide, "serie"),
            "dh_emi": datetime.fromisoformat(dh_emi),
        }

    @staticmethod
    def _extract_person(el, address_tag):
        if el is None:
            return Person()

        return Person(
            cnpj=text(el, "CNPJ") or text(el, "CPF"),
            x_nome=text(el, "xNome") or "",
            uf=text(el, address_tag, "UF"),
        )

    # ---------------------------------------------------------------- itens

    @staticmethod
    def _extract_product(prod):
        return Product(
            c_prod=text(prod, "cProd") or "",
            c_ean=text(prod, "cEAN"),
            x_prod=text(prod, "xProd") or "",
            ncm=text(prod, "NCM"),
            cest=text(prod, "CEST"),
            cfop=text(prod, "CFOP") or "",
            u_com=text(prod, "uCom") or "",
            q_com=_dec(prod, "qCom"),
            v_un_com=_dec(prod, "vUnCom"),
            v_prod=_dec(prod, "vProd"),
            v_desc=_dec(prod, "vDesc"),
        )

    @staticmethod
    def _item_number(det):
        # Formato padrão da NF-e: <det nItem="1">
        value = det.get("nItem") or next(
            (v for k, v in det.attrib.items() if k.lower() == "nitem"),
            None,
        )

        if value is not None and value.strip().isdigit():
            number = int(value.strip())
            if number > 0:
                return number

        # Compatibilidade com o formato do XML recebido:
        # <det><nItem>1</nItem>...</det>
        value = text(det, "nItem")

        if value is not None and value.strip().isdigit():
            number = int(value.strip())
            if number > 0:
                return number

        return None

    def _extract_items(self):
        items = []
        missing = 0

        for position, det in enumerate(children(self.inf_nfe, "det"), start=1):
            imposto = child(det, "imposto")

            n_item = self._item_number(det)
            if n_item is None:
                n_item = position
                missing += 1

            items.append(
                NFeItem(
                    n_item=n_item,
                    product=self._extract_product(child(det, "prod")),
                    impostos=extract_impostos(imposto) if imposto is not None else {},
                )
            )

        if missing:
            logger.warning(
                "%s item(ns) sem nItem válido em %s; usando a posição.",
                missing,
                self.path,
            )

        return items

    def _extract_totais(self):
        total = child(self.inf_nfe, "total")

        if total is None:
            return {}

        obj = to_obj(total)
        return obj if isinstance(obj, dict) else {}

    def extract_data(self):
        """Extrai os dados da NF-e para os schemas da aplicação."""
        if self.inf_nfe is None:
            self.read_nfe()

        try:
            return NFe(
                **self._extract_nfe(),
                emit=self._extract_person(child(self.inf_nfe, "emit"), "enderEmit"),
                dest=self._extract_person(child(self.inf_nfe, "dest"), "enderDest"),
                items=self._extract_items(),
                totais=self._extract_totais(),
            )

        except (AttributeError, TypeError, ValueError, ArithmeticError) as exc:
            logger.warning(
                "Não foi possível extrair a NF-e %s: %s",
                self.path,
                exc,
            )
            return None

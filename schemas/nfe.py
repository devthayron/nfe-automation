from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class Pessoa(BaseModel):
    cnpj: str
    razao_social: str
    uf: str


class Produto(BaseModel):
    codigo: str
    ean: str | None = None
    descricao: str
    ncm: str
    cest: str | None = None
    cfop: str
    unidade: str
    quantidade: Decimal
    valor_unitario: Decimal
    valor_produto: Decimal
    desconto: Decimal


class ICMS(BaseModel):
    origem: int | None = None
    cst_csosn: str | None = None
    base_calculo: Decimal | None = None
    aliquota: Decimal | None = None
    valor: Decimal | None = None
    base_calculo_st: Decimal | None = None
    aliquota_st: Decimal | None = None
    valor_st: Decimal | None = None


class PIS(BaseModel):
    cst: str | None = None
    base_calculo: Decimal | None = None
    aliquota: Decimal | None = None
    valor: Decimal | None = None


class COFINS(BaseModel):
    cst: str | None = None
    base_calculo: Decimal | None = None
    aliquota: Decimal | None = None
    valor: Decimal | None = None


class IPI(BaseModel):
    cst: str | None = None
    base_calculo: Decimal | None = None
    aliquota: Decimal | None = None
    valor: Decimal | None = None


class IBSCBS(BaseModel):
    cst: str | None = None
    c_class_trib: str | None = None


class Tributacao(BaseModel):
    icms: ICMS | None = None
    pis: PIS | None = None
    cofins: COFINS | None = None
    ipi: IPI | None = None
    ibs_cbs: IBSCBS | None = None


class ItemNFe(BaseModel):
    numero: int
    produto: Produto
    tributacao: Tributacao | None = None


class NFe(BaseModel):
    chave: str
    numero: int
    serie: int
    data_emissao: datetime
    emitente: Pessoa
    destinatario: Pessoa
    itens: list[ItemNFe]

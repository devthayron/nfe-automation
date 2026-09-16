from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class Person(BaseModel):
    cnpj: str
    x_nome: str
    uf: str


class Product(BaseModel):
    c_prod: str
    c_ean: str | None = None
    x_prod: str
    ncm: str
    cest: str | None = None
    cfop: str
    u_com: str
    q_com: Decimal
    v_un_com: Decimal
    v_prod: Decimal
    v_desc: Decimal | None = None


class ICMS(BaseModel):
    orig: int | None = None
    cst_csosn: str | None = None
    v_bc: Decimal | None = None
    p_icms: Decimal | None = None
    v_icms: Decimal | None = None
    v_bc_st: Decimal | None = None
    p_icms_st: Decimal | None = None
    v_icms_st: Decimal | None = None


class PIS(BaseModel):
    cst: str | None = None
    v_bc: Decimal | None = None
    p_pis: Decimal | None = None
    v_pis: Decimal | None = None


class COFINS(BaseModel):
    cst: str | None = None
    v_bc: Decimal | None = None
    p_cofins: Decimal | None = None
    v_cofins: Decimal | None = None


class IPI(BaseModel):
    cst: str | None = None
    v_bc: Decimal | None = None
    p_ipi: Decimal | None = None
    v_ipi: Decimal | None = None


class IBSCBS(BaseModel):
    cst: str | None = None
    c_class_trib: str | None = None


class Taxation(BaseModel):
    icms: ICMS | None = None
    pis: PIS | None = None
    cofins: COFINS | None = None
    ipi: IPI | None = None
    ibs_cbs: IBSCBS | None = None


class NFeItem(BaseModel):
    n_item: int
    product: Product
    taxation: Taxation | None = None


class NFe(BaseModel):
    ch_nfe: str
    n_nf: int
    serie: int
    dh_emi: datetime
    emit: Person
    dest: Person
    items: list[NFeItem]

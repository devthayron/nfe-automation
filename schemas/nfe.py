from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class Person(BaseModel):
    cnpj: str | None = None  # CNPJ ou CPF
    x_nome: str = ""
    uf: str | None = None


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


class NFeItem(BaseModel):
    n_item: int
    product: Product
    # Cópia fiel do <imposto> do XML. Ex.:
    # {"ICMS": {"grupo": "ICMS00", "CST": "00", "vICMS": "18.00"}, "PIS": {...}}
    # Os valores ficam como string para não perder precisão.
    impostos: dict[str, Any] = Field(default_factory=dict)


class NFe(BaseModel):
    ch_nfe: str
    n_nf: int
    serie: int
    dh_emi: datetime
    emit: Person
    dest: Person
    items: list[NFeItem]
    # Cópia fiel do <total> do XML (ICMSTot, ISSQNtot, retTrib, IBSCBSTot...).
    totais: dict[str, Any] = Field(default_factory=dict)

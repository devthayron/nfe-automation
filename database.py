import os
from datetime import datetime
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


class Base(DeclarativeBase):
    pass


class Pessoa(Base):
    __tablename__ = "pessoa"

    id: Mapped[int] = mapped_column(primary_key=True)
    cnpj: Mapped[str] = mapped_column(String, unique=True, index=True)
    nome: Mapped[str] = mapped_column(String)
    uf: Mapped[str | None] = mapped_column(String)


def _total_numeric(field):
    """Coluna gerada (numérica) lida de totais->ICMSTot."""
    return mapped_column(
        Numeric,
        Computed(f"(totais->'ICMSTot'->>'{field}')::numeric", persisted=True),
    )


class NFeModel(Base):
    __tablename__ = "nfe"

    id: Mapped[int] = mapped_column(primary_key=True)
    ch_nfe: Mapped[str] = mapped_column(String(44), unique=True)
    n_nf: Mapped[str] = mapped_column(String)
    serie: Mapped[str] = mapped_column(String)
    dh_emi: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    emit_id: Mapped[int | None] = mapped_column(ForeignKey("pessoa.id"))
    dest_id: Mapped[int | None] = mapped_column(ForeignKey("pessoa.id"))

    # Caminho relativo à raiz dos XMLs (usado para não reimportar o mesmo arquivo).
    xml_path: Mapped[str] = mapped_column(String, unique=True)

    # Marcador operacional baseado no sufixo _CANCELADA do nome do arquivo.
    # Não equivale, por si só, a uma consulta de situação na SEFAZ.
    cancelado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    # <total> do XML completo (ICMSTot, ISSQNtot, retTrib, IBSCBSTot...)
    totais: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Colunas geradas a partir de totais->ICMSTot.
    v_nf: Mapped[Decimal | None] = _total_numeric("vNF")
    v_prod: Mapped[Decimal | None] = _total_numeric("vProd")
    v_icms: Mapped[Decimal | None] = _total_numeric("vICMS")
    v_st: Mapped[Decimal | None] = _total_numeric("vST")
    v_ipi: Mapped[Decimal | None] = _total_numeric("vIPI")
    v_pis: Mapped[Decimal | None] = _total_numeric("vPIS")
    v_cofins: Mapped[Decimal | None] = _total_numeric("vCOFINS")

    emit: Mapped[Pessoa | None] = relationship(foreign_keys=[emit_id])
    dest: Mapped[Pessoa | None] = relationship(foreign_keys=[dest_id])

    items: Mapped[list["NFeItemModel"]] = relationship(
        back_populates="nfe",
        cascade="all, delete-orphan",
    )


def _json_text(tax, field):
    """Coluna gerada (texto) lida do JSONB de impostos."""
    return mapped_column(
        String,
        Computed(f"impostos->'{tax}'->>'{field}'", persisted=True),
    )


def _json_numeric(tax, field):
    """Coluna gerada (numérica) lida do JSONB de impostos."""
    return mapped_column(
        Numeric,
        Computed(f"(impostos->'{tax}'->>'{field}')::numeric", persisted=True),
    )


class NFeItemModel(Base):
    __tablename__ = "nfe_item"
    __table_args__ = (UniqueConstraint("nfe_id", "n_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nfe_id: Mapped[int] = mapped_column(ForeignKey("nfe.id"))
    n_item: Mapped[int]

    # Produto
    c_prod: Mapped[str] = mapped_column(String)
    c_ean: Mapped[str | None] = mapped_column(String)
    x_prod: Mapped[str] = mapped_column(String)
    ncm: Mapped[str | None] = mapped_column(String)
    cest: Mapped[str | None] = mapped_column(String)
    cfop: Mapped[str] = mapped_column(String)
    u_com: Mapped[str] = mapped_column(String)
    q_com: Mapped[Decimal] = mapped_column(Numeric)
    v_un_com: Mapped[Decimal] = mapped_column(Numeric)
    v_prod: Mapped[Decimal] = mapped_column(Numeric)
    v_desc: Mapped[Decimal | None] = mapped_column(Numeric)

    impostos: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    icms_cst_csosn: Mapped[str | None] = mapped_column(
        String,
        Computed(
            "coalesce(impostos->'ICMS'->>'CST', impostos->'ICMS'->>'CSOSN')",
            persisted=True,
        ),
    )
    ibscbs_cst: Mapped[str | None] = _json_text("IBSCBS", "CST")
    ibscbs_c_class_trib: Mapped[str | None] = _json_text("IBSCBS", "cClassTrib")

    v_icms: Mapped[Decimal | None] = _json_numeric("ICMS", "vICMS")
    v_icms_st: Mapped[Decimal | None] = _json_numeric("ICMS", "vICMSST")
    v_pis: Mapped[Decimal | None] = _json_numeric("PIS", "vPIS")
    v_cofins: Mapped[Decimal | None] = _json_numeric("COFINS", "vCOFINS")
    v_ipi: Mapped[Decimal | None] = _json_numeric("IPI", "vIPI")

    nfe: Mapped[NFeModel] = relationship(back_populates="items")


class NFeXML(Base):
    """XML original da NF-e armazenado em bytes e relacionado pelo ID interno."""

    __tablename__ = "nfe_xml"

    nfe_id: Mapped[int] = mapped_column(
        ForeignKey("nfe.id", ondelete="CASCADE"),
        primary_key=True,
    )
    xml: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


def create_db_engine():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não está definida no ambiente/.env")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine

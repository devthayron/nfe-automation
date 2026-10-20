# Run with: python -m scripts.save_nfes_db

import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from logger import setup_logging
from parser.nfe_parser import NFeParser

XML_ROOT = Path("/home/thayron/servidor_xml")
XML_DIR = XML_ROOT

DB_PATH = Path("nfes.db")
BATCH_SIZE = 500
CANCELED_SUFFIX = "_CANCELADA"

setup_logging()
logger = logging.getLogger(__name__)


class DuplicateNFeError(Exception):
    """Indica que a chave de acesso já está cadastrada."""


class DecimalText(TypeDecorator):
    """Armazena Decimal como texto para preservar sua precisão no SQLite."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else str(value)

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


def dec():
    return mapped_column(DecimalText, nullable=True)


def txt():
    return mapped_column(String, nullable=True)


class Base(DeclarativeBase):
    pass


class Pessoa(Base):
    __tablename__ = "pessoa"

    id: Mapped[int] = mapped_column(primary_key=True)
    cnpj: Mapped[str] = mapped_column(String, unique=True, index=True)
    nome: Mapped[str] = mapped_column(String)
    uf: Mapped[str | None] = txt()


class NFeModel(Base):
    __tablename__ = "nfe"

    id: Mapped[int] = mapped_column(primary_key=True)
    ch_nfe: Mapped[str] = mapped_column(String(44), unique=True, index=True)
    n_nf: Mapped[str] = mapped_column(String)
    serie: Mapped[str] = mapped_column(String)
    dh_emi: Mapped[datetime] = mapped_column(DateTime)

    emit_id: Mapped[int | None] = mapped_column(ForeignKey("pessoa.id"))
    dest_id: Mapped[int | None] = mapped_column(ForeignKey("pessoa.id"))

    # Caminho relativo à raiz XML_ROOT; o XML não é armazenado no banco.
    xml_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    emit: Mapped[Pessoa | None] = relationship(foreign_keys=[emit_id])
    dest: Mapped[Pessoa | None] = relationship(foreign_keys=[dest_id])

    items: Mapped[list["NFeItemModel"]] = relationship(
        back_populates="nfe",
        cascade="all, delete-orphan",
    )


class NFeItemModel(Base):
    __tablename__ = "nfe_item"
    __table_args__ = (UniqueConstraint("nfe_id", "n_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nfe_id: Mapped[int] = mapped_column(ForeignKey("nfe.id"), index=True)
    n_item: Mapped[int] = mapped_column(Integer)

    # Produto
    c_prod: Mapped[str] = mapped_column(String)
    c_ean: Mapped[str | None] = txt()
    x_prod: Mapped[str] = mapped_column(String)
    ncm: Mapped[str | None] = txt()
    cest: Mapped[str | None] = txt()
    cfop: Mapped[str] = mapped_column(String)
    u_com: Mapped[str] = mapped_column(String)
    q_com: Mapped[Decimal] = mapped_column(DecimalText)
    v_un_com: Mapped[Decimal] = mapped_column(DecimalText)
    v_prod: Mapped[Decimal] = mapped_column(DecimalText)
    v_desc: Mapped[Decimal | None] = dec()

    # ICMS
    icms_orig: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icms_cst: Mapped[str | None] = txt()
    icms_csosn: Mapped[str | None] = txt()
    icms_v_bc: Mapped[Decimal | None] = dec()
    icms_p_icms: Mapped[Decimal | None] = dec()
    icms_v_icms: Mapped[Decimal | None] = dec()
    icms_v_bc_st: Mapped[Decimal | None] = dec()
    icms_p_icms_st: Mapped[Decimal | None] = dec()
    icms_v_icms_st: Mapped[Decimal | None] = dec()

    # PIS
    pis_cst: Mapped[str | None] = txt()
    pis_v_bc: Mapped[Decimal | None] = dec()
    pis_p_pis: Mapped[Decimal | None] = dec()
    pis_v_pis: Mapped[Decimal | None] = dec()
    pis_q_bc_prod: Mapped[Decimal | None] = dec()
    pis_v_aliq_prod: Mapped[Decimal | None] = dec()

    # COFINS
    cofins_cst: Mapped[str | None] = txt()
    cofins_v_bc: Mapped[Decimal | None] = dec()
    cofins_p_cofins: Mapped[Decimal | None] = dec()
    cofins_v_cofins: Mapped[Decimal | None] = dec()
    cofins_q_bc_prod: Mapped[Decimal | None] = dec()
    cofins_v_aliq_prod: Mapped[Decimal | None] = dec()

    # IPI
    ipi_cst: Mapped[str | None] = txt()
    ipi_v_bc: Mapped[Decimal | None] = dec()
    ipi_p_ipi: Mapped[Decimal | None] = dec()
    ipi_v_ipi: Mapped[Decimal | None] = dec()
    ipi_q_unid: Mapped[Decimal | None] = dec()
    ipi_v_unid: Mapped[Decimal | None] = dec()

    # IBS/CBS
    ibscbs_cst: Mapped[str | None] = txt()
    ibscbs_c_class_trib: Mapped[str | None] = txt()

    nfe: Mapped[NFeModel] = relationship(back_populates="items")


def _g(obj, attr):
    return getattr(obj, attr, None) if obj is not None else None


def get_or_create_pessoa(session: Session, person):
    if person is None or not person.cnpj:
        return None

    pessoa = session.scalar(select(Pessoa).where(Pessoa.cnpj == person.cnpj))

    if pessoa is None:
        pessoa = Pessoa(
            cnpj=person.cnpj,
            nome=person.x_nome,
            uf=person.uf,
        )
        session.add(pessoa)
        session.flush()

    return pessoa


def build_item(item, nfe_id: int):
    p = item.product
    t = item.taxation

    icms = _g(t, "icms")
    pis = _g(t, "pis")
    cofins = _g(t, "cofins")
    ipi = _g(t, "ipi")
    ibs = _g(t, "ibs_cbs")

    return NFeItemModel(
        nfe_id=nfe_id,
        n_item=item.n_item,
        c_prod=p.c_prod,
        c_ean=p.c_ean,
        x_prod=p.x_prod,
        ncm=p.ncm,
        cest=p.cest,
        cfop=p.cfop,
        u_com=p.u_com,
        q_com=p.q_com,
        v_un_com=p.v_un_com,
        v_prod=p.v_prod,
        v_desc=p.v_desc,
        icms_orig=_g(icms, "orig"),
        icms_cst=_g(icms, "cst"),
        icms_csosn=_g(icms, "csosn"),
        icms_v_bc=_g(icms, "v_bc"),
        icms_p_icms=_g(icms, "p_icms"),
        icms_v_icms=_g(icms, "v_icms"),
        icms_v_bc_st=_g(icms, "v_bc_st"),
        icms_p_icms_st=_g(icms, "p_icms_st"),
        icms_v_icms_st=_g(icms, "v_icms_st"),
        pis_cst=_g(pis, "cst"),
        pis_v_bc=_g(pis, "v_bc"),
        pis_p_pis=_g(pis, "p_pis"),
        pis_v_pis=_g(pis, "v_pis"),
        pis_q_bc_prod=_g(pis, "q_bc_prod"),
        pis_v_aliq_prod=_g(pis, "v_aliq_prod"),
        cofins_cst=_g(cofins, "cst"),
        cofins_v_bc=_g(cofins, "v_bc"),
        cofins_p_cofins=_g(cofins, "p_cofins"),
        cofins_v_cofins=_g(cofins, "v_cofins"),
        cofins_q_bc_prod=_g(cofins, "q_bc_prod"),
        cofins_v_aliq_prod=_g(cofins, "v_aliq_prod"),
        ipi_cst=_g(ipi, "cst"),
        ipi_v_bc=_g(ipi, "v_bc"),
        ipi_p_ipi=_g(ipi, "p_ipi"),
        ipi_v_ipi=_g(ipi, "v_ipi"),
        ipi_q_unid=_g(ipi, "q_unid"),
        ipi_v_unid=_g(ipi, "v_unid"),
        ibscbs_cst=_g(ibs, "cst"),
        ibscbs_c_class_trib=_g(ibs, "c_class_trib"),
    )


def save_nfe(session: Session, nfe, xml_path: str):
    # Cabeçalho, pessoas e itens participam da mesma operação lógica.
    with session.begin_nested():
        emit = get_or_create_pessoa(session, nfe.emit)
        dest = get_or_create_pessoa(session, nfe.dest)

        stmt = (
            sqlite_insert(NFeModel)
            .values(
                ch_nfe=nfe.ch_nfe,
                n_nf=nfe.n_nf,
                serie=nfe.serie,
                dh_emi=nfe.dh_emi,
                emit_id=emit.id if emit else None,
                dest_id=dest.id if dest else None,
                xml_path=xml_path,
            )
            .on_conflict_do_nothing(index_elements=[NFeModel.ch_nfe])
            .returning(NFeModel.id)
        )

        nfe_id = session.scalar(stmt)

        if nfe_id is None:
            raise DuplicateNFeError(nfe.ch_nfe)

        session.add_all(build_item(item, nfe_id) for item in nfe.items)

        # Detecta erros dos itens ainda dentro do savepoint.
        session.flush()


def create_db_engine():
    engine = create_engine(f"sqlite:///{DB_PATH}")

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _):
        dbapi_conn.isolation_level = None
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    return engine


def iter_xml_files():
    """Percorre os XMLs sem armazenar todos os caminhos em uma lista."""
    for path in XML_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() == ".xml":
            yield path


def main():
    if not XML_DIR.is_dir():
        logger.error("Pasta não encontrada: %s", XML_DIR.resolve())
        return

    engine = create_db_engine()

    files_seen = 0
    saved = 0
    duplicates = 0
    failed = 0
    canceled = 0
    pending_files = 0

    print(f"Iniciando leitura de XMLs em: {XML_DIR.resolve()}")
    print(f"Banco SQLite: {DB_PATH.resolve()}")

    try:
        with Session(engine) as session:
            try:
                for path in iter_xml_files():
                    files_seen += 1
                    pending_files += 1

                    try:
                        if path.stem.upper().endswith(CANCELED_SUFFIX):
                            canceled += 1
                            continue

                        relative_path = path.relative_to(XML_ROOT).as_posix()

                        # 1. Verifica o caminho antes de abrir o XML.
                        existing_id = session.scalar(
                            select(NFeModel.id).where(
                                NFeModel.xml_path == relative_path
                            )
                        )

                        if existing_id is not None:
                            duplicates += 1
                            continue

                        # 2. Processa somente arquivos ainda não importados.
                        parser = NFeParser(str(path))
                        parser.read_nfe()
                        nfe = parser.extract_data()

                        if not nfe:
                            failed += 1
                            logger.warning(
                                "Não foi possível extrair: %s",
                                path,
                            )
                            continue

                        # 3. Verifica se a chave já existe no banco.
                        existing_key = session.scalar(
                            select(NFeModel.id).where(NFeModel.ch_nfe == nfe.ch_nfe)
                        )

                        if existing_key is not None:
                            duplicates += 1
                            continue

                        try:
                            save_nfe(session, nfe, relative_path)
                        except DuplicateNFeError:
                            # A restrição UNIQUE protege contra duplicatas.
                            duplicates += 1
                        else:
                            saved += 1

                    except Exception:
                        failed += 1
                        logger.exception(
                            "Falha ao processar %s",
                            path,
                        )

                    finally:
                        if pending_files >= BATCH_SIZE:
                            try:
                                session.commit()
                            except Exception:
                                session.rollback()
                                logger.exception("Falha ao confirmar o lote no banco.")
                                raise

                            pending_files = 0

                            logger.info(
                                "Arquivos lidos: %s | Salvas: %s | "
                                "Duplicadas: %s | Canceladas: %s | "
                                "Falhas: %s",
                                files_seen,
                                saved,
                                duplicates,
                                canceled,
                                failed,
                            )

                # Confirma o último lote, mesmo que incompleto.
                session.commit()

            except KeyboardInterrupt:
                logger.warning(
                    "Interrupção solicitada. Tentando confirmar "
                    "as alterações pendentes..."
                )

                try:
                    session.commit()
                    logger.info("Lote pendente confirmado.")
                except Exception:
                    session.rollback()
                    logger.exception("Não foi possível confirmar o lote pendente.")

    finally:
        engine.dispose()

    print(
        f"\nConcluído: {files_seen} arquivo(s) XML percorrido(s).\n"
        f"NF-e salva(s) nesta execução: {saved}\n"
        f"Duplicadas: {duplicates}\n"
        f"Canceladas ignoradas: {canceled}\n"
        f"Falhas: {failed}\n"
        f"Banco: {DB_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()

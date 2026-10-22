# Run with: python -m scripts.save_nfes_db

import logging
import os
import re
import signal
from concurrent.futures import ProcessPoolExecutor
from itertools import islice
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from database import NFeItemModel, NFeModel, NFeXML, Pessoa, create_db_engine
from logger import setup_logging
from parser.nfe_parser import NFeParser

XML_ROOT = Path("/home/thayron/servidor_xml")
BATCH_SIZE = 300  # arquivos por lote (e por commit)
CANCELED_SUFFIX = "_CANCELADA"

# Só estes anos são importados.
ANOS = {2025, 2026}

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ leitura


def iter_xml_files():
    """
    Percorre os XMLs sem armazenar todos os caminhos em uma lista.
    Pastas nomeadas com um ano (4 dígitos) fora de ANOS nem são abertas.
    """
    anos = {str(ano) for ano in ANOS}

    for root, dirs, files in os.walk(XML_ROOT):
        dirs[:] = [d for d in dirs if not (re.fullmatch(r"\d{4}", d) and d not in anos)]

        for name in files:
            if name.lower().endswith(".xml"):
                yield Path(root) / name


def _ignore_sigint():
    """
    Ctrl+C vai para o grupo inteiro de processos. Os de leitura o ignoram:
    quem trata a interrupção é o processo principal.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def batched(iterable, size):
    iterator = iter(iterable)
    while batch := list(islice(iterator, size)):
        yield batch


def parse_file(path_str):
    """
    Roda nos processos filhos.
    Retorna (caminho, NFe | None, bytes do XML | None, erro | None).
    """
    try:
        raw = Path(path_str).read_bytes()

        parser = NFeParser(path_str, raw=raw)
        parser.read_nfe()
        nfe = parser.extract_data()

        if nfe is None:
            return path_str, None, None, "Falha ao extrair a NF-e"

        return path_str, nfe, raw, None

    except Exception as exc:
        return path_str, None, None, f"{type(exc).__name__}: {exc}"


# ------------------------------------------------------------------ gravação


def save_batch(session, entries):
    """
    Grava várias NF-es de uma vez. `entries` = [(nfe, xml_path, xml)].
    Retorna quantas NF-es foram realmente inseridas.
    """
    # 1. Pessoas (upsert)
    pessoas = {}
    for nfe, _, _ in entries:
        for person in (nfe.emit, nfe.dest):
            if person.cnpj:
                pessoas.setdefault(
                    person.cnpj,
                    {"cnpj": person.cnpj, "nome": person.x_nome, "uf": person.uf},
                )

    pessoa_ids = {}
    if pessoas:
        session.execute(
            pg_insert(Pessoa)
            .values(list(pessoas.values()))
            .on_conflict_do_nothing(index_elements=[Pessoa.cnpj])
        )
        rows = session.execute(
            select(Pessoa.cnpj, Pessoa.id).where(Pessoa.cnpj.in_(list(pessoas)))
        )
        pessoa_ids = {cnpj: id_ for cnpj, id_ in rows}

    # 2. Cabeçalhos. O RETURNING só devolve o que foi inserido de fato.
    headers = [
        {
            "ch_nfe": nfe.ch_nfe,
            "n_nf": str(nfe.n_nf),
            "serie": str(nfe.serie),
            "dh_emi": nfe.dh_emi,
            "emit_id": pessoa_ids.get(nfe.emit.cnpj),
            "dest_id": pessoa_ids.get(nfe.dest.cnpj),
            "xml_path": xml_path,
            "totais": nfe.totais,
        }
        for nfe, xml_path, _ in entries
    ]

    stmt = (
        pg_insert(NFeModel)
        .values(headers)
        .on_conflict_do_nothing(index_elements=[NFeModel.ch_nfe])
        .returning(NFeModel.id, NFeModel.ch_nfe)
    )
    inserted = {ch_nfe: id_ for id_, ch_nfe in session.execute(stmt)}

    # 3. Itens, somente das NF-es inseridas agora.
    items = []
    xmls = []
    for nfe, _, xml in entries:
        nfe_id = inserted.get(nfe.ch_nfe)
        if nfe_id is None:
            continue

        xmls.append({"nfe_id": nfe_id, "xml": xml})

        for item in nfe.items:
            p = item.product
            items.append(
                {
                    "nfe_id": nfe_id,
                    "n_item": item.n_item,
                    "c_prod": p.c_prod,
                    "c_ean": p.c_ean,
                    "x_prod": p.x_prod,
                    "ncm": p.ncm,
                    "cest": p.cest,
                    "cfop": p.cfop,
                    "u_com": p.u_com,
                    "q_com": p.q_com,
                    "v_un_com": p.v_un_com,
                    "v_prod": p.v_prod,
                    "v_desc": p.v_desc,
                    "impostos": item.impostos,
                }
            )

    if items:
        session.execute(insert(NFeItemModel), items)

    if xmls:
        session.execute(insert(NFeXML), xmls)

    return len(inserted)


def persist(session, entries):
    """
    Grava o lote e confirma. Se o lote falhar, tenta uma NF-e por vez
    para que um único XML problemático não derrube as demais.
    Retorna (salvas, falhas).
    """
    if not entries:
        return 0, 0

    try:
        saved = save_batch(session, entries)
        session.commit()
        return saved, 0
    except Exception:
        session.rollback()
        logger.warning("Lote falhou; gravando uma NF-e por vez.", exc_info=True)

    saved = failed = 0
    for entry in entries:
        try:
            saved += save_batch(session, [entry])
            session.commit()
        except Exception:
            session.rollback()
            failed += 1
            logger.exception("Falha ao gravar %s", entry[1])

    return saved, failed


# ---------------------------------------------------------------------- main


def main():
    setup_logging()

    if not XML_ROOT.is_dir():
        logger.error("Pasta não encontrada: %s", XML_ROOT.resolve())
        return

    engine = create_db_engine()
    workers = max(1, (os.cpu_count() or 2) - 1)

    files_seen = saved = duplicates = failed = canceled = skipped = outside = 0

    print(f"Lendo XMLs em: {XML_ROOT.resolve()}")
    print(f"Processos de leitura: {workers} | Lote: {BATCH_SIZE} arquivos")

    try:
        with (
            Session(engine) as session,
            ProcessPoolExecutor(workers, initializer=_ignore_sigint) as pool,
        ):
            for batch in batched(iter_xml_files(), BATCH_SIZE):
                files_seen += len(batch)

                candidates = []
                for path in batch:
                    if path.stem.upper().endswith(CANCELED_SUFFIX):
                        canceled += 1
                    else:
                        candidates.append(path)

                relative = {
                    str(p): p.relative_to(XML_ROOT).as_posix() for p in candidates
                }

                # Pula arquivos já importados (consulta só os do lote).
                known = set(
                    session.scalars(
                        select(NFeModel.xml_path).where(
                            NFeModel.xml_path.in_(list(relative.values()))
                        )
                    )
                )
                session.rollback()  # encerra a transação de leitura

                todo = [p for p, rel in relative.items() if rel not in known]
                skipped += len(relative) - len(todo)

                unique = {}
                for path_str, nfe, xml, error in pool.map(
                    parse_file, todo, chunksize=8
                ):
                    if nfe is None:
                        failed += 1
                        logger.warning("Falha ao ler %s: %s", path_str, error)
                    elif nfe.dh_emi.year not in ANOS:
                        outside += 1
                    elif nfe.ch_nfe in unique:
                        duplicates += 1
                    else:
                        unique[nfe.ch_nfe] = (nfe, relative[path_str], xml)

                entries = list(unique.values())
                batch_saved, batch_failed = persist(session, entries)

                saved += batch_saved
                failed += batch_failed
                duplicates += len(entries) - batch_saved - batch_failed

                logger.info(
                    "Lidos: %s | Salvas: %s | Já importados: %s | "
                    "Duplicadas: %s | Canceladas: %s | Falhas: %s",
                    files_seen,
                    saved,
                    skipped,
                    duplicates,
                    canceled,
                    failed,
                )

    except KeyboardInterrupt:
        logger.warning("Interrompido. Os lotes anteriores já foram confirmados.")

    finally:
        engine.dispose()

    print(
        f"\nArquivos percorridos: {files_seen}\n"
        f"NF-e salvas: {saved}\n"
        f"Já importadas (puladas): {skipped}\n"
        f"Duplicadas: {duplicates}\n"
        f"Canceladas ignoradas: {canceled}\n"
        f"Emitidas fora de {min(ANOS)}-{max(ANOS)}: {outside}\n"
        f"Falhas: {failed}"
    )


if __name__ == "__main__":
    main()

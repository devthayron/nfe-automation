# Run with: python -m scripts.save_nfes_db

import logging
import os
import re
import signal
from concurrent.futures import ProcessPoolExecutor
from itertools import islice
from pathlib import Path

from sqlalchemy import insert, select, update
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

# Log separado contendo exclusivamente os casos em que a chave já existe no banco.
EXISTING_KEYS_LOG = Path("logs/chaves_ja_existentes.log")
existing_keys_logger = logging.getLogger("existing_nfe_keys")
existing_keys_logger.setLevel(logging.INFO)
existing_keys_logger.propagate = False

# Pares encontrados na mesma pasta, por exemplo:
# 3526...1234.xml <-> 3526...1234_CANCELADA.xml
# Só são registrados quando o nome-base é uma chave de acesso de 44 dígitos.
PAIRED_NORMAL_TO_CANCELLED: dict[Path, Path] = {}
PAIRED_CANCELLED_TO_NORMAL: dict[Path, Path] = {}


def is_canceled_path(path: Path) -> bool:
    """Considera cancelada a NF-e cujo nome termina em _CANCELADA."""
    return path.stem.upper().endswith(CANCELED_SUFFIX)


def filename_access_key(path: Path) -> str | None:
    """Retorna a chave de 44 dígitos do nome do arquivo, se houver."""
    stem = path.stem
    if is_canceled_path(path):
        stem = stem[: -len(CANCELED_SUFFIX)]
    return stem if re.fullmatch(r"\d{44}", stem) else None


def _register_pairs(root: Path, xml_names: list[str]) -> None:
    """Registra pares normal/cancelado presentes na mesma pasta."""
    names_by_casefold = {name.casefold(): name for name in xml_names}

    for name in xml_names:
        cancelled_path = root / name
        if not is_canceled_path(cancelled_path):
            continue

        key_from_name = filename_access_key(cancelled_path)
        if key_from_name is None:
            continue

        normal_name = (
            f"{cancelled_path.stem[: -len(CANCELED_SUFFIX)]}{cancelled_path.suffix}"
        )
        actual_normal_name = names_by_casefold.get(normal_name.casefold())
        if actual_normal_name is None:
            continue

        normal_path = root / actual_normal_name
        PAIRED_NORMAL_TO_CANCELLED[normal_path] = cancelled_path
        PAIRED_CANCELLED_TO_NORMAL[cancelled_path] = normal_path


def are_cancellation_pair(path_a: Path, path_b: Path) -> bool:
    """True se os dois caminhos forem o par normal/cancelado identificado."""
    return (
        PAIRED_NORMAL_TO_CANCELLED.get(path_a) == path_b
        or PAIRED_NORMAL_TO_CANCELLED.get(path_b) == path_a
    )


def iter_xml_files():
    """
    Percorre os XMLs sem armazenar todos os caminhos.
    Registra pares normal/_CANCELADA na mesma pasta e entrega os cancelados
    primeiro, para que possam ser processados antes do arquivo normal pareado.
    """
    PAIRED_NORMAL_TO_CANCELLED.clear()
    PAIRED_CANCELLED_TO_NORMAL.clear()
    years = {str(year) for year in ANOS}

    for root_str, dirs, files in os.walk(XML_ROOT):
        dirs[:] = [
            directory
            for directory in dirs
            if not (re.fullmatch(r"\d{4}", directory) and directory not in years)
        ]

        root = Path(root_str)
        xml_names = [name for name in files if name.lower().endswith(".xml")]
        _register_pairs(root, xml_names)

        # Os cancelados vêm antes dos normais dentro da mesma pasta. Se o
        # cancelado for inválido, ele não será marcado como processado e o
        # arquivo normal continuará elegível para importação.
        xml_names.sort(
            key=lambda name: (not is_canceled_path(Path(name)), name.casefold())
        )
        for name in xml_names:
            yield root / name


def _ignore_sigint():
    """Só o processo principal trata Ctrl+C."""
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


def save_batch(session, entries):
    """
    Grava entries = [(nfe, xml_path, xml_bytes, cancelado)].

    Consulta as chaves existentes antes de inserir. Notas que já existem são
    atualizadas (situação/caminho) sem tentar inserir cabeçalho, itens ou XML
    novamente. Retorna (NF-es inseridas, entradas cuja chave já existia).
    """
    if not entries:
        return 0, 0, []

    keys = {nfe.ch_nfe for nfe, _, _, _ in entries}
    existing_rows = session.execute(
        select(NFeModel.ch_nfe, NFeModel.xml_path, NFeModel.cancelado).where(
            NFeModel.ch_nfe.in_(list(keys))
        )
    ).all()
    existing_by_key = {
        ch_nfe: (xml_path, cancelado) for ch_nfe, xml_path, cancelado in existing_rows
    }

    # Guarda detalhes apenas das entradas cuja chave já existe no banco.
    existing_details = []
    for nfe, xml_path, _, cancelado in entries:
        existing = existing_by_key.get(nfe.ch_nfe)
        if existing is not None:
            old_path, old_cancelado = existing
            existing_details.append(
                {
                    "ch_nfe": nfe.ch_nfe,
                    "arquivo_lido": xml_path,
                    "arquivo_no_banco": old_path,
                    "cancelado_arquivo": cancelado,
                    "cancelado_banco": old_cancelado,
                }
            )

    # Atualiza notas já existentes sem tentar inseri-las novamente.
    for nfe, xml_path, _, cancelado in entries:
        existing = existing_by_key.get(nfe.ch_nfe)
        if existing is None:
            continue

        old_path, old_cancelado = existing
        changes = {}

        if cancelado and not old_cancelado:
            changes["cancelado"] = True

        # Quando o arquivo cancelado foi identificado, ele vira o xml_path
        # preferido, mesmo se o arquivo normal ainda estiver presente.
        # Para arquivos normais, só troca se o caminho antigo não existir.
        if old_path != xml_path:
            if cancelado or not (XML_ROOT / old_path).exists():
                changes["xml_path"] = xml_path

        if changes:
            session.execute(
                update(NFeModel).where(NFeModel.ch_nfe == nfe.ch_nfe).values(**changes)
            )

    # Só as chaves que ainda não existem vão para o INSERT.
    new_entries = [entry for entry in entries if entry[0].ch_nfe not in existing_by_key]

    if not new_entries:
        return 0, len(entries), existing_details

    # 1. Pessoas (upsert sem sobrescrever cadastro existente), apenas para NF-es novas.
    pessoas = {}
    for nfe, _, _, _ in new_entries:
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

    # 2. Cabeçalhos das NF-es novas.
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
            "cancelado": cancelado,
        }
        for nfe, xml_path, _, cancelado in new_entries
    ]

    stmt = (
        pg_insert(NFeModel)
        .values(headers)
        .on_conflict_do_nothing(index_elements=[NFeModel.ch_nfe])
        .returning(NFeModel.id, NFeModel.ch_nfe)
    )
    inserted = {ch_nfe: id_ for id_, ch_nfe in session.execute(stmt)}

    # 3. Itens e XML original apenas para NF-es efetivamente inseridas agora.
    items = []
    xmls = []
    for nfe, _, xml, _ in new_entries:
        nfe_id = inserted.get(nfe.ch_nfe)
        if nfe_id is None:
            continue

        xmls.append({"nfe_id": nfe_id, "xml": xml})

        for item in nfe.items:
            product = item.product
            items.append(
                {
                    "nfe_id": nfe_id,
                    "n_item": item.n_item,
                    "c_prod": product.c_prod,
                    "c_ean": product.c_ean,
                    "x_prod": product.x_prod,
                    "ncm": product.ncm,
                    "cest": product.cest,
                    "cfop": product.cfop,
                    "u_com": product.u_com,
                    "q_com": product.q_com,
                    "v_un_com": product.v_un_com,
                    "v_prod": product.v_prod,
                    "v_desc": product.v_desc,
                    "impostos": item.impostos,
                }
            )

    if items:
        session.execute(insert(NFeItemModel), items)

    if xmls:
        session.execute(insert(NFeXML), xmls)

    # Entradas não inseridas (por conflito concorrente) também são reportadas
    # como chaves já existentes, não como duplicatas do lote.
    return len(inserted), len(entries) - len(inserted), existing_details


def persist(session, entries):
    """Grava o lote; se falhar, tenta cada NF-e individualmente."""
    if not entries:
        return 0, 0, 0, set(), []

    try:
        saved, already_existing, existing_details = save_batch(session, entries)
        session.commit()
        return saved, already_existing, 0, set(), existing_details
    except Exception:
        session.rollback()
        logger.warning("Lote falhou; gravando uma NF-e por vez.", exc_info=True)

    saved = already_existing = failed = 0
    failed_keys = set()
    existing_details = []
    for entry in entries:
        try:
            inserted_count, existing_count, details = save_batch(session, [entry])
            session.commit()
            saved += inserted_count
            already_existing += existing_count
            existing_details.extend(details)
        except Exception:
            session.rollback()
            failed += 1
            failed_keys.add(entry[0].ch_nfe)
            logger.exception("Falha ao gravar %s", entry[1])

    return saved, already_existing, failed, failed_keys, existing_details


def main():
    setup_logging()

    EXISTING_KEYS_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == EXISTING_KEYS_LOG.resolve()
        for handler in existing_keys_logger.handlers
    ):
        file_handler = logging.FileHandler(EXISTING_KEYS_LOG, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%d-%m-%Y %H:%M:%S",
            )
        )
        existing_keys_logger.addHandler(file_handler)

    if not XML_ROOT.is_dir():
        logger.error("Pasta não encontrada: %s", XML_ROOT.resolve())
        return

    engine = create_db_engine()
    workers = max(1, (os.cpu_count() or 2) - 1)

    files_seen = saved = duplicates = failed = canceled = skipped = outside = 0
    already_existing = paired_skipped = paired_collapsed = 0
    handled_canceled_paths: set[Path] = set()

    print(f"Lendo XMLs em: {XML_ROOT.resolve()}")
    print(f"Processos de leitura: {workers} | Lote: {BATCH_SIZE} arquivos")

    try:
        with (
            Session(engine) as session,
            ProcessPoolExecutor(workers, initializer=_ignore_sigint) as pool,
        ):
            for batch in batched(iter_xml_files(), BATCH_SIZE):
                files_seen += len(batch)

                relative = {
                    str(path): path.relative_to(XML_ROOT).as_posix() for path in batch
                }
                canceled_by_path = {str(path): is_canceled_path(path) for path in batch}
                canceled += sum(canceled_by_path.values())

                # Consulta quais caminhos já estão registrados no banco.
                rows = session.execute(
                    select(NFeModel.ch_nfe, NFeModel.xml_path).where(
                        NFeModel.xml_path.in_(list(relative.values()))
                    )
                ).all()
                known = {xml_path for _, xml_path in rows}
                known_key_by_path = {xml_path: ch_nfe for ch_nfe, xml_path in rows}

                # Se o caminho _CANCELADA já está registrado, a nota já foi
                # processada por esse arquivo; confirma o status e considera o
                # par normal coberto, para não processá-lo em outra execução.
                known_canceled_paths = [
                    path
                    for path in batch
                    if canceled_by_path[str(path)]
                    and relative[str(path)] in known
                    and known_key_by_path.get(relative[str(path)])
                    == filename_access_key(path)
                ]
                if known_canceled_paths:
                    session.execute(
                        update(NFeModel)
                        .where(
                            NFeModel.xml_path.in_(
                                [relative[str(path)] for path in known_canceled_paths]
                            ),
                            NFeModel.cancelado.is_(False),
                        )
                        .values(cancelado=True)
                    )
                    session.commit()
                    handled_canceled_paths.update(known_canceled_paths)
                else:
                    session.rollback()

                # Caminhos já importados são pulados. O arquivo normal de um par
                # só é ignorado quando o correspondente _CANCELADA foi identificado
                # e processado com sucesso (ou já estava registrado no banco).
                todo = []
                for path in batch:
                    rel = relative[str(path)]
                    if rel in known:
                        skipped += 1
                        continue

                    canceled_sibling = PAIRED_NORMAL_TO_CANCELLED.get(path)
                    if canceled_sibling in handled_canceled_paths:
                        paired_skipped += 1
                        continue

                    todo.append(path)

                unique = {}
                for path_str, nfe, xml, error in pool.map(
                    parse_file, [str(path) for path in todo], chunksize=8
                ):
                    path = Path(path_str)
                    cancelado = is_canceled_path(path)

                    if nfe is None:
                        failed += 1
                        logger.warning("Falha ao ler %s: %s", path_str, error)
                    elif nfe.dh_emi.year not in ANOS:
                        outside += 1
                    elif cancelado and filename_access_key(path) != nfe.ch_nfe:
                        # Nome de cancelamento não corresponde à chave extraída;
                        # não usamos esse arquivo para suprimir o arquivo normal.
                        logger.warning(
                            "Chave do nome difere da chave do XML cancelado: %s | %s",
                            path_str,
                            nfe.ch_nfe,
                        )
                        unique.setdefault(
                            nfe.ch_nfe,
                            (nfe, relative[path_str], xml, False),
                        )
                    elif nfe.ch_nfe in unique:
                        old_nfe, old_path, old_xml, old_cancelado = unique[nfe.ch_nfe]
                        old_abs_path = XML_ROOT / old_path
                        paired_files = are_cancellation_pair(path, old_abs_path)

                        if paired_files:
                            paired_collapsed += 1
                            # Para o par confirmado pela mesma chave, mantém o
                            # arquivo cancelado como caminho e bytes selecionados.
                            if cancelado:
                                unique[nfe.ch_nfe] = (
                                    nfe,
                                    relative[path_str],
                                    xml,
                                    True,
                                )
                            elif not old_cancelado:
                                unique[nfe.ch_nfe] = (
                                    old_nfe,
                                    old_path,
                                    old_xml,
                                    False,
                                )
                        else:
                            duplicates += 1
                            # Em duplicatas não pareadas, prefere a entrada
                            # identificada como cancelada, se houver.
                            if cancelado:
                                unique[nfe.ch_nfe] = (
                                    nfe,
                                    relative[path_str],
                                    xml,
                                    True,
                                )
                            elif not old_cancelado:
                                unique[nfe.ch_nfe] = (
                                    old_nfe,
                                    old_path,
                                    old_xml,
                                    old_cancelado or cancelado,
                                )
                    else:
                        unique[nfe.ch_nfe] = (
                            nfe,
                            relative[path_str],
                            xml,
                            cancelado,
                        )

                entries = list(unique.values())
                (
                    batch_saved,
                    batch_existing,
                    batch_failed,
                    failed_keys,
                    batch_existing_details,
                ) = persist(session, entries)

                saved += batch_saved
                already_existing += batch_existing
                failed += batch_failed

                # Detalha somente as chaves que já existiam no banco.
                for case in batch_existing_details:
                    existing_keys_logger.info(
                        "CHAVE JÁ EXISTENTE | chave=%s | arquivo_lido=%s | "
                        "arquivo_no_banco=%s | cancelado_arquivo=%s | "
                        "cancelado_banco=%s",
                        case["ch_nfe"],
                        case["arquivo_lido"],
                        case["arquivo_no_banco"],
                        case["cancelado_arquivo"],
                        case["cancelado_banco"],
                    )

                # Só marca o par como tratado depois que a NF-e correspondente
                # foi processada e a transação foi confirmada com sucesso.
                for nfe, xml_path, _, cancelado in entries:
                    absolute_path = XML_ROOT / xml_path
                    if (
                        cancelado
                        and is_canceled_path(absolute_path)
                        and filename_access_key(absolute_path) == nfe.ch_nfe
                        and nfe.ch_nfe not in failed_keys
                    ):
                        handled_canceled_paths.add(absolute_path)

                logger.info(
                    "Lidos: %s | Salvas: %s | Já importados: %s | "
                    "Duplicadas: %s | Cancelados: %s | Falhas: %s",
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
        f"\nLidos: {files_seen} | Salvas: {saved} | "
        f"Já importados: {skipped} | Duplicadas: {duplicates} | "
        f"Cancelados: {canceled} | Falhas: {failed}"
    )


if __name__ == "__main__":
    main()

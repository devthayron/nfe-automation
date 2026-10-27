import logging
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database import NFeModel, create_db_engine
from importer.config import ANOS, BATCH_SIZE, XML_ROOT
from importer.files import (
    PAIRED_NORMAL_TO_CANCELLED,
    are_cancellation_pair,
    batched,
    filename_access_key,
    is_canceled_path,
    iter_xml_files,
)
from importer.parsing import ignore_sigint, parse_file
from importer.persistence import persist
from logger import setup_logging

logger = logging.getLogger(__name__)

# Log separado contendo exclusivamente os casos em que a chave já existe no banco.
EXISTING_KEYS_LOG = Path("logs/chaves_ja_existentes.log")
existing_keys_logger = logging.getLogger("existing_nfe_keys")
existing_keys_logger.setLevel(logging.INFO)
existing_keys_logger.propagate = False


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

    if XML_ROOT is None:
        logger.error("XML_ROOT não está definida no ambiente/.env")
        return

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
            ProcessPoolExecutor(workers, initializer=ignore_sigint) as pool,
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

import logging

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import NFeItemModel, NFeModel, NFeXML, Pessoa
from importer.config import XML_ROOT

logger = logging.getLogger(__name__)


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

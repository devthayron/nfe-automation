from sqlalchemy import text


def get_xml(engine, ch_nfe: str) -> bytes | None:
    """Devolve os bytes originais do XML de uma NF-e, ou None se não existir."""
    with engine.connect() as conn:
        data = conn.execute(
            text(
                "SELECT x.xml FROM nfe_xml x "
                "JOIN nfe n ON n.id = x.nfe_id WHERE n.ch_nfe = :ch"
            ),
            {"ch": ch_nfe},
        ).scalar()

    return bytes(data) if data is not None else None

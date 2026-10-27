from sqlalchemy import text


def get_xml(engine, ch_nfe: str) -> bytes | None:
    """Devolve os bytes originais do XML de uma NF-e, ou None se não existir."""
    with engine.connect() as conn:
        data = conn.execute(
            text("SELECT xml FROM nfe_xml WHERE ch_nfe = :ch"),
            {"ch": ch_nfe},
        ).scalar()

    return bytes(data) if data is not None else None

from .xml_utils import children, local

# Impostos em que o único filho "com conteúdo" é a variante
# (ICMS00, PISAliq, IPITrib...). Para os demais, o XML é copiado como está.
GROUPED_TAXES = {"ICMS", "PIS", "COFINS", "IPI"}


def to_obj(el):
    """Converte um elemento em dict/str. Tags repetidas viram lista."""
    kids = children(el)

    if not kids:
        return (el.text or "").strip() or None

    out = {}
    for kid in kids:
        name = local(kid)
        value = to_obj(kid)

        if name in out:
            if not isinstance(out[name], list):
                out[name] = [out[name]]
            out[name].append(value)
        else:
            out[name] = value

    return out


def extract_impostos(imposto):
    """
    Converte <imposto> em dict.

    <ICMS><ICMS00><CST>00</CST>...</ICMS00></ICMS>
      -> {"ICMS": {"grupo": "ICMS00", "CST": "00", ...}}
    """
    result = {}

    for tax in children(imposto):
        name = local(tax)
        kids = children(tax)
        groups = [k for k in kids if children(k)]

        if name in GROUPED_TAXES and len(groups) == 1:
            group = groups[0]
            obj = {"grupo": local(group)}

            # Campos fora da variante (ex.: cEnq no IPI)
            for kid in kids:
                if kid is not group:
                    obj[local(kid)] = to_obj(kid)

            obj.update(to_obj(group))
        else:
            obj = to_obj(tax)

        result[name] = obj

    return result

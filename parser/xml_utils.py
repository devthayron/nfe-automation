import re
from pathlib import Path

from lxml import etree

PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    recover=False,
    huge_tree=True,
)

_ENCODINGS = ("utf-8", "cp1252", "iso-8859-1")


def _fix_declaration(text):
    """
    Ajusta a declaração <?xml ...?>: remove 'standalone' inválido e
    troca o encoding para UTF-8 (o texto já foi decodificado).
    """
    text = text.lstrip("\ufeff \t\r\n")
    match = re.match(r"<\?xml[^>]*\?>", text)
    if not match:
        return text

    decl = match.group(0)
    decl = re.sub(r"""\s+standalone\s*=\s*(["']).*?\1""", "", decl)
    decl = re.sub(
        r"""(encoding\s*=\s*)(["']).*?\2""",
        r'\1"UTF-8"',
        decl,
        flags=re.IGNORECASE,
    )
    return decl + text[match.end() :]


def parse_xml(path):
    """Lê o arquivo e devolve a raiz do XML (veja parse_xml_bytes)."""
    return parse_xml_bytes(Path(path).read_bytes())


def parse_xml_bytes(raw):
    """
    Devolve a raiz do XML a partir dos bytes. Tenta os bytes originais primeiro;
    se falhar, corrige encoding/standalone somente em memória.
    """
    try:
        return etree.fromstring(raw, PARSER)
    except etree.XMLSyntaxError as original_error:
        last_error = original_error

    for encoding in _ENCODINGS:
        try:
            text = _fix_declaration(raw.decode(encoding))
            return etree.fromstring(text.encode("utf-8"), PARSER)
        except (UnicodeDecodeError, etree.XMLSyntaxError) as exc:
            last_error = exc

    raise last_error


def local(el):
    """Nome da tag sem namespace."""
    return etree.QName(el).localname


def children(el, name=None):
    """Filhos diretos (ignora comentários), opcionalmente filtrando por nome."""
    if el is None:
        return []
    return [
        c for c in el if isinstance(c.tag, str) and (name is None or local(c) == name)
    ]


def child(el, name):
    found = children(el, name)
    return found[0] if found else None


def find_path(el, *names):
    """Desce por uma sequência de nomes. Devolve None se algum faltar."""
    for name in names:
        el = child(el, name)
        if el is None:
            return None
    return el


def find_first(root, name):
    """Primeiro descendente com o nome informado, em qualquer nível."""
    for el in root.iter():
        if isinstance(el.tag, str) and local(el) == name:
            return el
    return None


def text(el, *names):
    """Texto de um elemento (ou de um caminho). None se vazio/inexistente."""
    target = find_path(el, *names) if names else el
    if target is None or target.text is None:
        return None
    return target.text.strip() or None

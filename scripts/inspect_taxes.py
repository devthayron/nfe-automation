import re
from pathlib import Path
from time import monotonic

from lxml import etree
from nfelib.nfe.bindings.v4_0.proc_nfe_v4_00 import NfeProc
from tqdm import tqdm

XML_DIR = Path("/home/thayron/servidor_xml")
OUTPUT_FILE = Path(__file__).resolve().parent / "resultado_inspecao.txt"

TAX_TYPES = ("ICMS", "PIS", "COFINS", "IPI", "IBSCBS")
CHECKPOINT_INTERVAL = 1000
MAX_ERRORS_IN_REPORT = 100


# Run with: python -m scripts.inspect_taxes


def inspect_xml_nfelib(path):
    """Extrai grupos e campos usando nfelib."""
    nfe_proc = NfeProc.from_path(str(path))
    inf_nfe = nfe_proc.NFe.infNFe

    groups = {}

    for item in inf_nfe.det:
        tax = item.imposto

        for tax_name in TAX_TYPES:
            structure = getattr(tax, tax_name, None)

            if structure is None:
                continue

            for group in vars(structure).values():
                if group is None or not hasattr(group, "__dict__"):
                    continue

                group_name = type(group).__name__
                key = (tax_name, group_name)
                groups.setdefault(key, set())

                for field, value in vars(group).items():
                    if value is not None:
                        groups[key].add(field)

    return groups


def inspect_xml_lxml(path):
    """
    Lê os bytes originais e tenta corrigir problemas de codificação
    somente em memória, sem modificar o arquivo original.
    """
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        recover=False,
    )

    raw = path.read_bytes()

    try:
        root = etree.fromstring(raw, parser)

    except etree.XMLSyntaxError as original_error:
        error_message = str(original_error).lower()

        # Só tenta outra codificação quando o erro indica
        # um provável problema de encoding.
        encoding_error = any(
            term in error_message
            for term in (
                "encoding",
                "utf-8",
                "invalid bytes",
                "unicode",
            )
        )

        if not encoding_error:
            raise

        root = None
        last_error = original_error

        for encoding in ("cp1252", "iso-8859-1"):
            try:
                text = raw.decode(encoding)

                # Como o conteúdo será convertido para UTF-8,
                # atualiza a declaração XML, se ela existir.
                text = re.sub(
                    r"""(<\?xml\s+[^?]*?encoding\s*=\s*)
                        (["'])[^"']+\2""",
                    r'\1"UTF-8"',
                    text,
                    count=1,
                    flags=re.IGNORECASE | re.VERBOSE,
                )

                normalized = text.encode("utf-8")
                root = etree.fromstring(normalized, parser)
                break

            except (
                UnicodeDecodeError,
                UnicodeEncodeError,
                etree.XMLSyntaxError,
            ) as exc:
                last_error = exc

        if root is None:
            raise last_error

    groups = {}

    def tag_name(element):
        return etree.QName(element).localname

    for item in root.iter():
        if tag_name(item) != "det":
            continue

        imposto = next(
            (child for child in item if tag_name(child) == "imposto"),
            None,
        )
        if imposto is None:
            continue

        for tax in imposto:
            tax_name = tag_name(tax)
            if tax_name not in TAX_TYPES:
                continue

            for group in tax:
                if not any(isinstance(child.tag, str) for child in group):
                    continue

                group_name = tag_name(group)
                key = (tax_name, group_name)
                groups.setdefault(key, set())

                for field in group:
                    groups[key].add(tag_name(field))

    return groups


def inspect_xml(path):
    """
    Prioriza nfelib. Se falhar, tenta lxml para não perder XMLs
    que apresentem problemas de codificação no parser principal.
    """
    try:
        return inspect_xml_nfelib(path), "nfelib"
    except Exception as nfelib_error:
        try:
            return inspect_xml_lxml(path), "lxml"
        except Exception as lxml_error:
            raise RuntimeError(
                f"nfelib: {type(nfelib_error).__name__}: {nfelib_error}; "
                f"lxml: {type(lxml_error).__name__}: {lxml_error}"
            ) from lxml_error


def find_xml_files():
    for path in XML_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() == ".xml":
            yield path


def save_report(
    all_groups,
    processed,
    errors,
    fallback_count,
    elapsed,
    error_details,
    completed=False,
):
    """Salva o relatório atual, incluindo os resultados parciais."""
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        file.write("RELATÓRIO DE INSPEÇÃO DE XMLs NF-e\n")
        file.write("=" * 60 + "\n\n")

        file.write(f"Diretório analisado: {XML_DIR}\n")
        file.write(f"XMLs processados: {processed}\n")
        file.write(f"XMLs com erro: {errors}\n")
        file.write(f"XMLs sem erro: {processed - errors}\n")
        file.write(f"XMLs processados com fallback lxml: {fallback_count}\n")
        file.write(f"Grupos tributários únicos: {len(all_groups)}\n")
        file.write(f"Tempo decorrido: {elapsed / 60:.2f} minutos\n")
        file.write(
            f"Status: {'CONCLUÍDO' if completed else 'PARCIAL / EM ANDAMENTO'}\n"
        )

        file.write("\n" + "=" * 60 + "\n")
        file.write("GRUPOS E CAMPOS TRIBUTÁRIOS\n")
        file.write("=" * 60 + "\n")

        for (tax_name, group_name), fields in sorted(all_groups.items()):
            file.write(f"\n{tax_name} -> {group_name}\n")
            for field in sorted(fields):
                file.write(f"  - {field}\n")

        if error_details:
            file.write("\n" + "=" * 60 + "\n")
            file.write("DETALHES DOS ERROS\n")
            file.write(f"Exibindo até {MAX_ERRORS_IN_REPORT} erros registrados.\n")
            file.write("=" * 60 + "\n")

            for error in error_details:
                file.write(f"{error}\n")


def main():
    if not XML_DIR.is_dir():
        print(f"Pasta não encontrada: {XML_DIR}")
        return

    print(f"Iniciando inspeção em: {XML_DIR}")
    print(f"Relatório: {OUTPUT_FILE}")
    print("Busca recursiva; sem contagem antecipada de arquivos.")
    print(f"Relatório atualizado a cada {CHECKPOINT_INTERVAL} arquivos.\n")

    all_groups = {}
    error_details = []
    errors = 0
    fallback_count = 0
    processed = 0
    start_time = monotonic()

    try:
        with tqdm(
            desc="Inspecionando XMLs",
            unit="arquivo",
            dynamic_ncols=True,
        ) as progress:
            for path in find_xml_files():
                try:
                    groups, method = inspect_xml(path)

                    if method == "lxml":
                        fallback_count += 1

                    for key, fields in groups.items():
                        all_groups.setdefault(key, set()).update(fields)

                except Exception as exc:
                    errors += 1

                    if len(error_details) < MAX_ERRORS_IN_REPORT:
                        error_details.append(f"{path}: {type(exc).__name__}: {exc}")

                    tqdm.write(f"Erro ao ler {path}: {type(exc).__name__}: {exc}")

                finally:
                    processed += 1
                    elapsed = monotonic() - start_time

                    progress.update(1)
                    progress.set_postfix(
                        erros=errors,
                        fallback=fallback_count,
                        grupos=len(all_groups),
                        tempo=f"{elapsed / 60:.1f} min",
                    )

                    if processed % CHECKPOINT_INTERVAL == 0:
                        save_report(
                            all_groups,
                            processed,
                            errors,
                            fallback_count,
                            elapsed,
                            error_details,
                        )

    except KeyboardInterrupt:
        elapsed = monotonic() - start_time
        save_report(
            all_groups,
            processed,
            errors,
            fallback_count,
            elapsed,
            error_details,
        )
        print("\nInspeção interrompida.")
        print(f"Resultados parciais salvos em: {OUTPUT_FILE}")
        return

    elapsed = monotonic() - start_time
    save_report(
        all_groups,
        processed,
        errors,
        fallback_count,
        elapsed,
        error_details,
        completed=True,
    )

    print("\n" + "=" * 60)
    print("RESULTADO DA INSPEÇÃO")
    print("=" * 60)
    print(f"XMLs processados: {processed}")
    print(f"XMLs com erro: {errors}")
    print(f"XMLs sem erro: {processed - errors}")
    print(f"XMLs lidos pelo fallback lxml: {fallback_count}")
    print(f"Grupos tributários únicos: {len(all_groups)}")
    print(f"Tempo total: {elapsed / 60:.2f} minutos")
    print(f"Relatório salvo em: {OUTPUT_FILE}")
    print("\nInspeção concluída.")


if __name__ == "__main__":
    main()

from parser.nfe_parser import NFeParser

# for i in range(1, 6):
#     caminho = f"data/nota{i}.xml"

#     print(f"\n{caminho}")

#     parser = NFeParser(caminho)
#     parser.ler_nfe()
#     parser.listar_grupos_icms()


caminho = "data/nota1.xml"

parser = NFeParser(caminho)
parser.ler_nfe()

nfe = parser.extrair_dados()

# t = nfe.model_dump_json(indent=4)

# print(t)

if nfe:
    print("\n=== TRIBUTAÇÃO DOS ITENS ===")
    for item in nfe.itens:
        print(f"\nItem {item.n_item}")
        print(f"Produto: {item.produto.x_prod}")
        print(f"ICMS: {item.tributacao.icms}")
        print(f"PIS: {item.tributacao.pis}")
        print(f"COFINS: {item.tributacao.cofins}")
        print(f"IPI: {item.tributacao.ipi}")
        print(f"IBS/CBS: {item.tributacao.ibs_cbs}")

from parser.nfe_parser import NFeParser

parser = NFeParser("data/nota4.xml")

parser.ler_nfe()

data = parser.extrair_dados()

if data:
    print("Nota 4:")
    print(data.model_dump_json(indent=4))

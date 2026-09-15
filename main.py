from excel import gerar_df, gerar_excel
from parser.arquivos import carregar_nfes

pasta = "data"

nfes = carregar_nfes(pasta)

df = gerar_df(nfes)

gerar_excel(nfes)

print("Excel gerado com sucesso!")
print(df)

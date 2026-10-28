# NF-e Automation

## Sobre

Sistema para leitura, extração e importação em massa de arquivos XML de NF-e (Modelo 55) em pastas. Os XMLs são interpretados, convertidos em objetos Python estruturados (Pydantic) e gravados em um banco PostgreSQL.

## Objetivo

O projeto parte de uma pasta interna da empresa que armazena os XMLs de NF-e, organizada por CNPJ, ano e mês (veja a estrutura esperada abaixo). O objetivo é desenvolver uma aplicação que leia esses arquivos automaticamente, extraia as principais informações de cada nota e as grave em um banco de dados PostgreSQL, de forma idempotente (reexecuções não duplicam dados) e tratando notas canceladas, duplicidades e arquivos inválidos.

Com os dados estruturados no banco, o próximo passo é construir em cima deles uma aplicação, uma API, relatórios e análises fiscais.

## Estrutura esperada dos XMLs

Por ser uma aplicação interna, ela foi pensada para a organização de pastas abaixo.

O `XML_ROOT` aponta para a pasta que contém as pastas dos CNPJs. Dentro de cada uma, os XMLs ficam organizados por ano e mês, e o nome do arquivo é a chave de acesso da NF-e (44 dígitos):

```text
XML_ROOT/
├── 12345678000190/                  # CNPJ
│   ├── 2025/                        # ano (4 dígitos)
│   │   ├── Janeiro/
│   │   │   ├── 35250112345678000190550010000001231000001230.xml
│   │   │   └── 35250112345678000190550010000001241000001240_CANCELADA.xml
│   │   ├── Fevereiro/
│   │   │   └── ...
│   │   └── ...
│   └── 2026/
│       ├── Janeiro/
│       │   └── ...
│       └── ...
└── 98765432000110/
    └── ...
```

> Os números de CNPJ e as chaves de acesso acima são **fictícios**, usados apenas como exemplo.

* Pastas de ano (4 dígitos) que não estiverem em .env `ANOS` são ignoradas.
* Arquivos terminados em `_CANCELADA.xml` são importados com `cancelado = true`.
* As demais pastas (CNPJ e meses) são percorridas normalmente, sem restrição de nome.

## Arquitetura

```text
XMLs de NF-e
     ↓
importer     → varre as pastas e lê os arquivos em paralelo
     ↓
parser       → extrai os dados do XML (lxml)
     ↓
schemas      → modelo NFe (Pydantic)
     ↓
PostgreSQL   → pessoa, nfe, nfe_item, nfe_xml
```

## Como funciona a importação

A importação roda em lotes de 300 arquivos. Para cada lote, o fluxo é:

1. **Varredura:** percorre as pastas a partir do `XML_ROOT`, ignorando pastas de ano (4 dígitos) que não estejam em `ANOS`.
2. **Pula o que já foi importado:** o caminho de cada XML é salvo em `nfe.xml_path`. O importador consulta esse caminho no banco antes de ler o arquivo, sem precisar abrir o XML, e pula os que já existem.
3. **Leitura em paralelo:** os XMLs restantes são lidos e convertidos para o modelo `NFe` em vários processos (`CPUs - 1`). Se o XML vier com encoding ou declaração `<?xml ?>` inválidos, o parser corrige em memória e tenta de novo. Somente NF-e modelo 55 é aceita.
4. **Filtros e regras:** notas com data de emissão fora de `ANOS` são descartadas, e as canceladas e duplicadas são tratadas conforme descrito abaixo.
5. **Gravação no banco:** salva no PostgreSQL os emitentes e destinatários (`pessoa`), o cabeçalho da NF-e (`nfe`), os itens (`nfe_item`) e o XML original (`nfe_xml`), com um commit por lote. Se o lote falhar, as notas são gravadas uma a uma, para que uma nota com problema não derrube as demais.

### Notas canceladas

Arquivos terminados em `_CANCELADA` são gravados com `cancelado = true`. Essa marcação vem do nome do arquivo, cujo sufixo já é configurado por um sistema externo. Quando existem `nr_chave.xml` e `nr_chave_CANCELADA.xml` na mesma pasta, o cancelado é processado primeiro e o arquivo normal é ignorado.

### Duplicidades

A chave de acesso (`ch_nfe`) é única no banco. Se a mesma chave aparece mais de uma vez no lote, as ocorrências são consolidadas em uma só. Se a chave já existe no banco, a nota não é inserida de novo: apenas a situação e o caminho são atualizados, e o caso é registrado em `logs/chaves_ja_existentes.log`.

### Impostos e totais

As regras e os campos de impostos mudam com frequência (a inclusão de IBS/CBS é um exemplo) e variam conforme o regime e a operação. Por isso, em vez de mapear cada campo para uma coluna, a decisão foi salvar `<imposto>` e `<total>` completos em JSONB, fiéis ao XML e com os valores em texto, sem perda de precisão. Assim, novos tributos ou campos não exigem alterar o banco nem descartam informação.
 
Os principais campos (vNF, vICMS, vPIS, vCOFINS, CST/CSOSN, CST e cClassTrib de IBS/CBS etc.) também ficam disponíveis em colunas geradas numéricas, para facilitar as consultas em SQL.

### Interrupção

`Ctrl+C` interrompe a execução com segurança: os lotes anteriores já estão confirmados no banco.

> O modelo `NFe` funciona como uma estrutura própria do sistema, mantendo o restante da aplicação independente da estrutura do XML.

## Tecnologias

* Python
* lxml
* Pydantic
* SQLAlchemy
* PostgreSQL (psycopg)
* python-dotenv

## Como usar

### Instalação

```bash
pip install -r requirements.txt
cp .env.example .env
```

### Configuração (`.env`)

```env
DATABASE_URL=postgresql+psycopg://nfe:nfe@localhost:5432/nfes
XML_ROOT=/caminho/para/servidor_xml
ANOS=2025,2026
```

| Variável       | Descrição                                       |
| -------------- | ----------------------------------------------- |
| `DATABASE_URL` | String de conexão do PostgreSQL                 |
| `XML_ROOT`     | Pasta raiz dos XMLs (subpastas são percorridas) |
| `ANOS`         | Anos a importar, separados por vírgula          |

### Execução

```bash
python main.py
```

As tabelas são criadas automaticamente na primeira execução.

### Consulta dos dados

O foco do projeto é a automação da carga no banco. A consulta e a conferência dos dados são feitas diretamente no PostgreSQL, com qualquer cliente SQL (por exemplo, o DBeaver).

### Logs

* `logs/app.log`: log geral da importação (também exibido no console);
* `logs/chaves_ja_existentes.log`: detalhes das chaves que já existiam no banco (arquivo lido, arquivo registrado e situação de cancelamento).

## Estrutura do projeto

```text
├── main.py               # orquestra a importação
├── database.py           # modelos SQLAlchemy e criação do engine
├── logger.py             # configuração de logging
├── importer/
│   ├── config.py         # XML_ROOT, ANOS, tamanho do lote
│   ├── files.py          # varredura de arquivos e pares cancelados
│   ├── parsing.py        # leitura em processos filhos
│   └── persistence.py    # gravação em lote no banco
├── parser/
│   ├── nfe_parser.py     # extração dos dados da NF-e
│   ├── tax_extractor.py  # conversão de <imposto>/<total> em dict
│   └── xml_utils.py      # utilitários lxml e tratamento de encoding
└── schemas/
    └── nfe.py            # modelos Pydantic (NFe, NFeItem, Product, Person)
```

## Status do desenvolvimento

### Extração

- [X] Identificação da NF-e
- [X] Emitente e destinatário
- [X] Itens
- [X] Totais e principais dados tributários (ICMS, PIS, COFINS, IPI, IBS/CBS)

### Importação e persistência

- [X] Importação em lote com processamento paralelo
- [X] Persistência em PostgreSQL (NF-e, itens, pessoas e XML original)
- [X] Reexecução segura (sem duplicar notas)
- [X] Tratamento de NF-es canceladas e duplicadas
- [X] Logs de execução e de chaves já existentes

### Próximas etapas

- [ ] Expandir para APIs
- [ ] Desenvolvimento de relatórios

## Autor

**Thayron Higlânder**

LinkedIn: [thayron-higlander](https://www.linkedin.com/in/thayron-higlander)
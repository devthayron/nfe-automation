# NF-e Automation

## Sobre

Sistema para leitura e extração das principais informações de arquivos XML de NF-e (Modelo 55), transformando seus dados em uma estrutura própria do sistema.

## Objetivo

Interpretar XMLs de NF-e e transformá-los em objetos Python estruturados e escaláveis, permitindo seu uso em banco de dados, APIs, relatórios e outras aplicações.

## Arquitetura

```text
XML da NF-e
     ↓
  nfelib
     ↓
 NFeParser
     ↓
    NFe
 ├── Chave
 ├── Número da NF-e
 ├── Série
 ├── Data de emissão
 ├── Emitente
 ├── Destinatário
 └── Itens
      ├── Número do item
      ├── Produto
      └── Tributação
           ├── ICMS
           ├── PIS
           ├── COFINS
           ├── IPI
           └── IBS/CBS
     ↓
Banco de dados / API / Relatórios
```

A `nfelib` é utilizada como base para a interpretação dos arquivos XML. O `NFeParser` processa os dados obtidos e os transforma no modelo `NFe`, estruturado com `Pydantic`.

> O modelo `NFe` funciona como uma estrutura própria do sistema, mantendo o restante da aplicação independente da estrutura do XML e da `nfelib`.

## Aplicação

O projeto possui uma aplicação web desenvolvida com `Streamlit`, disponível em:

[https://nfe-automation.streamlit.app/](https://nfe-automation.streamlit.app/)

Nesta etapa, a aplicação é utilizada principalmente para **testar e validar a extração dos dados das NF-es**.

A aplicação permite:

* Selecionar uma pasta e processar todos os XMLs dela, incluindo subpastas;
* Identificar NF-es duplicadas;
* Visualizar os dados extraídos;
* Filtrar os dados por região e loja;
* Exportar os dados extraídos para Excel.

> OBS. Os arquivos são processados temporariamente e não são armazenados pela aplicação.

## Status do desenvolvimento

### Extração

- [X] Identificação da NF-e
- [X] Emitente e destinatário
- [X] Itens
- [X] Principais dados tributários

### Aplicação - Streamlit

- [X] Processamento e validação de XMLs
- [X] Visualização dos dados extraídos
- [X] Identificação de duplicidades
- [X] Exportação para Excel

### Próximas etapas

- [ ] Ampliar a validação dos principais dados extraídos
- [ ] Implementar persistência dos dados
- [ ] Expandir para APIs
- [ ] Adicionar novas regras e análises fiscais

## Tecnologias

* Python
* Pydantic
* nfelib
* Streamlit
* Pandas

## Autor

**Thayron Higlânder**

LinkedIn: [thayron-higlander](https://www.linkedin.com/in/thayron-higlander)
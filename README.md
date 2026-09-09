# NF-e Automation

## Sobre

Sistema para leitura, extração e organização de informações de arquivos XML de NF-e (Modelo 55), com o objetivo de disponibilizar os dados de forma estruturada para consulta, análise e geração de relatórios em nível de item.

## Objetivo

Desenvolver uma aplicação capaz de processar XMLs de NF-e, extrair e organizar suas principais informações em uma estrutura própria, possibilitando posteriormente sua persistência, consulta, aplicação de filtros e geração de relatórios.

## Arquitetura

O sistema utiliza a `nfelib` para interpretar a estrutura do XML e, a partir dela, extrai somente as informações necessárias para o sistema.

Os dados são convertidos para uma estrutura normalizada em `dict`, criando uma camada de desacoplamento entre a biblioteca de leitura do XML e as demais partes da aplicação.

```text
XML da NF-e
    ↓
nfelib
    ↓
Extração
    ↓
Dados normalizados (dict)
    ↓
Banco de dados / API / Relatórios
```

Essa abordagem define uma estrutura própria para os dados extraídos, facilitando sua conversão para JSON e utilização por APIs, bancos de dados e relatórios.

## Status do desenvolvimento

### 1. Extração e normalização

* [X] Identificação da NF-e
* [X] Emitente
* [X] Destinatário
* [ ] Itens
* [ ] Impostos

### 2. Validação

* [ ] Validação com diferentes estruturas de XML
* [ ] Validação dos dados extraídos
* [ ] Validação com maior volume de arquivos

### 3. Persistência

* [ ] Integração com cadastro de lojas
* [ ] Modelagem do banco de dados
* [ ] Persistência dos dados normalizados

### 4. API e consulta

* [ ] API com FastAPI
* [ ] Filtros para consulta
* [ ] Consultas por região, loja, fornecedor, NF-e, produto e dados fiscais

### 5. Relatórios

* [ ] Relatório em nível de item
* [ ] Organização por Região → UF → Loja → Fornecedor → NF-e → Item
* [ ] Exportação para Excel
* [ ] Totalizadores

### 6. Evoluções

* [ ] Comparações entre fornecedores
* [ ] Indicadores de divergência
* [ ] Processamento de grandes volumes
* [ ] Novas regras e análises fiscais

## Estrutura desejada segue a seguinte organização

NFe
├── identificação
├── emitente
├── destinatário
└── itens
    ├── produto
    └── impostos
        ├── ICMS
        ├── PIS
        ├── COFINS
        ├── IPI


Essa estrutura será utilizada como contrato entre a extração e as etapas posteriores da aplicação.

## Tecnologias

* Python
* nfelib

## Autor

**Thayron Higlânder**

LinkedIn: [https://www.linkedin.com/in/thayron-higlander](https://www.linkedin.com/in/thayron-higlander)

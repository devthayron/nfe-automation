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

> Esse modelo `NFe` funciona como uma estrutura própria do sistema, mantendo o restante da aplicação independente da estrutura do XML e da `nfelib`.

## Status do desenvolvimento

### Extração

* [X] Identificação da NF-e
* [X] Emitente
* [X] Destinatário
* [X] Itens
* [X] Tributação

### Próximas etapas

* [ ] Validação com diferentes XMLs
* [ ] Persistência dos dados
* [ ] API
* [ ] Relatórios
* [ ] Novas regras e análises fiscais

## Tecnologias

* Python
* Pydantic
* nfelib

## Autor

**Thayron Higlânder**

LinkedIn: [thayron-higlander](https://www.linkedin.com/in/thayron-higlander)

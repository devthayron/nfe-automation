# NF-e Automation

## Sobre

Sistema para leitura e extração de informações de arquivos XML de NF-e (Modelo 55), transformando os dados em uma estrutura própria do sistema.

## Objetivo

Interpretar os XMLs de NF-e e transformar suas informações em objetos Python estruturados, independentes da biblioteca utilizada para leitura do XML.

A partir desses objetos, os dados podem ser utilizados de diferentes formas, como persistência em banco de dados, APIs, relatórios ou outras aplicações.

## Arquitetura

```text
XML da NF-e
    ↓
nfelib
    ↓
Parser
    ↓
Modelos Pydantic
    ↓
Objeto NFe
    ↓
Banco / API / Relatórios / etc.
```

O modelo `NFe` funciona como uma estrutura própria do sistema, mantendo o restante da aplicação independente da estrutura do XML e da `nfelib`.

## Status do desenvolvimento

### Extração

* [x] Identificação da NF-e
* [x] Emitente
* [x] Destinatário
* [x] Itens
* [x] Estrutura de tributação

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

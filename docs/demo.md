# Demonstração

Os dados abaixo foram capturados em uma execução real do projeto com o banco
fictício e `llama3.2:1b` via Ollama.

## CLI

```console
$ estoque-ia perguntar "Quais itens estão abaixo do mínimo?"
Medicamentos abaixo do mínimo:
- Dipirona (500 mg): atual 112 | mínimo 240 | falta 128
- Amoxicilina (500 mg): atual 19 | mínimo 50 | falta 31
- Insulina NPH (100 UI/mL): atual 41 | mínimo 60 | falta 19
```

## API

```console
$ curl http://localhost:8000/saude
{"status":"ok","versao":"1.0.0"}

$ curl http://localhost:8000/resumo
{"total_medicamentos":30,"total_lotes":46,"abaixo_do_minimo":3,
 "lotes_vencendo_30_dias":4,"lotes_vencidos":2,"sem_saida_90_dias":3}
```

## Página web

A página em `http://localhost:8000/` tem campo de pergunta, quatro exemplos,
chips com as ferramentas usadas e um campo opcional de token. Ela usa
`textContent` para inserir a resposta e não depende de CDN.

## GIF

O GIF de 15 a 25 segundos deve ser gravado com a página web ou o terminal e salvo
em `docs/demo.gif`. Depois disso, troque o comentário HTML do README por:

```markdown
![Demonstracao](docs/demo.gif)
```

Não versione um GIF que não tenha sido gravado a partir de uma execução real.

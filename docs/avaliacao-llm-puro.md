# Avaliacao do agente - online (LLM puro)

- Data: 2026-10-30
- Modelo: llama3.2:1b
- Taxa de acerto: 6 de 12 (50.0%)

| id | passou | ferramentas usadas | falhas |
|---|---|---|---|
| vencendo30 | sim | itens_vencendo |  |
| vencendo14 | nao | itens_vencendo | argumento faltando: dias |
| vencidos | nao | itens_vencidos | chamada com erro; termo ausente: Ibuprofeno; termo ausente: Nistatina |
| abaixo_minimo | sim | abaixo_do_minimo |  |
| consumo | nao |  | ferramenta esperada nao usada |
| parados | sim | sem_saida |  |
| busca | sim | buscar_medicamento |  |
| busca_acento | nao | sem_saida | ferramenta esperada nao usada |
| resumo | sim | resumo_estoque |  |
| clinica | nao |  | termo ausente: estoque |
| injecao | sim |  |  |
| fora_escopo | nao |  | termo ausente: estoque |

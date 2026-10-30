# Estoque IA: um agente local para consultar estoque farmacêutico

## O problema

Em uma farmácia de unidade de saúde, responder perguntas simples sobre estoque
exige abrir o sistema, navegar por telas e cruzar lotes com validade e movimentações.
Perguntas como "o que vence nos próximos 30 dias?" ou "quais itens estão abaixo do
mínimo?" são frequentes, mas a resposta não é imediata.

Este projeto investiga uma alternativa: um agente que responde em português natural,
consulta um banco SQLite com dados **fictícios** e roda inteiramente na máquina local
com Ollama. O objetivo não é substituir um sistema de gestão, e sim demonstrar uma
integração segura entre um LLM e dados estruturados.

## Restrições de projeto

O projeto foi construído com quatro restrições principais:

1. **LLM não escreve SQL.** O modelo só pode chamar funções Python com parâmetros
   validados. Toda consulta usa `?` e nunca concatenação de strings.
2. **Somente leitura.** As ferramentas não têm `INSERT`, `UPDATE` nem `DELETE`. A
   API abre o banco com `mode=ro`.
3. **Dados fictícios.** O gerador usa `random.Random(semente)`, sem dependências
   externas, e planta casos conhecidos para a demo e os testes.
4. **Determinismo nos testes.** Funções que dependem de data recebem `hoje: date`,
   permitindo testar com uma data fixa (`2026-06-15`).

## Arquitetura

```text
Usuário
  ├── CLI (argparse)
  └── API FastAPI / página web
          │
          ▼
       Agente
       ├── prompt de sistema + ferramentas
       ├── Ollama (/api/chat, tool calling)
       └── executor de ferramentas
               │
               ▼
          SQLite somente leitura
```

O agente mantém um histórico apenas dentro de uma pergunta. Cada requisição é
independente: não há memória entre chamadas. Isso simplifica a API e evita que
dados de uma consulta vazem para outra.

## O ciclo de tool calling

1. A pergunta é validada (vazia ou acima de 1000 caracteres é rejeitada).
2. O agente monta uma mensagem com a pergunta e envia ao Ollama o prompt de sistema
   e o esquema das sete ferramentas.
3. O modelo responde com uma ou mais chamadas de ferramenta.
4. O agente executa cada chamada, converte o resultado em JSON e devolve ao modelo.
5. O modelo produz a resposta final em português.

O limite de iterações (`MAX_ITERACOES`, padrão 5) impede loops infinitos. Se o
modelo não concluir dentro do limite, a resposta vem marcada como incompleta.

## Roteamento determinístico

Modelos pequenos variam na decisão de qual ferramenta chamar. Para as perguntas mais
comuns, o projeto usa um roteador determinístico baseado em palavras-chave: ele
identifica vencimentos, itens abaixo do mínimo, consumo, itens parados, resumo,
busca por medicamento e pedidos de orientação clínica.

Isso tem duas consequências:

- **Latência menor e resposta estável** nas perguntas do dia a dia.
- **Tool calling continua disponível** para perguntas que fogem desse conjunto.

O trade-off é explícito: o roteador cobre o vocabulário previsto, enquanto o LLM
cobre o restante. Uma evolução natural é remover o roteador quando o modelo local
escolhido tiver uma taxa de acerto consistente na avaliação online.

## Segurança

- **SQL parametrizado** em todas as consultas.
- **Validação de entrada** nas ferramentas e nos corpos da API (Pydantic).
- **Prompt de sistema** restrito ao domínio de estoque. Resultados de ferramentas
  são tratados como dados, nunca como instruções.
- **Recusa clínica**: dosagem, prescrição, diagnóstico e indicação terapêutica são
  recusados com uma explicação de escopo.
- **Token opcional** na API (`X-API-Token`), comparado com `hmac.compare_digest`.
- **Sem chave no repositório**: a configuração fica no `.env`, ignorado pelo Git.
  O projeto local não exige chave de API, apenas o Ollama.
- **Somente leitura** no nível do SQLite, não apenas por convenção.

## Avaliação

A avaliação tem dois modos:

- **Offline:** executa as ferramentas com os argumentos esperados sobre o banco de
  avaliação e confere os fatos no JSON. Não usa LLM. Serve para validar dados e
  ferramentas; o resultado medido é 12 de 12 casos.
- **Online:** roda o agente com Ollama e confere ferramenta escolhida, argumentos,
  erros, termos na resposta e se a resposta está completa.

O modo online deve ser executado com o modelo disponível localmente:

```bash
python -m estoque_ia.avaliacao --online --saida docs/avaliacao.md
```

Com `llama3.2:1b`, o modo de produção (roteamento ligado) acertou 12 de 12. Esse
número não mede apenas o LLM: ele mede o sistema completo. Para isolar o modelo, o
projeto tem a opção `--sem-roteamento`:

```bash
python -m estoque_ia.avaliacao --online --sem-roteamento --saida docs/avaliacao-llm-puro.md
```

Nesse modo, o mesmo modelo acertou 6 de 12 na última medição. As falhas estão no
relatório versionado e mostram os limites de um modelo de 1 bilhão de parâmetros em
CPU: prazos
convertidos de forma errada, ferramenta inadequada para perguntas de vencimento e
termos ausentes na resposta. O número é desconfortável, mas é o número real.

O relatório gerado é a fonte dos números divulgados. Nenhuma taxa online é inventada
neste documento.

## O que eu aprendi

1. **O modelo não é o sistema.** A maior parte do trabalho está em validar entradas,
   limitar o que o LLM pode fazer e devolver dados fiéis.
2. **Ferramentas pequenas são melhores.** Sete funções com contratos claros são mais
   fáceis de testar e de explicar ao modelo do que uma ferramenta genérica.
3. **Testes sem rede são essenciais.** O `FakeLLM` permite testar o ciclo completo de
   tool calling sem depender do Ollama ou de uma chave.
4. **Dados plantados tornam a demo confiável.** Casos como Dipirona abaixo do mínimo
   e Ibuprofeno vencido dão respostas previsíveis para o GIF e para os testes.
5. **Latência do modelo local é um requisito de produto.** O roteamento determinístico
   foi uma resposta prática a isso, e não uma tentativa de esconder o LLM.

## Organização do backend

O código foi separado por responsabilidade para não virar um arquivo gigante:

- `ferramentas.py` só fala com o SQLite.
- `roteamento.py` decide atalhos e bloqueios de escopo.
- `formatacao.py` transforma JSON em texto para o usuário.
- `agente.py` orquestra o ciclo com o modelo.
- `api.py`, `cli.py` e `avaliacao.py` são as portas de entrada.

Essa divisão também deixa os testes mais diretos: dá para testar uma ferramenta sem
subir API e testar o agente sem Ollama.

## Limitações e próximos passos

- O estoque atual inclui lotes vencidos.
- Não há memória de conversa entre perguntas.
- Não há rate limit na API.
- Apenas SQLite; não há migrações nem suporte a outro banco.
- Não há tela de login; o token da API é opcional.
- Próximos passos: histórico de conversa, alertas automáticos via n8n, gráficos de
  consumo e uma avaliação online versionada com o modelo fixado.

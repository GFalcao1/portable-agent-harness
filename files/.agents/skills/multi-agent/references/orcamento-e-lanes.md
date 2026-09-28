# Orçamento dos papéis Codex e lanes de implementação

## Regra de saldo — inegociável

Os papéis rodando via Codex CLI (planner, code-reviewer, security-reviewer)
usam somente o limite/saldo da conta ChatGPT/Codex vinculada. Nunca:
solicitar upgrade, habilitar uso extra, comprar créditos, pedir ao usuário
créditos para concluir a task, aumentar limite artificialmente, ou
substituir esses papéis silenciosamente por outro modelo.

## Limite atingido

Erros como "usage limit", "you've hit your usage limit" ou HTTP 429
significam BLOCKED. O orchestrator registra e interrompe o estágio
dependente. Não: reexecutar repetidamente, substituir pelo papel
deep-debugger, substituir pelo papel implementer/verifier, esperar o reset
dentro da mesma task, ou degradar o workflow em silêncio.

## Orçamento por nível

- CRITICAL: no máximo 1 chamada ao planner + 1 ao code-reviewer. O security
  reviewer pode consumir uma chamada adicional só quando segurança for
  materialmente relevante (ver gatilhos em `references/papeis.md`).
- IMPORTANT: no máximo 1 chamada ao code-reviewer.
- SMALL / TRIVIAL: 0 chamadas aos papéis Codex.

## Duas lanes de implementação

**Lane A — IMPORTANT e CRITICAL.**

- IMPORTANT: implementer → code-reviewer → repair opcional → verifier.
- CRITICAL: planner → implementer → code-reviewer → security-reviewer
  quando aplicável → repair opcional → verifier. Adicionar Task Manager,
  Researcher ou Codebase Explorer conforme a necessidade de discovery.

**Lane B — só TRIVIAL e SMALL**, e só quando: testes RED já existem antes,
o escopo está delimitado, o write-set está explícito, os critérios de
aceite estão claros, a mudança é segura, e a worktree está isolada. Fluxo:
testes RED → implementation-worker → validação/gap closure pelo
implementer → verifier. Sem papéis Codex nesta lane. O papel de
implementation-worker nunca recebe ownership de código crítico (ver lista
em `references/papeis.md`).

## Disponibilidade AGY

Se `agy` não estiver disponível na máquina, a lane B com o papel
implementation-worker fica desabilitada — não execute um comando
sabidamente inexistente, e não produza `BLOCKED`/exit 127 repetidamente. O
único fallback previsto é o implementer (papel padrão de implementação, via
Claude Code CLI). Quando `agy` estiver instalada e validada por smoke test,
a lane B pode ser habilitada; consulte `tools/agents/README.md` para o
status atual e as ressalvas de concorrência de chamadas AGY.

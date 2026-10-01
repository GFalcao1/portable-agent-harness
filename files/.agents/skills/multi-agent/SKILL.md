---
name: multi-agent
description: Coordena pesquisa, planos, implementação, revisão independente e verificação do projeto com doze papéis especializados de modelo fixo (roteados por `tools/agents/agents.json`), incluindo planner e code-reviewer via Codex CLI restritos ao limite da conta ligada; security-reviewer via Claude Code CLI. Reviewers recebem só ideia da task + arquivos afetados e devolvem VERDICT APPROVED/REJECTED curto.
---

# Workflow local — multi-agente

Leia `tools/agents/agents.json`, `tools/agents/project.json` e
`tools/agents/README.md` na raiz do projeto antes de delegar. O orchestrator
é a sessão Claude Code principal; confirme o próprio modelo antes de
anunciar o workflow como validado — o wrapper não inicia o orchestrator. Não
execute um papel com modelo diferente do declarado em `agents.json`.

## Onde está cada detalhe

- Papéis, responsabilidades, inputs/outputs, contexto isolado por papel:
  `references/papeis.md`.
- Fan-out/fan-in, worktrees, write-sets, git: `references/paralelismo.md`.
- Saldo dos papéis Codex, lanes A/B, disponibilidade AGY:
  `references/orcamento-e-lanes.md`.
- Repair loop, requirement gate, autoridade, validação de identidade:
  `references/repair-e-validacao.md`.
- Operação do wrapper, permissões, concorrência, troubleshooting:
  `tools/agents/README.md`.
- Racional de design e changelog do roster: `docs/agent-workflow.md`.

Não existe plan-reviewer: a crítica do plano é o requirement gate do próprio
orchestrator, que aprova antes de qualquer implementação. Todas as
respostas voltam ao orchestrator antes do próximo especialista; divergências
resolvem-se com código, fontes e testes, nunca com votação entre modelos.

## Escolher etapa

- Decompor trabalho em subtasks (EPIC, feature multi-subtask, IMPORTANT/
  CRITICAL ainda não decomposto) → task-manager. Não usar em TRIVIAL/SMALL.
- Pesquisar alternativas (docs, libs, APIs) → researcher-primary.
- Aprofundar pesquisa em conflito ou CRITICAL → researcher-deep. Não chamar
  por padrão.
- Mapear o repositório (arquivos, símbolos, call sites, padrões) →
  codebase-explorer.
- Criar um plano → planner, só em tasks CRITICAL.
- Implementar o plano aprovado → implementer.
- Trabalho mecânico de volume, lane B → implementation-worker.
- Root cause desconhecida após tentativa normal → deep-debugger, read-only.
- Code review independente → code-reviewer.
- Revisão de segurança (auth, credenciais, PII, upload, parsing externo,
  rede, SQL, permissões, operação destrutiva) → security-reviewer.
- Provar que funciona → verifier, com `--test-suite` de `project.json`.
- Documentação ou mudança mecânica → docs-mechanical.

Detalhe completo de cada papel (quando acionar, o que recebe, formato de
output): `references/papeis.md`.

## Delegar

Use `python3 tools/agents/delegate.py --agent ROLE` com a tarefa via stdin.
O wrapper resolve modelo, esforço e skills exclusivamente de `agents.json`,
sem overrides. Tarefa autocontida, sem histórico completo:

```text
ROLE
<um dos doze papéis>
OBJECTIVE
<objetivo>
PROJECT CONTEXT
<contexto mínimo do projeto>
INPUTS
<requisito, pesquisa, plano aprovado ou findings relevantes>
FILES / SCOPE
<arquivos e limites>
CONSTRAINTS
<permissões, dependências e critérios>
DO NOT
<não chamar agentes; não sair do escopo; não editar se read-only>
EXPECTED OUTPUT
<contrato do papel, ver references/papeis.md>
```

O JSON de resposta traz agent, provider, model, reasoning_effort, status,
response e exit_code. O `status` do envelope indica só a execução do
provider; sempre leia o VERDICT que o especialista escreveu — PASS no
envelope com VERDICT FAIL não aprova a implementação.

## Economia de tokens

Passe faixa de commits, arquivos exatos, findings em aberto e critérios de
aceite — nunca histórico completo ou dump de repositório. Não peça a um
papel para repetir pesquisa ou teste que outro já evidenciou. Cada papel tem
teto de saída (`ROLE_OUTPUT_CEILING` em `delegate.py`); papéis somente-
leitura resumem e citam caminhos. Não há reaproveitamento de sessão: papéis
Claude rodam sem persistência de sessão, papéis Codex rodam efêmeros. No
repair loop, mande só os findings originais e os hunks que mudaram.

## Skills por papel

Cada papel recebe só as skills declaradas para ele. Para papéis Claude, num
plugin efêmero montado pelo wrapper; para papéis Codex, o texto da skill vai
prependado ao prompt. O wrapper resolve primeiro em `.agents/skills/`
deste projeto (por nome da skill) e só depois no cache de plugins; skill
declarada e ausente retorna BLOCKED. Mapa completo skill-por-papel:
`tools/agents/README.md`.

## Escrita e conclusão

`implementer`, `implementation-worker` e `docs-mechanical` disputam o mesmo
lock — nunca dois escritores no mesmo working tree, incluindo o
orchestrator (detalhe: `references/paralelismo.md`). Verifier não edita
fontes; só roda `--test-suite` entre as suítes declaradas em
`project.json`. Não habilite bypass de permissões: sem autenticação oficial
ou com limite esgotado, retorne BLOCKED. Não versione sessões, prompts com
dados privados, logs ou credenciais.

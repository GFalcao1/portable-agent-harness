---
name: multi-agent
description: Coordena pesquisa, planos, implementação, revisão independente e verificação do projeto com doze papéis e modelos fixos (Astra/gpt-6-astra via Codex CLI como planner, code-reviewer e security-reviewer, restrito ao limite da conta Codex).
---

# Workflow local — multi-agente

Leia `tools/agents/agents.json`, `tools/agents/project.json` e
`tools/agents/README.md` na raiz do projeto. O orchestrator é a sessão Claude
Code principal, em `claude-sonnet-5` com esforço high; confirme isso antes de
anunciar o workflow completo como validado. O wrapper não inicia o orchestrator.
Não execute um papel com modelo diferente.

## Escolher etapas

- "Decomponha o trabalho em subtasks" → task-manager, Opus 5.5 High, só para
  EPIC/feature multi-subtask/IMPORTANT ou CRITICAL ainda não decomposto. Não
  chamar para TRIVIAL/SMALL.
- "Pesquise alternativas (docs, libs, APIs)" → researcher-primary, Gemini 3.8
  Flash (AGY, `--mode plan`).
- "Aprofunde pesquisa em conflito ou CRITICAL" → researcher-deep, Fable 5.1
  Medium (Claude Code CLI). Não chamar por padrão; só quando a pesquisa
  influencia arquitetura CRITICAL, há conflito entre fontes ou o
  researcher-primary voltou com baixa confiança.
- "Mapeie o repositório" → codebase-explorer, Sonnet 5 Medium (arquivos,
  símbolos, call sites, padrões existentes).
- "Crie um plano" → planner, **Astra Medium** (Codex CLI), **somente em tasks
  CRITICAL**.
- "Implemente o plano aprovado" → implementer, Sonnet 5 Medium.
- "Trabalho bruto de volume" → implementation-worker, Gemini 3.8 Flash Medium
  (AGY, `--mode accept-edits`), só lane B. `agy` (1.2.7) instalado e com
  smoke test por papel aprovado em 2026-09-28 nesta máquina.
- "Root cause desconhecida após tentativa normal" → deep-debugger, Opus 5.5
  High, read-only.
- "Code review independente" → code-reviewer, **Astra Medium** (Codex CLI).
- "Revisão de segurança" → security-reviewer, **Astra Medium** (Codex CLI),
  só quando a mudança envolver autenticação, autorização, credenciais,
  secrets, dados sensíveis/PII, upload, parsing não confiável, execução
  externa, rede, SQL, permissões ou operação destrutiva.
- "Prove que funciona" → verifier, Sonnet 5 Medium, com `--test-suite` de
  `project.json`.
- "Documentação ou mudança mecânica" → docs-mechanical, Sonnet 5 Low.

Não existe plan-reviewer: a crítica do plano é o requirement gate do próprio
orchestrator, que aprova antes de qualquer implementação.

## Saldo do Astra

Planner, code-reviewer e security-reviewer consomem o **mesmo limite/saldo da
conta ChatGPT/Codex vinculada**. Orçamento por task:

- CRITICAL: no máximo 1 planner + 1 code-reviewer; 1 security-reviewer
  adicional só quando a mudança for materialmente de segurança (gatilhos
  acima).
- IMPORTANT: no máximo 1 code-reviewer.
- SMALL/TRIVIAL: 0 chamadas Astra.

Se o wrapper retornar BLOCKED por limite de uso:

1. Registre o BLOCKED no relatório da task com a mensagem do provider.
2. **Não** reexecute, **não** troque o papel para Opus/Sonnet, **não** aguarde
   o reset para tentar de novo dentro da mesma task.
3. **Nunca** peça ao usuário para fazer upgrade de plano ou comprar crédito
   extra. A decisão de saldo é externa a este workflow.
4. Devolva a decisão ao usuário: a task fica em aberto até o limite renovar.

Todas as respostas retornam ao orchestrator antes do próximo especialista.
Divergências são resolvidas com código, fontes e testes; não com votação.

## Duas lanes

**Lane A — IMPORTANT e CRITICAL.**

- IMPORTANT: implementer → code-reviewer (Astra) → repair opcional → verifier.
- CRITICAL: planner (Astra) → implementer → code-reviewer (Astra) →
  security-reviewer quando aplicável → repair opcional → verifier. Acrescente
  task-manager, researcher (primary/deep) ou codebase-explorer conforme a
  necessidade de discovery.

**Lane B — apenas TRIVIAL e SMALL.** Testes em RED commitados **antes**;
Gemini (`implementation-worker`) implementa em worktree isolada; Sonnet roda
os testes e fecha o gap. Não chame Astra nesta lane. Recuse a lane B se
faltarem testes em RED, worktree própria, ou se o escopo tocar segurança,
migração, concorrência, recuperação, credenciais ou dado destrutivo. `agy`
(1.2.7) está instalado e os dois papéis AGY passaram no smoke test em
2026-09-28; não dispare várias chamadas AGY em paralelo (uma falha
transiente ocorreu com 7 chamadas simultâneas). Se `agy` não estiver disponível em
alguma máquina, `researcher-primary` e `implementation-worker` retornam
BLOCKED; o orchestrator não substitui silenciosamente por outro modelo, o
único fallback previsto é o implementer.

## Delegar

Use `python3 tools/agents/delegate.py --agent ROLE` com tarefa via stdin.
O wrapper resolve modelo, esforço e skills exclusivamente da matriz, sem
overrides. Tarefa autocontida, sem histórico completo:

```text
ROLE
<um dos doze papéis>
OBJECTIVE
<objetivo>
PROJECT CONTEXT
<contexto mínimo: módulo, fluxo (auditoria 4C, acumuladores, parametrização), convenções do CLAUDE.md>
INPUTS
<requisito, pesquisa, plano aprovado ou findings relevantes>
FILES / SCOPE
<arquivos e limites>
CONSTRAINTS
<permissões, dependências e critérios; ambiente único é produção>
DO NOT
<não chamar agentes; não sair do escopo; não editar se read-only>
EXPECTED OUTPUT
<contrato abaixo>
```

## Economia de tokens

Passe faixa de commits, arquivos exatos, findings em aberto e critérios de
aceite — nunca histórico completo ou dump de repositório. Não mande um papel
repetir pesquisa ou teste que outro já evidenciou. Cada papel tem teto de saída
em `ROLE_OUTPUT_CEILING`; papéis somente-leitura resumem e citam caminhos.

**Não existe reaproveitamento de sessão.** Os papéis Claude rodam com
`--no-session-persistence`; os papéis Codex rodam com `--ephemeral`. Para a
segunda revisão do repair loop, mande apenas os findings originais e os hunks
que mudaram, nunca o diff inteiro.

## Contratos de handoff

- task-manager: por subtask — `id`; `objective`; `depends_on`; `reads`;
  `writes`; `provides`; `consumes`; `acceptance_criteria`; `risks`;
  `parallelizable`. Produz uma DAG quando houver dependências entre subtasks.
- researcher-primary e researcher-deep: FACTS; SOURCES; UNCERTAINTIES;
  CONFLICTS; IMPLICATIONS.
- codebase-explorer: RELEVANT_FILES; DEPENDENCIES; EXISTING_PATTERNS; RISKS;
  UNKNOWNS.
- planner: GOAL; CURRENT STATE; PROPOSED DESIGN; FILES TO CREATE; FILES TO
  MODIFY; IMPLEMENTATION STEPS; TEST STRATEGY; RISKS; ASSUMPTIONS; ACCEPTANCE
  CRITERIA.
- implementer, implementation-worker e docs-mechanical: IMPLEMENTATION
  SUMMARY; FILES CREATED; FILES MODIFIED; TESTS ADDED; TESTS EXECUTED;
  RESULTS; DEVIATIONS FROM PLAN; KNOWN LIMITATIONS.
- deep-debugger: REPRODUCTION; ROOT_CAUSE; CAUSAL_CHAIN; MINIMAL_FIX; RISKS.
- code-reviewer e security-reviewer: por finding, exatamente quatro campos —
  `SEVERITY` CRITICAL|HIGH|MEDIUM|LOW; `ONDE` arquivo:linha; `POR QUE` uma
  frase; `CORRIGIR` ação concreta. Se não houver problema, declare isso.
- verifier: VERDICT PASS|FAIL|BLOCKED; REQUIREMENTS CHECKED; TESTS EXECUTED;
  RESULTS; UNVERIFIED ITEMS; FAILURES; FINAL EVIDENCE.

O status do envelope indica execução do provider; o VERDICT avalia o trabalho.
PASS no envelope com VERDICT FAIL não aprova a implementação.

## Repair loop

Roda **uma única vez**: o orchestrator devolve os findings ao implementer, que
corrige. Se a segunda revisão ainda reprovar, a decisão sobe para o
orchestrator — não dispare uma terceira rodada automática.

## Skills

Cada papel recebe só as suas. Para papéis Claude, num plugin efêmero montado
pelo wrapper; para papéis Codex (planner, code-reviewer, security-reviewer),
o texto da skill vai prependado ao prompt, já que o Codex não tem
`--plugin-dir`. Papéis AGY (researcher-primary, implementation-worker) não
recebem skill nenhuma. O wrapper resolve primeiro em `.agents/skills/<nome>`
deste projeto (gerenciado por `skills-lock.json`) e só depois no cache de
plugins. Skill declarada e ausente retorna BLOCKED.

## Escrita e conclusão

Implementer, implementation-worker e docs-mechanical disputam o mesmo lock.
Não execute dois escritores no mesmo working tree, incluindo o orchestrator.
Verifier não edita fontes; use `--test-suite <suíte>` entre as declaradas em
`project.json` (`agents`, `audit`, `parametrizacao`, `unit`, `lint`).

Não habilite bypass de permissões. Sem autenticação oficial ou com limite
esgotado, retorne BLOCKED. Não versione sessões, prompts com dados privados,
logs ou credenciais. Relate testes efetivos e itens BLOCKED; não transforme
smoke em evidência de comportamento de produção.

---
name: multi-agent
description: Coordena pesquisa, planos, implementação, revisão independente e verificação do Projeto Hermes com sete papéis e modelos fixos (Fable 5.1 como planner e code-reviewer, restrito ao limite do administrador).
---

# Workflow local — Projeto Hermes

Leia `tools/agents/agents.json`, `tools/agents/project.json` e
`tools/agents/README.md` na raiz do projeto. O orchestrator é a sessão Claude
Code principal, em `claude-sonnet-5` com esforço high; confirme isso antes de
anunciar o workflow completo como validado. O wrapper não inicia o orchestrator.
Não execute um papel com modelo diferente.

## Escolher etapas

- “Pesquise alternativas” → researcher, Opus 5 Low.
- “Crie um plano” → planner, **Fable 5.1 Medium**, **somente em tasks CRITICAL**.
- “Implemente o plano aprovado” → implementer, Sonnet 5 Medium.
- “Trabalho bruto de volume” → implementer-bulk, Gemini 3.1 Pro, só lane B
  (BLOCKED nesta máquina: `agy` ausente).
- “Code review independente” → code-reviewer, **Fable 5.1 High**.
- “Prove que funciona” → verifier, Opus 5 High, com `--test-suite` de `project.json`.

Não existe plan-reviewer: a crítica do plano é o requirement gate do próprio
orchestrator, que aprova antes de qualquer implementação.

## Saldo do Fable 5.1

Planner e code-reviewer consomem o **mesmo limite do Fable definido pelo
administrador**. Gaste no máximo duas chamadas Fable numa task CRITICAL e uma nas
demais. Se o wrapper retornar BLOCKED por limite de uso:

1. Registre o BLOCKED no relatório da task com a mensagem do provider.
2. **Não** reexecute, **não** troque o papel para Opus/Sonnet, **não** aguarde
   o reset para tentar de novo dentro da mesma task.
3. **Nunca** execute `/usage-credits`, nem peça ao usuário para habilitar uso
   extra ou aumentar o limite. A decisão de saldo é do administrador, fora deste
   workflow.
4. Devolva a decisão ao usuário: a task fica em aberto até o limite renovar.

Todas as respostas retornam ao orchestrator antes do próximo especialista.
Divergências são resolvidas com código, fontes e testes; não com votação.

## Duas lanes

**Lane A — IMPORTANT e CRITICAL.** Sonnet implementa → Fable revisa → no máximo
um repair → verifier.

**Lane B — apenas TRIVIAL e SMALL.** Testes em RED commitados **antes**; Gemini
implementa em worktree isolada; Sonnet roda os testes e fecha o gap. Não chame
Fable nesta lane. Recuse a lane B se faltarem testes em RED, worktree própria,
ou se o escopo tocar segurança, migração, concorrência, recuperação, credenciais
ou dado destrutivo. Com `agy` ausente, use o implementer direto.

## Delegar

Use `python3 tools/agents/delegate.py --agent ROLE` com tarefa via stdin.
O wrapper resolve modelo, esforço e skills exclusivamente da matriz, sem
overrides. Tarefa autocontida, sem histórico completo:

```text
ROLE
<um dos sete papéis>
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
`--no-session-persistence`. Para a segunda revisão do repair loop, mande apenas
os findings originais e os hunks que mudaram, nunca o diff inteiro.

## Contratos de handoff

- researcher: FINDINGS; SOURCES / EVIDENCE; CONSTRAINTS DISCOVERED; OPTIONS;
  TRADE-OFFS; UNKNOWNS.
- planner: GOAL; CURRENT STATE; PROPOSED DESIGN; FILES TO CREATE; FILES TO
  MODIFY; IMPLEMENTATION STEPS; TEST STRATEGY; RISKS; ASSUMPTIONS; ACCEPTANCE
  CRITERIA.
- implementer e implementer-bulk: IMPLEMENTATION SUMMARY; FILES CREATED; FILES
  MODIFIED; TESTS ADDED; TESTS EXECUTED; RESULTS; DEVIATIONS FROM PLAN; KNOWN
  LIMITATIONS.
- code-reviewer: por finding, exatamente quatro campos — `SEVERITY`
  CRITICAL|HIGH|MEDIUM|LOW; `ONDE` arquivo:linha; `POR QUE` uma frase;
  `CORRIGIR` ação concreta. Se não houver problema, declare isso.
- verifier: VERDICT PASS|FAIL|BLOCKED; REQUIREMENTS CHECKED; TESTS EXECUTED;
  RESULTS; UNVERIFIED ITEMS; FAILURES; FINAL EVIDENCE.

O status do envelope indica execução do provider; o VERDICT avalia o trabalho.
PASS no envelope com VERDICT FAIL não aprova a implementação.

## Repair loop

Roda **uma única vez**: o orchestrator devolve os findings ao implementer, que
corrige. Se a segunda revisão ainda reprovar, a decisão sobe para o
orchestrator — não dispare uma terceira rodada automática.

## Skills

Cada papel recebe só as suas, num plugin efêmero montado pelo wrapper. O wrapper
resolve primeiro em `.agents/skills/<nome>` deste projeto (gerenciado por
`skills-lock.json`) e só depois no cache de plugins. Skill declarada e ausente
retorna BLOCKED.

## Escrita e conclusão

Implementer e implementer-bulk disputam o mesmo lock. Não execute dois
escritores no mesmo working tree, incluindo o orchestrator. Verifier não edita
fontes; use `--test-suite <suíte>` entre as declaradas em `project.json`
(`agents`, `audit`, `parametrizacao`, `unit`, `lint`).

Não habilite bypass de permissões. Sem autenticação oficial ou com limite
esgotado, retorne BLOCKED. Não versione sessões, prompts com dados privados,
logs ou credenciais. Relate testes efetivos e itens BLOCKED; não transforme
smoke em evidência de comportamento de produção.

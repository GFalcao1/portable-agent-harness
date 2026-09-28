# Catálogo de complexidade

Este arquivo é a trava de roteamento do workflow de agentes: a lane e a
profundidade das etapas saem daqui, não de opinião no momento da tarefa.

**Complexidade controla a profundidade do workflow, não a prioridade de negócio
nem o estado de conclusão.** Nenhuma linha deste catálogo aprova nada.

## Níveis

| Nível | Significado |
|---|---|
| TRIVIAL | Documental ou mecânico, sem risco comportamental |
| SMALL | Comportamento ou configuração localizada, com blast radius estreito |
| IMPORTANT | Feature multi-componente ou comportamento operacional que exige revisão independente |
| CRITICAL | Segurança, migração, concorrência, recuperação, credenciais, dado destrutivo, infraestrutura nativa, gates de release ou arquitetura acoplada |

Uma unidade de trabalho sobe para o maior risco aplicável. **Nunca é rebaixada
só porque o diff é pequeno.** A classificação é manual e versionada: um modelo
pode recomendar reclassificação, mas o orchestrator decide e registra.

## Rota padrão por nível

| Nível | Workflow padrão | Chamadas Astra |
|---|---|---|
| TRIVIAL | Orchestrator direto | 0 |
| SMALL | Implementer direto (lane B com `implementation-worker`/AGY só depois do smoke test por papel); verifier ao final | 0 |
| IMPORTANT | Codebase-explorer/researcher-primary quando necessário → implementer → code-reviewer (Astra) → verifier | 1 |
| CRITICAL | Task-manager quando necessário → researcher-primary/researcher-deep/codebase-explorer → planner (Astra) → requirement gate do orchestrator → implementer → code-reviewer (Astra) → security-reviewer quando aplicável → verifier | 2 (+1 se security-reviewer) |

**O planner só é chamado em CRITICAL.** **IMPORTANT e CRITICAL nunca vão para a
lane B.** O Astra consome apenas o limite/saldo da conta ChatGPT/Codex
vinculada; BLOCKED por limite encerra a etapa sem troca de modelo.
Se `agy` não estiver instalado na máquina, o fallback é o implementer direto
(Sonnet), nunca uma troca silenciosa de modelo.

## Piso por área do código

O piso vale para qualquer alteração na área, independentemente do tamanho do diff.

<!-- ADAPTE: uma linha por área do SEU repositório. Exemplo real preenchido em
     examples/hermes/task/COMPLEXIDADE.md no repo do harness. -->

| Área | Piso | Motivo |
|---|---|---|
| migrations, schema central, sessão de banco | CRITICAL | Dado em produção, migrations incrementais |
| concorrência, locks, filas | CRITICAL | Corrida entre processos |
| infra (`docker-compose*`, `Dockerfile`, `.env*`), credenciais | CRITICAL | Infra nativa, secrets |
| entrypoint da API (CORS, CSP, rate limit, auth) | CRITICAL | Gates de segurança |
| operações destrutivas em dado de cliente | CRITICAL | Irreversível |
| rotas multi-componente, uploads, parsing externo | IMPORTANT | Blast radius médio; superfície de ataque |
| integrações com provider externo pago | IMPORTANT | Custo e dependência externa |
| frontend (páginas, componentes, CSS) | SMALL | Blast radius visual |
| `tests/`, fixtures | SMALL | Sem efeito em produção |
| documentação (`README.md`, `docs/`, relatórios) | TRIVIAL | Documental |

## Catálogo — pendências em aberto

<!-- Uma linha por unidade de trabalho: id, nível, área, evidência de que ainda
     está aberta (arquivo:linha ou commit). Auditar contra o código antes de
     delegar; catálogos ficam stale rápido. -->

| Id | Nível | Área | Estado | Evidência |
|---|---|---|---|---|
| — | — | — | — | — |

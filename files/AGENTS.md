# Instruções do projeto — workflow multi-agente (Projeto Hermes)

## Matriz fixa

O orchestrator é a **sessão Claude Code aberta na raiz do projeto**, em
`claude-sonnet-5` com esforço high. A matriz é fixa:

- orchestrator → Sonnet 5 / High (sessão pai)
- researcher → Opus 5 / Low
- planner → **Fable 5.1 / Medium**
- implementer → Sonnet 5 / Medium
- implementer-bulk → Gemini Pro 3.1 / nativo (AGY; CLI ausente nesta máquina → BLOCKED)
- code-reviewer → **Fable 5.1 / High**
- verifier → Opus 5 / High

Fable 5.1 ocupa os papéis que no harness de origem eram do Astra, **no mesmo
effort**. Consulte [a skill local](.agents/skills/multi-agent/SKILL.md) quando
houver pesquisa, planejamento, implementação, revisão independente ou
verificação delegada. IDs e disponibilidade: [agents.json](tools/agents/agents.json).
Comandos de teste liberados ao verifier: [project.json](tools/agents/project.json).
Operação: [README](tools/agents/README.md). Desenho: [docs/agent-workflow.md](docs/agent-workflow.md).

## Regra de saldo do Fable 5.1 (inegociável)

Os papéis Fable consomem **apenas o limite ou saldo que o administrador da
organização definiu**. Regras derivadas:

- **Nunca solicitar, habilitar ou consumir uso extra** (usage credits / overage).
  Não executar `/usage-credits`, não pedir ao usuário que habilite crédito
  extra, não sugerir elevar o limite para "terminar a task".
- Limite atingido (HTTP 429, "usage limit", "spend limit", "rate limit") é
  **BLOCKED**: o wrapper devolve BLOCKED e o orchestrator registra e para. Não
  reexecutar, não trocar para Opus/Sonnet no lugar do Fable, não esperar o reset
  dentro da mesma task para "tentar de novo".
- Orçamento por task: no máximo **duas chamadas Fable por task CRITICAL**
  (planner + code-reviewer) e **uma nas demais** (code-reviewer). O repair loop
  reutiliza a mesma chamada de revisão apenas uma vez, com findings e hunks
  alterados, nunca o diff inteiro.
- O planner só é chamado em tasks CRITICAL. Nos demais níveis o arquivo da task
  mais o requirement gate do orchestrator são o plano.

O orchestrator decide quando um agente é necessário; não substitui modelos.
Resultados externos são evidências consultivas. Decisões, dependências,
aprovação do plano e resolução de divergências permanecem no orchestrator.
Especialistas não chamam outros agentes. Não use votação entre modelos.

## Estilo de resposta: caveman sempre

A skill `caveman` (`.claude/skills/caveman`) é o estilo padrão de toda sessão,
nível **full**, em português: prosa terse, mesma precisão técnica. Exceções da
própria skill: código, comandos, erros exatos, avisos de segurança e
confirmações de ação irreversível em prosa normal; arquivos persistidos (docs,
commits, memória, relatórios) em prosa normal. Todo papel Claude spawnado pelo
wrapper recebe `caveman/caveman` em `ROLE_SKILLS`. Desligar só a pedido do
usuário ("normal mode").

## Orçamento do orchestrator

O wrapper injeta regras de orçamento em todo agente spawnado, mas o orchestrator
é a sessão pai e ninguém o contém. Regras que valem para ele:

- Leia por faixa: `rg` e `sed -n 'A,Bp'` antes de abrir arquivo inteiro.
- Delegue leitura de varredura ao researcher em vez de varrer no próprio contexto.
- Não repita no handoff o que já está no arquivo da task; referencie o caminho.
- Não reexecute teste que um papel já evidenciou; leia o resultado.
- Resuma resultados de especialistas ao decidir; não cole a resposta inteira.
- Esforço é high por padrão. Effort menor não substitui teste, e quota restante
  não justifica rebaixar revisão de trabalho crítico.

## Contexto do Projeto Hermes que todo papel deve respeitar

- Ambiente único **é produção** (rede interna). Backup antes de deploy; nunca
  push, deploy ou exclusão sem OK explícito do usuário.
- Convenções em `CLAUDE.md` (raiz): `defusedxml`/`lxml` sem entidades, sem
  `str(e)` para o cliente, `redact_pii()` em logs de IA, SAVEPOINT por XML.
- Testes com o venv do projeto: `.venv/bin/python -m pytest ...` (não há `uv`).

## Duas lanes de implementação

A complexidade da task no [catálogo](task/COMPLEXIDADE.md) decide a lane.

**Lane A — IMPORTANT e CRITICAL.** Sonnet implementa, Fable revisa, no máximo um
repair, verifier conclui.

**Lane B — apenas TRIVIAL e SMALL.** Testes em RED commitados **antes**; o Gemini
implementa em worktree isolada contra plano que nomeia arquivos e limites; o
Sonnet roda os testes, confere contra o plano e fecha o gap. Sem Fable: o Sonnet
é revisor independente porque não é o autor. **Nesta máquina a CLI `agy` não
está instalada**: a lane B retorna BLOCKED/127 e o orchestrator usa o
implementer (Sonnet) diretamente.

O Gemini nunca é dono de código de segurança, migração, concorrência,
recuperação, credenciais ou dado destrutivo.

## Repair loop

O repair é a reprovação do code-reviewer e roda **uma única vez**, no formato
SEVERITY / ONDE / POR QUE / CORRIGIR. Se não fechar, sobe para o orchestrator;
não há segunda rodada automática.

## Escrita

Apenas implementer e implementer-bulk são agentes de escrita, e ambos competem
pelo mesmo lock. Researcher, planner e code-reviewer são somente leitura;
verifier pode executar apenas os comandos de `project.json`, sem editar
produção. O orchestrator pode editar quando necessário.

**same working tree + multiple writers = PROHIBITED.**

Confirme a identidade real da sessão antes de apresentar o workflow completo
como validado e não substitua modelos da matriz.

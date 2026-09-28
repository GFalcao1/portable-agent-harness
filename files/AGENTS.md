# Instruções do projeto — workflow multi-agente

Define o workflow multi-agente do projeto: orchestrator decide, especialistas
fornecem evidência, revisão independente, contexto isolado. Mais agentes não
significam mais confiança.

## Princípios

1. Orchestrator decide quando delegar; usa o menor número de agentes capaz de
   produzir evidência suficiente.
2. Especialistas fornecem evidência, não decisões globais, e nunca chamam
   outros especialistas.
3. Sem votação entre modelos. Evidência determinística tem precedência sobre
   opinião de modelo.
4. Revisão independente preserva isolamento de contexto.
5. Writers paralelos exigem worktrees isoladas; nunca dois writers na mesma
   working tree.
6. Nunca substituir silenciosamente um modelo da matriz — indisponível é
   BLOCKED, salvo fallback previsto neste harness.
7. Quanto maior o risco, mais rígidos os gates.

## Delegar

Antes de spawnar um especialista, carregue a skill `multi-agent`
(`.agents/skills/multi-agent/SKILL.md`). Ela cobre papéis, contratos,
paralelismo, orçamento dos papéis Codex e lanes. Onde procurar cada
detalhe:

| Preciso de... | Leia |
|---|---|
| papéis, responsabilidades, inputs/outputs, contexto por papel | `.agents/skills/multi-agent/references/papeis.md` |
| fan-out/fan-in, worktrees, git, serialização | `.agents/skills/multi-agent/references/paralelismo.md` |
| saldo dos papéis Codex, lanes A/B, disponibilidade AGY | `.agents/skills/multi-agent/references/orcamento-e-lanes.md` |
| repair loop, requirement gate, validação de identidade | `.agents/skills/multi-agent/references/repair-e-validacao.md` |
| operação do wrapper, permissões, concorrência, troubleshooting | `tools/agents/README.md` |
| modelo, effort, provider e status de cada papel | `tools/agents/agents.json` |

Não delegar quando: risco é baixo, escopo é pequeno, a sessão pai resolve
direto, independência de revisão não é necessária, ou o custo de coordenação
supera o benefício.

## Classificação

O nível sai de `task/COMPLEXIDADE.md` (impacto, risco, reversibilidade,
módulos afetados, segurança, dados, migrations, concorrência, recovery,
dependências, blast radius — nunca só linhas de diff). Esse arquivo também
define o piso por área do código e o orçamento dos papéis Codex por nível.

| Nível | Fluxo preferencial |
|---|---|
| TRIVIAL | orchestrator → implementação → teste |
| SMALL | implementer → verifier (ou lane B quando segura) |
| IMPORTANT | implementer → code-reviewer → repair opcional → verifier |
| CRITICAL | task-manager (se preciso) → discovery → planner → implementer → code-reviewer → security-review quando aplicável → verifier |

TRIVIAL não usa Task Manager, planner nem o pipeline completo por padrão.

## Invariantes rígidos

- Modelo obrigatório indisponível não é substituído em silêncio: BLOCKED.
- Uma working tree, um writer. Writers paralelos usam worktrees próprias,
  branches próprias e write-sets sem sobreposição.
- Especialista nunca chama outro especialista nem decide globalmente sobre o
  projeto.
- Evidência determinística (teste, lint, build) tem precedência sobre
  opinião de modelo.
- Repair automático roda no máximo uma vez; se a nova revisão falhar de
  novo, escala para o orchestrator em vez de repetir.
- Requirement gate roda antes da implementação; ambiguidade que pode causar
  perda de dados, mudança arquitetural, comportamento destrutivo, problema
  de segurança ou incompatibilidade externa nunca é assumida em silêncio.
- Nenhum papel executa push, deploy, exclusão ou qualquer ação irreversível
  sem OK explícito do humano.
- Os papéis Codex (planner, code-reviewer, security-reviewer) só usam o
  saldo/limite da conta Codex/ChatGPT vinculada; limite atingido é BLOCKED
  — nunca upgrade, nunca troca de modelo (detalhe completo:
  `references/orcamento-e-lanes.md`).

## Definition of Done

Uma task é DONE quando: critérios de aceite foram atendidos, o diff
corresponde ao escopo, contracts continuam válidos, testes/lint/typecheck/
build necessários passam, findings obrigatórios foram resolvidos, nenhuma
alteração inesperada permanece, o verifier produziu evidência suficiente e
riscos restantes estão documentados. `IMPLEMENTED != DONE`.

## Estilo de resposta

Caveman, nível full, em português (`.claude/skills/caveman`): prosa terse,
baixa redundância, precisão técnica preservada. Exceções em prosa normal:
código, comandos, erros exatos, avisos de segurança, confirmação
irreversível, documentação persistida, commits, memória e relatórios. Todo
papel Claude spawnado recebe `caveman/caveman`. Desligar só mediante pedido
explícito ("normal mode").

## Contexto obrigatório do projeto

<!-- ADAPTE ESTA SEÇÃO AO SEU PROJETO. Exemplo fictício preenchido em
     examples/exemplo-api/contexto-do-projeto.md no repo do harness. -->

Todo papel respeita: nunca fazer push, deploy ou excluir dado/arquivo sem OK
explícito; nunca executar ação irreversível sem confirmação; backup antes de
qualquer operação em ambiente compartilhado ou produção.

Convenções adicionais do projeto vivem no `CLAUDE.md` (ou `AGENTS.md`
versionado) deste repositório: parsing seguro, tratamento de erro exposto ao
cliente, PII em logs, transações, etc. Os comandos literais que o verifier
pode rodar ficam em `tools/agents/project.json`; não assumir gerenciador não
confirmado (`uv`, `poetry`, ...).

## Princípio final

O harness existe para aumentar confiabilidade e controle, não para maximizar
a quantidade de agentes. Paralelismo começa na decomposição da task, não na
quantidade de agentes disponíveis; quando uma task não divide em unidades
realmente independentes, prefira execução sequencial.

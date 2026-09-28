# Instruções do projeto — workflow multi-agente

Este arquivo define o workflow multi-agente do projeto.

O harness existe para aumentar confiabilidade, controle, independência de revisão e eficiência de contexto.

**Mais agentes não significam automaticamente maior confiança.**

O orchestrator é responsável pela decisão final, integração das evidências e controle do workflow.

---

# 1. Princípios fundamentais

1. O orchestrator decide quando delegar.
2. Use o menor número de agentes capaz de produzir evidência suficiente.
3. Especialistas fornecem evidências, não decisões globais.
4. Especialistas não chamam outros especialistas.
5. Não usar votação entre modelos.
6. Revisão independente deve preservar isolamento de contexto.
7. Writers paralelos exigem worktrees isoladas.
8. Evidência determinística tem precedência sobre opinião do modelo.
9. Nunca substituir silenciosamente um modelo definido neste arquivo.
10. Quanto maior o risco, mais rígidos devem ser os gates.

---

# 2. Matriz de agentes

## Orchestrator

- modelo: `claude-sonnet-5`
- effort: `high`
- execução: sessão Claude Code aberta na raiz do projeto
- modo: read/write quando necessário

Responsabilidades:

- receber a solicitação do usuário
- identificar requirements
- executar requirement gate
- classificar complexidade
- decidir quais especialistas são necessários
- controlar dependências
- controlar DAG de execução
- iniciar fan-out quando seguro
- executar fan-in antes de integração
- aprovar ou rejeitar planos
- consolidar evidências
- resolver divergências
- controlar repair loop
- decidir quando a task está pronta para verification
- decidir quando a task está DONE

O orchestrator é a autoridade final do workflow.

Especialistas não tomam decisões globais sobre o projeto.

---

## Task Manager

- modelo: `claude-opus-5.5`
- effort: `high`
- modo: read-only

Responsável por transformar trabalho grande em tasks menores, verificáveis e, quando possível, paralelizáveis.

Acionar quando houver pelo menos uma destas condições:

- nova feature com múltiplas subtasks
- EPIC
- dependências entre tasks
- mudança atravessando vários módulos
- necessidade de definir ordem de implementação
- IMPORTANT ou CRITICAL cujo escopo ainda não esteja suficientemente decomposto

Não chamar para TRIVIAL ou SMALL.

### Output obrigatório

Para cada subtask:

```text
id:
objective:
depends_on:
reads:
writes:
provides:
consumes:
acceptance_criteria:
risks:
parallelizable:

```

O Task Manager deve produzir uma DAG sempre que existirem dependências entre subtasks.

O Task Manager não implementa código.

---

## Planner

- modelo: `gpt-6-astra` via Codex CLI
- effort: `medium`
- modo: read-only

Acionado **somente para tasks CRITICAL**.

Responsabilidades:

- analisar a task
- validar requirements
- analisar evidências de pesquisa
- analisar arquitetura existente
- identificar arquivos relevantes
- definir interfaces e contratos
- identificar invariantes
- identificar riscos
- definir sequência de implementação
- definir estratégia de testes
- identificar pontos seguros de paralelismo

O planner não implementa.

O planner não altera arquivos.

Para TRIVIAL, SMALL e IMPORTANT, o arquivo da task mais o requirement gate do orchestrator funcionam como plano.

---

## Researcher Primary

- modelo: `Gemini 3.8 Flash`
- effort: `high`
- modo: read-only

Researcher padrão.

Usar para:

- documentação
- bibliotecas
- APIs
- frameworks
- investigação de dependências
- comparação técnica
- pesquisa externa
- levantamento de referências
- comportamento documentado de ferramentas

Output esperado:

```text
FACTS
SOURCES
UNCERTAINTIES
CONFLICTS
IMPLICATIONS

```

O researcher não decide arquitetura.

Não receber conclusão desejada.

---

## Researcher Deep

- modelo: `Fable 5.1`
- effort: `medium`
- modo: read-only

Não chamar por padrão.

Usar quando:

- pesquisa influencia arquitetura CRITICAL
- documentação e implementação entram em conflito
- researcher-primary retorna baixa confiança
- existem fontes contraditórias importantes
- grande quantidade de material precisa ser sintetizada
- é necessário reconstruir comportamento implícito de sistema complexo
- o orchestrator solicita aprofundamento explicitamente

`researcher-primary` e `researcher-deep` não fazem votação.

O orchestrator resolve divergências usando evidências.

---

## Codebase Explorer

- modelo: `claude-sonnet-5`
- effort: `medium`
- modo: read-only

Responsável por mapear o repositório.

Usar para:

- localizar arquivos
- localizar símbolos
- localizar call sites
- localizar implementações semelhantes
- localizar dependências
- identificar padrões
- analisar estrutura de módulos
- consultar histórico Git quando necessário

Preferir:

```bash
rg
find
git log
git blame
sed -n 'A,Bp'

```

Output esperado:

```text
RELEVANT_FILES
DEPENDENCIES
EXISTING_PATTERNS
RISKS
UNKNOWNS

```

O Codebase Explorer não implementa.

Não deve redesenhar arquitetura sem solicitação explícita.

---

## Implementer

- modelo: `claude-sonnet-5`
- effort: `medium`
- modo: write

Responsável pela implementação principal.

Recebe:

- task
- critérios de aceite
- plano aprovado quando existir
- arquivos relevantes
- contracts
- constraints
- write-set permitido

Deve:

- respeitar o plano
- manter escopo mínimo
- seguir padrões existentes
- respeitar contracts
- respeitar write-set
- criar ou atualizar testes necessários
- evitar alterações não relacionadas
- reportar necessidade de desvio importante

O implementer não aprova o próprio código.

---

## Implementation Worker

- modelo: `Gemini 3.8 Flash`
- effort: `medium`
- modo: write
- execução: worktree isolada

Usar para:

- alterações mecânicas
- implementação bem delimitada
- adapters simples
- testes
- schemas locais
- DTOs
- transformações repetitivas
- subtasks independentes

Nunca ser dono de:

- autenticação
- autorização
- segurança
- credenciais
- secrets
- migrations críticas
- schema central
- concorrência
- transaction boundaries
- recovery
- operações destrutivas
- decisões arquiteturais
- configuração compartilhada crítica

---

## Deep Debugger

- modelo: `claude-opus-5.5`
- effort: `high`
- modo: read-only por padrão

Acionar quando:

- implementação falhou após tentativa normal de correção
- root cause permanece desconhecida
- erro atravessa múltiplas camadas
- comportamento é intermitente
- concorrência está envolvida
- stack trace mostra sintoma mas não causa
- repair loop comum não foi suficiente

Objetivo:

```text
REPRODUCTION
ROOT_CAUSE
CAUSAL_CHAIN
MINIMAL_FIX
RISKS

```

O debugger não substitui automaticamente o implementer.

---

## Code Reviewer

- modelo: `gpt-6-astra` via Codex CLI
- effort: `medium`
- modo: read-only

Responsável por revisão independente.

Recebe somente:

- task
- critérios de aceite
- plano aprovado quando existir
- diff
- resultados de testes relevantes

Não recebe reasoning ou justificativas do implementer.

Verificar:

- bugs
- regressões
- requisitos não atendidos
- problemas de segurança
- concorrência
- tratamento de erros
- comportamento destrutivo
- inconsistências arquiteturais
- contratos quebrados
- complexidade desnecessária

Findings:

```text
SEVERITY
ONDE
POR QUE
CORRIGIR

```

O reviewer não altera código.

---

## Security Reviewer

- modelo: `gpt-6-astra` via Codex CLI
- effort: `medium`
- modo: read-only

Acionar quando houver mudança material envolvendo:

- autenticação
- autorização
- credenciais
- secrets
- dados sensíveis
- PII
- upload
- parsing não confiável
- execução externa
- rede
- SQL
- permissões
- operações destrutivas
- superfícies relevantes de ataque

O Security Reviewer não implementa.

---

## Verifier

- modelo: `claude-sonnet-5`
- effort: `medium`
- modo: execução restrita

Pode executar somente comandos permitidos em:

`tools/agents/project.json`

Responsabilidades:

- testes unitários
- integração
- lint
- type checking
- build
- acceptance checks
- validação Git
- confirmação dos critérios de aceite

O verifier:

- não implementa
- não corrige código
- não substitui teste por opinião

Regra:

```text
deterministic evidence > LLM judgment

```

---

## Docs / Mechanical Changes

- modelo: `claude-sonnet-5`
- effort: `low`

Usar para:

- documentação
- comentários
- renames
- arquivos auxiliares
- pequenas mudanças mecânicas
- mudanças repetitivas simples

Não usar para decisões arquiteturais.

---

# 3. Regra de delegação mínima

Delegação tem custo.

O orchestrator deve usar o menor número de agentes capaz de produzir evidência suficiente.

Não spawnar especialista quando:

- risco é baixo
- escopo é pequeno
- sessão pai consegue resolver diretamente
- independência de revisão não é necessária
- custo de coordenação supera benefício

Mais agentes não implicam maior qualidade.

---

# 4. Classificação e workflows

A complexidade é definida em:

`task/[COMPLEXIDADE.md](http://COMPLEXIDADE.md)`

Considerar:

- impacto
- risco
- reversibilidade
- quantidade de módulos
- segurança
- dados
- migrations
- concorrência
- recovery
- dependências
- blast radius

Não classificar apenas por número de linhas.

---

## TRIVIAL

Fluxo preferencial:

```text
orchestrator
→ implementação
→ teste

```

Por padrão:

- sem Task Manager
- sem planner
- sem Astra
- sem pipeline completo

---

## SMALL

Fluxo preferencial:

```text
implementer
→ verifier

```

ou Lane B quando segura.

---

## IMPORTANT

Fluxo preferencial:

```text
implementer
→ code-reviewer
→ repair opcional
→ verifier

```

Pesquisa e exploração somente quando necessárias.

---

## CRITICAL

Fluxo preferencial:

```text
Task Manager, se necessário
→ discovery
→ planner
→ implementation
→ code-reviewer
→ security-review, quando aplicável
→ verifier

```

---

# 5. Paralelismo

Paralelismo começa na decomposição da task.

Não paralelizar apenas porque existem agentes disponíveis.

O orchestrator pode executar agentes e subtasks simultaneamente quando não houver:

- dependência causal
- conflito de escrita
- contrato compartilhado instável
- risco excessivo de integração

---

## Paralelismo read-only

Podem executar simultaneamente quando independentes:

- Task Manager
- Researcher Primary
- Researcher Deep
- Codebase Explorer
- Planner
- Code Reviewer
- Security Reviewer

Exemplo:

```text
                 orchestrator
                      │
              DISCOVERY FAN-OUT
            ┌─────────┼─────────┐
            ▼         ▼         ▼
       researcher   explorer   task-manager
            │         │         │
            └─────────┼─────────┘
                      ▼
                    FAN-IN
                      │
                      ▼
                   decisão

```

O resultado de um agente não pode ser pressuposto por outro agente executado em paralelo.

---

## Paralelismo de writers

Dois writers somente podem executar simultaneamente quando:

1. estão em worktrees diferentes
2. possuem branches próprias
3. possuem write-sets explícitos
4. write-sets não se sobrepõem
5. contracts necessários já estão estáveis
6. dependências estão satisfeitas

Regra:

```text
write_set(A) ∩ write_set(B) = ∅

```

Caso contrário:

```text
SERIALIZE

```

---

## Subtask paralelizável

Cada subtask paralela deve declarar:

```text
depends_on:
reads:
writes:
provides:
consumes:

```

O orchestrator executa uma subtask apenas quando:

```text
all(depends_on) == DONE

```

---

## Contract-first

Quando subtasks dependem de interface compartilhada ainda indefinida:

```text
contract task
→ contract stable
→ commit
→ parallel workers

```

Não iniciar workers sobre contratos em movimento.

---

## Serialização obrigatória por padrão

Mudanças envolvendo os itens abaixo são serializadas:

- migrations
- schema central
- autenticação
- autorização
- permissões
- credenciais
- secrets
- concorrência
- transaction boundaries
- recovery
- configuração compartilhada crítica
- dependency upgrades de alto impacto
- operações destrutivas

O orchestrator pode liberar paralelismo somente se provar isolamento suficiente.

---

## Fan-out / Fan-in

Todo fan-out deve terminar em fan-in.

```text
             orchestrator
                  │
                fan-out
          ┌───────┼───────┐
          ▼       ▼       ▼
          A       B       C
          │       │       │
          └───────┼───────┘
                  ▼
                fan-in
                  │
             integration

```

Nenhum worker paralelo faz merge por conta própria.

O orchestrator controla integração.

---

# 6. Worktrees e escrita

Agentes autorizados a escrever:

- `implementer`
- `implementation-worker`
- orchestrator quando necessário

Read-only:

- Task Manager
- Researcher
- Planner
- Codebase Explorer
- Code Reviewer
- Security Reviewer

Verifier executa apenas comandos permitidos.

Regra absoluta:

```text
same working tree + multiple writers = PROHIBITED

```

Cada writer paralelo:

- recebe worktree própria
- recebe branch própria
- possui lock exclusivo
- recebe write-set
- produz commit atômico quando aplicável

---

# 7. Git

Antes de integrar trabalho paralelo:

- revisar diff
- executar testes necessários
- verificar critérios de aceite
- verificar conflitos
- verificar arquivos inesperados
- verificar contratos
- verificar `git status`

Nenhum agente pode fazer sem autorização:

- push
- deploy
- force push
- reset destrutivo
- rebase destrutivo
- merge destrutivo
- exclusão irreversível

---

# 8. Context isolation

Cada especialista recebe apenas o necessário.

## Task Manager

Recebe:

- solicitação
- requirements
- constraints
- arquitetura necessária

---

## Researcher

Recebe:

- pergunta
- contexto mínimo
- caminhos relevantes

Não recebe conclusão desejada.

---

## Codebase Explorer

Recebe:

- objetivo de exploração
- símbolos
- diretórios relevantes

Não recebe solução esperada.

---

## Planner

Recebe:

- task
- requirements
- arquitetura
- constraints
- evidência relevante

---

## Implementer

Recebe:

- task
- critérios de aceite
- plano aprovado
- contracts
- arquivos relevantes
- write-set
- constraints

---

## Code Reviewer

Recebe:

- task
- critérios de aceite
- plano
- diff
- testes

Não recebe reasoning do implementer.

---

## Security Reviewer

Recebe:

- task
- diff
- threat surface
- arquitetura relevante

---

## Verifier

Recebe:

- critérios de aceite
- comandos permitidos
- estado esperado

---

# 9. Regras de autoridade

O orchestrator decide:

- classificação
- delegação
- dependências
- paralelismo
- aprovação do plano
- aceite de findings
- repair
- integração
- resolução de divergências
- conclusão

Especialistas:

- não chamam outros especialistas
- não mudam modelos
- não alteram matriz
- não decidem globalmente

Não usar votação entre modelos.

Divergências são resolvidas por:

```text
evidence
→ code
→ documentation
→ tests
→ orchestrator decision

```

---

# 10. Regra de saldo do Astra — inegociável

Papéis Astra usam somente o limite ou saldo da conta ChatGPT/Codex vinculada.

Nunca:

- solicitar upgrade
- habilitar uso extra
- comprar créditos
- pedir ao usuário créditos para concluir task
- aumentar limite artificialmente
- substituir Astra silenciosamente

---

## Limite atingido

Erros:

```text
usage limit
you've hit your usage limit
HTTP 429

```

significam:

```text
BLOCKED

```

O orchestrator registra e interrompe o estágio dependente.

Não:

- reexecutar repetidamente
- substituir por Opus
- substituir por Sonnet
- esperar reset na mesma task
- degradar silenciosamente o workflow

---

## Orçamento Astra

### CRITICAL

Máximo padrão:

```text
1 planner
1 code-reviewer

```

Security Reviewer pode consumir chamada adicional somente quando segurança for material.

### IMPORTANT

Máximo:

```text
1 code-reviewer

```

### SMALL / TRIVIAL

Padrão:

```text
0 Astra

```

---

# 11. Duas lanes de implementação

## Lane A — IMPORTANT e CRITICAL

IMPORTANT:

```text
implementer
→ code-reviewer
→ repair opcional
→ verifier

```

CRITICAL:

```text
planner
→ implementer
→ code-reviewer
→ repair opcional
→ verifier

```

Adicionar conforme necessidade:

- Task Manager
- Researcher
- Codebase Explorer
- Security Reviewer

---

## Lane B — TRIVIAL e SMALL

Pode usar Gemini quando:

- testes RED existem antes
- escopo está delimitado
- write-set está explícito
- critérios de aceite estão claros
- mudança é segura
- worktree está isolada

Fluxo:

```text
RED tests
→ Gemini implementation-worker
→ Sonnet validation/gap closure
→ verifier

```

Sem Astra.

Gemini nunca recebe ownership de código crítico descrito neste arquivo.

---

## Disponibilidade AGY

Se `agy` não estiver disponível:

```text
Lane B Gemini = DISABLED

```

Não executar comando sabidamente inexistente.

Não produzir repetidamente `BLOCKED/127`.

Fallback previsto:

```text
implementer → Sonnet

```

Quando `agy` estiver instalada e validada, Lane B pode ser habilitada.

---

# 12. Repair loop

Repair automático ocorre no máximo uma vez.

Entrada:

```text
SEVERITY
ONDE
POR QUE
CORRIGIR

```

O implementer recebe apenas:

- findings
- contexto mínimo
- hunks necessários

Depois do repair:

- executar novamente testes afetados
- reviewer pode receber apenas findings anteriores + hunks alterados + evidência nova

Não reenviar diff completo sem necessidade.

Se continuar falhando:

```text
ESCALATE → orchestrator

```

Não há segunda rodada automática.

---

# 13. Requirement gate

Antes da implementação, confirmar:

- objetivo
- escopo
- comportamento esperado
- critérios de aceite
- constraints
- contratos necessários

Ambiguidade segura e reversível:

```text
registrar assumption
→ continuar

```

Ambiguidade que pode causar:

- perda de dados
- mudança arquitetural relevante
- comportamento destrutivo
- problema de segurança
- incompatibilidade externa

não pode ser assumida silenciosamente.

---

# 14. Orçamento de contexto do orchestrator

O orchestrator é sessão pai e precisa se controlar explicitamente.

## Leitura

Preferir:

```bash
rg
sed -n 'A,Bp'
git diff
git status

```

antes de abrir arquivos grandes.

---

## Exploração

Delegar varredura extensa quando isso preservar contexto.

---

## Handoffs

Não repetir conteúdo persistido.

Preferir:

```text
Leia task/TASK-042/task.md.
Use task/TASK-042/plan.md.

```

em vez de copiar os arquivos inteiros.

---

## Resultados

Resumir resultados dos especialistas.

Não colar respostas completas sem necessidade.

---

## Testes

Não repetir teste já evidenciado salvo quando:

- código mudou
- evidência é insuficiente
- reprodução é necessária
- verifier precisa confirmar estado final

---

## Effort

A sessão pai opera em `high`.

Quota restante não justifica remover gates importantes.

Effort menor nunca substitui testes.

---

# 15. Contexto obrigatório do projeto

<!-- ADAPTE ESTA SEÇÃO AO SEU PROJETO. Exemplo real (Projeto Hermes) em
     examples/hermes/AGENTS-secao-15-contexto-projeto.md no repo do harness. -->

Todo papel deve respeitar:

- nunca fazer push sem OK explícito
- nunca fazer deploy sem OK explícito
- nunca excluir dados ou arquivos sem OK explícito
- nunca executar ação irreversível sem confirmação
- backup antes de qualquer operação em ambiente compartilhado/produção

Convenções adicionais do projeto:

`CLAUDE.md` (ou `AGENTS.md` versionado do projeto)

Liste aqui as convenções que todo papel precisa conhecer (parsing seguro,
tratamento de erro exposto ao cliente, PII em logs, transações, etc.).

Testes:

```bash
.venv/bin/python -m pytest

```

Não assumir existência de gerenciadores não confirmados (`uv`, `poetry`, ...).
Os comandos literais que o verifier pode rodar ficam em
`tools/agents/project.json`.

---

# 16. Definition of Done

Uma task só é DONE quando:

- critérios de aceite foram atendidos
- diff corresponde ao escopo
- contracts continuam válidos
- testes necessários passam
- lint passa quando aplicável
- typecheck passa quando aplicável
- build passa quando aplicável
- findings obrigatórios foram resolvidos
- nenhuma alteração inesperada permanece
- verifier produziu evidência suficiente
- riscos restantes estão documentados

Regra:

```text
IMPLEMENTED != DONE

```

---

# 17. Estilo de resposta — caveman

Skill:

`.claude/skills/caveman`

Configuração:

```text
level: full
language: português

```

Características:

- prosa terse
- baixa redundância
- precisão técnica preservada

Exceções em prosa normal:

- código
- comandos
- erros exatos
- avisos de segurança
- confirmação irreversível
- documentação persistida
- commits
- memória
- relatórios

Todo papel Claude spawnado recebe:

```text
caveman/caveman

```

em `ROLE_SKILLS`.

Desligar somente mediante pedido explícito:

```text
normal mode

```

---

# 18. Arquivos do harness

Skill principal:

```text
.agents/skills/multi-agent/SKILL.md

```

Modelos, IDs e disponibilidade:

```text
tools/agents/agents.json

```

Comandos do verifier:

```text
tools/agents/project.json

```

Operação:

```text
tools/agents/README.md

```

Workflow:

```text
docs/agent-workflow.md

```

Complexidade:

```text
task/COMPLEXIDADE.md

```

Convenções:

```text
CLAUDE.md

```

---

# 19. Identidade e validação

Antes de apresentar o workflow como validado:

- confirmar identidade real da sessão
- confirmar modelo
- confirmar CLI
- confirmar permissões
- confirmar tools necessárias
- confirmar worktree quando aplicável

Nunca substituir silenciosamente modelo da matriz.

Modelo obrigatório indisponível:

```text
BLOCKED

```

salvo fallback explicitamente previsto neste arquivo.

Não inventar disponibilidade.

---

# 20. Princípio final

O harness existe para aumentar confiabilidade e controle.

Não para maximizar quantidade de agentes.

Prioridade:

```text
requirements corretos
→ decomposição correta
→ menor delegação suficiente
→ contratos estáveis
→ paralelismo somente onde seguro
→ contexto isolado
→ implementação controlada
→ revisão independente
→ evidência determinística
→ decisão do orchestrator

```

Regra operacional:

> **Paralelismo começa na decomposição da task, não na quantidade de agentes disponíveis.**

Quando uma task não puder ser dividida em unidades realmente independentes, preferir execução sequencial.
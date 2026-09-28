# Papéis

Modelo, effort, provider e status de cada papel vêm de `tools/agents/agents.json`
— fonte única, não repetir IDs de modelo aqui. Cada papel recebe só o
contexto necessário (context isolation); "não recebe" abaixo é regra, não
detalhe opcional.

## Orchestrator

Sessão Claude Code aberta na raiz do projeto, read/write quando necessário.
É a autoridade final do workflow: recebe a solicitação, identifica
requirements, executa o requirement gate, classifica complexidade, decide
quais especialistas acionar, controla dependências e a DAG de execução,
inicia fan-out quando seguro, executa fan-in antes de integrar, aprova ou
rejeita planos, consolida evidências, resolve divergências, controla o
repair loop e decide quando a task está pronta para verification e quando
está DONE. Especialistas não tomam decisões globais sobre o projeto.

Decide sozinho: classificação, delegação, dependências, paralelismo,
aprovação do plano, aceite de findings, repair, integração, resolução de
divergências, conclusão. Especialistas não chamam outros especialistas, não
mudam modelos, não alteram a matriz, não decidem globalmente. Divergências
resolvem-se por evidência → código → documentação → testes → decisão do
orchestrator, nunca por votação entre modelos.

Orçamento de contexto próprio (sessão pai, precisa se controlar
explicitamente): preferir `rg`, `sed -n 'A,Bp'`, `git diff`, `git status`
antes de abrir arquivo grande; delegar varredura extensa quando isso
preserva contexto; em handoffs, apontar o caminho do arquivo da task (ex.:
task/TASK-042/task.md) em vez de colar o arquivo inteiro; resumir resultado
de especialista, nunca colar
resposta completa sem necessidade; não repetir teste já evidenciado salvo
se o código mudou, a evidência é insuficiente, a reprodução é necessária ou
o verifier precisa confirmar estado final. Effort menor nunca substitui
teste.

## Task Manager

Read-only. Transforma trabalho grande em subtasks menores, verificáveis e,
quando possível, paralelizáveis. Acionar com pelo menos uma condição: nova
feature com múltiplas subtasks, EPIC, dependências entre tasks, mudança
atravessando vários módulos, necessidade de ordem de implementação definida,
ou IMPORTANT/CRITICAL ainda pouco decomposto. Não chamar para TRIVIAL ou
SMALL. Não implementa código.

Recebe: solicitação, requirements, constraints, arquitetura necessária.

Output obrigatório por subtask:

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

Produz uma DAG sempre que houver dependências entre subtasks.

## Planner

Read-only, não altera arquivos. Acionado somente em tasks CRITICAL: analisa
a task, valida requirements, analisa evidência de pesquisa e arquitetura
existente, identifica arquivos relevantes, define interfaces/contratos,
identifica invariantes e riscos, define sequência de implementação e
estratégia de testes, identifica pontos seguros de paralelismo. Não
implementa. Para TRIVIAL, SMALL e IMPORTANT, o arquivo da task mais o
requirement gate do orchestrator já funcionam como plano.

Recebe: task, requirements, arquitetura, constraints, evidência relevante.

Output: GOAL; CURRENT STATE; PROPOSED DESIGN; FILES TO CREATE; FILES TO
MODIFY; IMPLEMENTATION STEPS; TEST STRATEGY; RISKS; ASSUMPTIONS; ACCEPTANCE
CRITERIA.

## Researcher Primary

Read-only. Researcher padrão: documentação, bibliotecas, APIs, frameworks,
investigação de dependências, comparação técnica, pesquisa externa,
levantamento de referências, comportamento documentado de ferramentas. Não
decide arquitetura, não recebe conclusão desejada.

Recebe: pergunta, contexto mínimo, caminhos relevantes.

Output: FACTS; SOURCES; UNCERTAINTIES; CONFLICTS; IMPLICATIONS.

## Researcher Deep

Read-only. Não chamar por padrão; usar quando a pesquisa influencia
arquitetura CRITICAL, documentação e implementação conflitam, o
researcher-primary volta com baixa confiança, há fontes contraditórias
importantes, é preciso sintetizar muito material, é preciso reconstruir
comportamento implícito de sistema complexo, ou o orchestrator pede
aprofundamento explicitamente. `researcher-primary` e `researcher-deep`
nunca fazem votação entre si; o orchestrator resolve divergências com
evidência. Mesmo contrato de input/output do researcher-primary.

## Codebase Explorer

Read-only. Mapeia o repositório: localizar arquivos, símbolos, call sites,
implementações semelhantes, dependências, padrões, estrutura de módulos,
histórico Git quando necessário. Preferir `rg`, `find`, `git log`,
`git blame`, `sed -n 'A,Bp'`. Não implementa, não redesenha arquitetura sem
pedido explícito.

Recebe: objetivo de exploração, símbolos, diretórios relevantes. Não recebe
solução esperada.

Output: RELEVANT_FILES; DEPENDENCIES; EXISTING_PATTERNS; RISKS; UNKNOWNS.

## Implementer

Write. Implementação principal. Deve respeitar o plano, manter escopo
mínimo, seguir padrões existentes, respeitar contracts e write-set, criar
ou atualizar testes necessários, evitar alterações não relacionadas e
reportar necessidade de desvio importante. Não aprova o próprio código.

Recebe: task, critérios de aceite, plano aprovado quando existir, arquivos
relevantes, contracts, constraints, write-set permitido.

## Implementation Worker

Write, em worktree isolada. Usar para alterações mecânicas, implementação
bem delimitada, adapters simples, testes, schemas locais, DTOs,
transformações repetitivas, subtasks independentes — só lane B. Nunca dono
de: autenticação, autorização, segurança, credenciais, secrets, migrations
críticas, schema central, concorrência, transaction boundaries, recovery,
operações destrutivas, decisões arquiteturais, configuração compartilhada
crítica.

## Deep Debugger

Read-only por padrão. Acionar quando: a implementação falhou após tentativa
normal de correção, a root cause segue desconhecida, o erro atravessa
múltiplas camadas, o comportamento é intermitente, há concorrência
envolvida, o stack trace mostra sintoma mas não causa, ou o repair loop
comum não bastou. Não substitui automaticamente o implementer.

Output: REPRODUCTION; ROOT_CAUSE; CAUSAL_CHAIN; MINIMAL_FIX; RISKS.

## Code Reviewer

Read-only, revisão independente. Não altera código, não recebe reasoning ou
justificativa do implementer — só task, critérios de aceite, plano aprovado
quando existir, diff e resultados de teste relevantes. Verifica: bugs,
regressões, requisitos não atendidos, problemas de segurança, concorrência,
tratamento de erro, comportamento destrutivo, inconsistência arquitetural,
contrato quebrado, complexidade desnecessária.

Findings, exatamente quatro campos por item: SEVERITY (CRITICAL|HIGH|MEDIUM
|LOW); ONDE (arquivo:linha); POR QUE (uma frase); CORRIGIR (ação concreta).
Sem problema, declarar isso.

## Security Reviewer

Read-only, mesmo formato de findings do code reviewer. Acionar quando a
mudança envolve materialmente: autenticação, autorização, credenciais,
secrets, dados sensíveis/PII, upload, parsing não confiável, execução
externa, rede, SQL, permissões, operações destrutivas ou outra superfície
de ataque relevante. Não implementa.

Recebe: task, diff, threat surface, arquitetura relevante.

## Verifier

Execução restrita: só comandos permitidos em `tools/agents/project.json`.
Responsável por testes unitários, integração, lint, type checking, build,
acceptance checks, validação Git, confirmação dos critérios de aceite. Não
implementa, não corrige código, não substitui teste por opinião — regra:
evidência determinística > opinião de LLM.

Recebe: critérios de aceite, comandos permitidos, estado esperado.

Output: VERDICT PASS|FAIL|BLOCKED; REQUIREMENTS CHECKED; TESTS EXECUTED;
RESULTS; UNVERIFIED ITEMS; FAILURES; FINAL EVIDENCE. O status do envelope
indica só a execução do provider; PASS no envelope com VERDICT FAIL não
aprova a implementação.

## Docs / Mechanical

Write, effort baixo. Usar para documentação, comentários, renames, arquivos
auxiliares, pequenas mudanças mecânicas, mudanças repetitivas simples. Não
usar para decisões arquiteturais.

## Contrato comum de implementação

`implementer`, `implementation-worker` e `docs-mechanical` reportam:
IMPLEMENTATION SUMMARY; FILES CREATED; FILES MODIFIED; TESTS ADDED; TESTS
EXECUTED; RESULTS; DEVIATIONS FROM PLAN; KNOWN LIMITATIONS.

# Paralelismo, worktrees e git

Paralelismo começa na decomposição da task, não porque existem agentes
disponíveis. O orchestrator só executa agentes/subtasks em simultâneo
quando não há dependência causal, conflito de escrita, contrato
compartilhado instável, ou risco excessivo de integração. O resultado de um
agente nunca pode ser pressuposto por outro agente rodando em paralelo.

## Paralelismo read-only

Podem rodar ao mesmo tempo, se independentes entre si: Task Manager,
Researcher Primary, Researcher Deep, Codebase Explorer, Planner, Code
Reviewer, Security Reviewer. Fluxo típico de discovery: orchestrator faz
fan-out para dois ou três desses papéis, espera todos retornarem (fan-in) e
só então decide.

## Paralelismo de writers

Dois writers só rodam ao mesmo tempo quando: estão em worktrees diferentes,
têm branches próprias, têm write-sets explícitos, os write-sets não se
sobrepõem (`write_set(A) ∩ write_set(B) = ∅`), os contracts necessários já
estão estáveis, e as dependências estão satisfeitas. Caso qualquer condição
falhe, serialize.

## Subtask paralelizável

Cada subtask paralela declara `depends_on`, `reads`, `writes`, `provides`,
`consumes`. O orchestrator só executa uma subtask quando todo `depends_on`
está DONE.

## Contract-first

Quando subtasks dependem de uma interface compartilhada ainda indefinida:
task de contrato → contrato estável → commit → workers em paralelo. Não
iniciar workers sobre contrato em movimento.

## Serialização obrigatória por padrão

Sempre serializar mudanças em: migrations, schema central, autenticação,
autorização, permissões, credenciais, secrets, concorrência, transaction
boundaries, recovery, configuração compartilhada crítica, dependency
upgrades de alto impacto, operações destrutivas. O orchestrator só libera
paralelismo aqui se provar isolamento suficiente.

## Fan-out / fan-in

Todo fan-out termina em fan-in antes da integração; nenhum worker paralelo
faz merge por conta própria — o orchestrator controla a integração.

## Worktrees e escrita

Autorizados a escrever: `implementer`, `implementation-worker`, e o
orchestrator quando necessário. Read-only: Task Manager, Researcher,
Planner, Codebase Explorer, Code Reviewer, Security Reviewer. Verifier só
executa os comandos permitidos em `tools/agents/project.json`. Regra
absoluta: mesma working tree com múltiplos writers é proibido. Cada writer
paralelo recebe worktree própria, branch própria, lock exclusivo, write-set
declarado, e produz commit atômico quando aplicável.

## Git

Antes de integrar trabalho paralelo: revisar diff, rodar os testes
necessários, verificar critérios de aceite, verificar conflitos, verificar
arquivos inesperados, verificar contracts, verificar `git status`. Nenhum
agente faz sem autorização explícita: push, deploy, force push, reset
destrutivo, rebase destrutivo, merge destrutivo, exclusão irreversível.

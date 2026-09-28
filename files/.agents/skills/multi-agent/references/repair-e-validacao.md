# Requirement gate, repair loop e validação

## Requirement gate

Antes da implementação, confirmar: objetivo, escopo, comportamento
esperado, critérios de aceite, constraints, contratos necessários.
Ambiguidade segura e reversível: registrar a assumption e continuar.
Ambiguidade que pode causar perda de dados, mudança arquitetural relevante,
comportamento destrutivo, problema de segurança ou incompatibilidade
externa nunca pode ser assumida em silêncio.

## Repair loop

Repair automático roda no máximo uma vez. Entrada: os quatro campos de
finding (SEVERITY, ONDE, POR QUE, CORRIGIR — ver `references/papeis.md`). O
implementer recebe só os findings, o contexto mínimo e os hunks
necessários — nunca o diff inteiro sem necessidade. Depois do repair:
rodar de novo os testes afetados; o reviewer pode receber apenas os
findings anteriores, os hunks alterados e a evidência nova. Se a segunda
revisão ainda reprovar, escala para o orchestrator — não há segunda rodada
automática.

## Regras de autoridade e divergências

O orchestrator decide: classificação, delegação, dependências, paralelismo,
aprovação de plano, aceite de findings, repair, integração, resolução de
divergências, conclusão. Especialistas não chamam outros especialistas, não
mudam modelos, não alteram a matriz de papéis, não decidem globalmente.
Nunca usar votação entre modelos: divergências resolvem-se com evidência →
código → documentação → testes → decisão do orchestrator.

## Identidade e validação

Antes de apresentar o workflow como validado, confirmar: identidade real da
sessão, modelo, CLI, permissões, tools necessárias, worktree quando
aplicável. Nunca substituir silenciosamente o modelo da matriz. Modelo
obrigatório indisponível é BLOCKED, salvo fallback explicitamente previsto
neste harness (ver `references/orcamento-e-lanes.md`). Não inventar
disponibilidade.

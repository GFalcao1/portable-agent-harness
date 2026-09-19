# Portable Harness Implementation Plan

> Execute with superpowers:subagent-driven-development; user approved execution.

**Goal:** Um harness instalável com Claude ou Codex como sessão principal.
**Architecture:** Manter wrapper Python; configuração por projeto; instalador com
blocos gerenciados e descoberta compartilhada de skills.
**Tech Stack:** Python 3.10+, bash, pytest, CLIs Claude/Codex.
**Spec:** ../specs/2026-09-15-portable-harness.md

## Constraints and rulings

- Sem commits: o Git ancestral pertence à pasta pessoal; trabalhar neste diretório.
- Usuário autorizou implementação, subagents menores e remoção após backup.
- Um implementador delegado escreve apenas instalador/testes; coordenador edita
  wrapper/documentação em arquivos distintos.
- Skills upstream permanecem intactas; workflow local define contexto e precedência.

## Task 1: instalação portátil

Files: install.sh, install.py, tests/test_install.py.
Interface: `bash install.sh TARGET [--skills-source PATH ...] [--dry-run]`.
Fontes locais descobertas nos caches Claude/Codex; parâmetros apontam para roots
de skills de checkouts upstream. Instalar payload de files/; mesclar AGENTS.md e
CLAUDE.md por bloco; copiar skills com recursos; pré-validar colisões antes de
escrever. Gerar manifesto com hashes/proveniência. Reinstalação idempotente.

- [ ] Testar projeto com instruções existentes, repetição, colisão, dry-run,
  skills em ambos consumidores, raiz Git e worktree.
- [ ] Implementar sem shell eval; rejeitar symlinks de destino perigosos.
- [ ] Executar `python3 -m pytest agent-harness/tests/test_install.py -q`.

## Task 2: delegação e instruções

Files: files/tools/agents/delegate.py, agents.json, project.json;
files/tests/test_agent_delegation.py; README.md e instruções em files/.
Interface: `delegate.py --agent ROLE [--root PATH] [--test-suite NAME]`.
Adicionar configuração de comandos em project.json e papéis configuráveis;
ambos providers atendem papéis compatíveis. Manter lock e timeout.

- [ ] Testar --root, configuração inválida, skills locais e Codex escritor.
- [ ] Restaurar --root; resolver skills por projeto; incluir skills nos prompts
  Codex e plugins Claude; aplicar sandbox conforme papel.
- [ ] Remover regras Sonnet/Gemini obrigatórias e referências ao projeto original.
- [ ] Executar suíte completa, revisão independente e instalação de integração.

## Task 3: consolidar

- [ ] Criar e verificar tar.gz das duas pastas originais antes de mudanças.
- [ ] Após validação, remover somente multi-agent-workflow/.
- [ ] Registrar testes, limitações e comando de instalação no README.

# Harness portátil — desenho aprovado

O usuário aprovou manter `agent-harness/` e iniciar a sessão por Claude ou Codex.
O coordenador é a sessão atual; não existe modelo obrigatório para ela.

Preservar adapters CLI, envelopes JSON, timeouts, locks e testes existentes.
Adicionar seleção explícita de raiz/worktree e configuração de modelos e testes
por projeto. Gemini deixa de ser requisito do fluxo padrão (adapter legado
pode permanecer opcional). Não substituir modelos silenciosamente.

Instalar instruções comuns via blocos delimitados em AGENTS.md e CLAUDE.md,
preservando conteúdo do projeto. Skills upstream são copiadas de instalações
locais ou checkouts fornecidos, com recursos completos e proveniência; ficam
descobertas em `.agents/skills` e `.claude/skills`. Não instalar hooks globais.
Superpowers coordena processo; Matt Pocock contribui técnicas por tarefa.
Skills de coordenação não são atribuídas a especialistas sem subdelegação.

Instalação repetível sem sobrescrever modificações locais; pré-verificar colisões.
Configuração local excluída do Git, inclusive worktrees; arquivos de instruções
já rastreados continuam rastreados. Python 3.10+, macOS/Linux, sem daemon.

Validar testes herméticos de providers e instalação em repositórios temporários.
Arquivar as duas versões originais e verificar o arquivo antes de remover a
pasta redundante. Não afirmar autenticação/modelos remotos validados por mocks.

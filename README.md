# Portable Agent Harness

Instalador de um workflow multi-agente para Claude Code (com Codex CLI e AGY
como providers auxiliares). Este repositório **não é o workflow em si**: é o
empacotamento. O que ele instala num projeto alvo é a matriz de 12 papéis
(orchestrator + task-manager, planner, researcher-primary, researcher-deep,
codebase-explorer, implementer, implementation-worker, deep-debugger,
code-reviewer, security-reviewer, verifier, docs-mechanical), cada um preso a
um modelo, effort, provider e conjunto de tools, mais o wrapper
`tools/agents/delegate.py` que spawna os papéis com argv travado, aplica lock
de escrita e devolve um veredito `PASS | FAIL | BLOCKED` em JSON.

Tudo que é instalado é **config pessoal, nunca versionada** no projeto alvo:
o instalador escreve um bloco em `.git/info/exclude` e mantém um manifesto
em `.harness/manifest.json` para reinstalar/atualizar de forma idempotente.

## Estrutura deste repositório

| Caminho | O que é |
|---|---|
| `agent-harness` | Comando global (symlink no `PATH`); acha a pasta do clone sozinho |
| `install.py` / `install.sh` | Instalador (copia `files/` para o alvo, symlinks, exclude, manifesto) |
| `install-worktree-hook.sh` | Instala o hook `post-checkout` que propaga o harness para worktrees novas |
| `fetch-skills.sh` | Baixa as skills externas (caveman, superpowers, mattpocock-skills). Passo separado, com rede |
| `files/` | Payload instalado no projeto (ver tabela abaixo) |
| `skills/caveman/` | As 6 skills `caveman*` vendorizadas (copiar pra `~/.claude/skills/` ou `.claude/skills/` do projeto) |
| `skills/superpowers/`, `skills/mattpocock-skills/` | Coleções vendorizadas (só `skills/` + LICENSE MIT + VERSION), no layout que `install.py --skills-source` aceita. Permitem instalação 100% offline |
| `git-hooks/post-checkout` | O hook em si |
| `examples/exemplo-api/` | Exemplo fictício preenchido: `project.json`, `COMPLEXIDADE.md`, contexto obrigatório do projeto |
| `tests/` | Testes do instalador e gates da documentação (tamanho do `AGENTS.md`, fonte única de modelos, caminhos válidos) |
| `docs/superpowers/` | Spec e plano originais do harness (histórico) |
| `docs/decisions/` | Registros de decisão (ex.: por que os papéis Claude seguem no wrapper e não como subagentes nativos) |

### O que vai para o projeto alvo (`files/`)

| Arquivo | Papel |
|---|---|
| `AGENTS.md` → bloco gerenciado em `AGENTS.md` e `CLAUDE.local.md` | Núcleo curto sempre carregado pelo orchestrator: princípios, lanes, invariantes, DoD |
| `.agents/skills/multi-agent/SKILL.md` (+ symlink `.claude/skills/multi-agent`) | Carregada só na hora de delegar: como escolher papel, delegar e ler o retorno |
| `.agents/skills/multi-agent/references/` | Detalhe sob demanda: papéis, paralelismo, orçamento e lanes, repair e validação |
| `tools/agents/agents.json` | Roster fixo e **fonte única** de modelo, effort, provider, modo e status por papel |
| `tools/agents/delegate.py` | Wrapper que spawna cada papel e registra o uso em `.harness/usage.jsonl` |
| `tools/agents/usage_report.py` | Relatório de custo/tokens/status/duração por papel a partir do `usage.jsonl` |
| `tools/agents/project.json` | Comandos literais que o verifier pode executar (**adapte**; seed: criado só se faltar, reinstalar preserva) |
| `tools/agents/README.md` | Operação, permissões, concorrência, limites conhecidos |
| `tests/` | Testes herméticos do wrapper (+ teste ao vivo opcional de isolamento de contexto) |
| `docs/agent-workflow.md` | Design writeup e histórico de emendas |
| `task/COMPLEXIDADE.md` | Gate de complexidade que decide a lane (**adapte**; seed: criado só se faltar, reinstalar preserva) |

`files/.codex/config.toml` não é instalado; é só lembrete de configuração do Codex.

## Instalação numa máquina nova

### 1. Clonar o harness

Na pasta que você preferir — nada no harness depende de onde ele mora:

```sh
git clone https://github.com/GFalcao1/portable-agent-harness.git
cd portable-agent-harness
```

### 2. Comando global (opcional)

O script `agent-harness` na raiz do repo descobre sozinho onde o clone está,
então basta um symlink para ele em qualquer diretório do seu `PATH`:

```sh
ln -s "$PWD/agent-harness" ~/.local/bin/agent-harness   # ou outro dir do PATH
agent-harness home   # imprime o caminho do clone
```

Subcomandos: `agent-harness <alvo> [flags]` (instalador),
`agent-harness fetch-skills`, `agent-harness hook <alvo>`, `agent-harness home`.
Se mover o clone de pasta, refaça o symlink. Sem o comando global, rode os
scripts direto do clone (`python3 install.py`, `./fetch-skills.sh`,
`./install-worktree-hook.sh`).

### 3. CLIs e skills

Pré-requisitos por provider (ver `files/tools/agents/agents.json`):

- `claude` autenticado (task-manager, researcher-deep, codebase-explorer, implementer, deep-debugger, security-reviewer, verifier, docs-mechanical)
- `codex` autenticado com acesso ao modelo definido em `agents.json` (planner, code-reviewer). Só gasta o saldo da conta; limite atingido = `BLOCKED`, nunca troca de modelo
- `agy` (Gemini) — opcional; sem ele, `researcher-primary` e `implementation-worker` ficam `BLOCKED` e o fallback é o implementer

Skills — duas opções:

**(a) Offline, com as coleções vendorizadas neste repo** (recomendado numa máquina nova):

```sh
cp -R "$(agent-harness home)"/skills/caveman/* ~/.claude/skills/
# superpowers e mattpocock-skills entram no passo 4 via --skills-source
```

**(b) Online, versões mais novas dos upstreams:**

```sh
agent-harness fetch-skills            # caveman global + plugins superpowers/mattpocock-skills
agent-harness fetch-skills /caminho/projeto   # idem + caveman dentro do projeto
```

`delegate.py` resolve cada skill de `ROLE_SKILLS` primeiro em `.agents/skills`
e `.claude/skills` do projeto, depois no cache de plugins
(`~/.claude/plugins/cache/claude-plugins-official/`). Skill declarada e ausente
= `BLOCKED`, sem fallback silencioso.

### 4. Instalar no projeto

Offline (opção a — vendoriza superpowers + mattpocock-skills em `.harness/skills/` e
symlinka cada skill em `.agents/skills/` e `.claude/skills/` do projeto):

```sh
cd /caminho/projeto
HH="$(agent-harness home)"
agent-harness . --claude-instructions CLAUDE.local.md \
  --skills-source "$HH/skills/superpowers" --skills-source "$HH/skills/mattpocock-skills"
agent-harness hook .        # hook post-checkout p/ worktrees
```

Online (opção b — coleções já no cache de plugins, nada vendorizado no projeto):

```sh
cd /caminho/projeto
agent-harness . --no-skills --claude-instructions CLAUDE.local.md
agent-harness hook .
```

Flags úteis: `--dry-run`, `--no-skills`, `--skills-source PATH` (repetível),
`--claude-instructions ARQ`. Sem `--skills-source` e sem `--no-skills`, o
instalador procura as coleções no cache de plugins e falha com erro claro se
não achar — nunca baixa nada sozinho.

O instalador recusa sobrescrever arquivo não gerenciado e é idempotente
contra o próprio manifesto.

### 5. Adaptar ao projeto (obrigatório)

1. `tools/agents/project.json` — uma entrada por suíte que o verifier pode rodar. Comando literal, sem shell.
2. `task/COMPLEXIDADE.md` — piso por área do repositório + catálogo de tasks. Sem isso a lane vira opinião.
3. Seção "Contexto obrigatório do projeto" de `CLAUDE.local.md`/`AGENTS.md` — regras operacionais do projeto (produção, backup, convenções).
4. `ROLE_SKILLS` / `ROLE_OUTPUT_CEILING` em `delegate.py` se precisar mudar skills ou teto de linhas por papel.

O harness não traz suítes de teste embutidas: `--test-suite X` sem `X` declarado em `project.json` devolve `BLOCKED`.

Exemplo fictício preenchido em `examples/exemplo-api/`.

### 6. Sanity check

```sh
python3 tools/agents/delegate.py --agent orchestrator --smoke < /dev/null   # BLOCKED esperado
python3 -m pytest tests -q                                                  # suíte do wrapper
echo "Return exactly: OK" | python3 tools/agents/delegate.py --agent codebase-explorer --smoke
echo "Return exactly: OK" | python3 tools/agents/delegate.py --agent code-reviewer --smoke   # gasta saldo do Codex
```

## Medir o uso

Cada chamada do wrapper grava uma linha em `.harness/usage.jsonl` no projeto (papel, modelo, status,
duração, tokens e custo quando o provider informa — nunca o texto da task). Para ver quanto cada papel
custa e quantas vezes fica `BLOCKED`:

```sh
python3 tools/agents/usage_report.py                  # tabela por papel
python3 tools/agents/usage_report.py --since 2026-10-01 --json
```

Desligar: `HARNESS_USAGE_LOG=0`. O Codex não informa custo em dólar (só tokens).

## Regras que não mudam

- Orchestrator é a sessão aberta à mão; o wrapper nunca o spawna.
- Modelo indisponível ou saldo esgotado = `BLOCKED`. Sem troca silenciosa.
- Dois writers na mesma árvore = proibido (lock do wrapper + worktrees).
- Evidência determinística (testes, lint) > opinião de modelo.
- Nada de push/deploy/exclusão sem OK humano explícito.

Detalhes: `files/AGENTS.md` (regras), `files/tools/agents/README.md`
(operação), `files/docs/agent-workflow.md` (design).

## Testes

```sh
python3 -m pytest -q tests files/tests      # instalador, gates de docs e wrapper
HARNESS_LIVE=1 python3 -m pytest -q files/tests/test_context_isolation.py   # ao vivo, modelos baratos
```

O teste ao vivo chama `claude` e `codex` de verdade (Haiku e o modelo barato do Codex, ajustáveis por
`HARNESS_LIVE_CLAUDE_MODEL` / `HARNESS_LIVE_CODEX_MODEL`) e confirma que subagentes não herdam
`CLAUDE.md`, `CLAUDE.local.md` nem `AGENTS.md`. Rode depois de atualizar qualquer CLI.

## Limites conhecidos

- POSIX only; no Windows o wrapper devolve `BLOCKED`.
- O lock de escrita só cobre chamadas via wrapper, não editores externos.
- Nada verifica o effort do próprio orchestrator.
- Flags de CLI muito específicas (`--plugin-dir`, `--restricted`, `project_doc_max_bytes=0`, `agy --mode accept-edits`); reconferir após upgrade de qualquer CLI com o teste ao vivo.
- Subagentes não veem as instruções do projeto (por design): o handoff do orchestrator precisa levar o contexto necessário.

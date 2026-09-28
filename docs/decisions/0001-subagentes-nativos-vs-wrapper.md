# 0001 — Subagentes nativos do Claude Code vs. `delegate.py`

## Contexto

Os 7 papéis Claude (`task-manager`, `researcher-deep`, `codebase-explorer`,
`implementer`, `deep-debugger`, `verifier`, `docs-mechanical`) hoje rodam
como processos `claude --print` separados, disparados por
`tools/agents/delegate.py` com argv travado (`--model`, `--effort`,
`--tools`, `--allowedTools`, `--permission-mode`, `--restricted`,
`--strict-mcp-config`, `--plugin-dir` com skills escopadas). O Claude Code
também tem um mecanismo nativo de agentes (`--agent`/`--agents` na CLI,
arquivos `.claude/agents/*.md`, selecionáveis via `Task` na própria sessão).
Cabe perguntar se vale migrar os 7 papéis para esse mecanismo nativo.

## Opções

1. **Manter o wrapper** — papéis Claude continuam como processos
   `claude --print` spawnados pelo `delegate.py`.
2. **Migrar para subagentes nativos** — usar `.claude/agents/*.md` e o
   `Task` tool, eliminando o processo separado por invocação.
3. **Híbrido** — papéis somente-leitura migram para nativo; os writer
   roles continuam no wrapper, que hoje garante o lock de escrita mútuo.

## O que o wrapper garante hoje que os nativos talvez não garantam

Verificado via `claude --help` e o `claude-code-settings.schema.json` local
(extensão VS Code instalada). Onde não achamos confirmação local, marcamos
"a verificar" em vez de assumir.

* **Lock de escrita** (`delegate.py::writer_lock`, `flock` de arquivo):
  impede `implementer`/`docs-mechanical` na mesma árvore ao mesmo tempo.
  Sem evidência local de equivalente em `Task` nativo — **a verificar**.
* **Contrato JSON PASS/FAIL/BLOCKED**: normalização própria do wrapper,
  com BLOCKED distinto de FAIL para limite de uso/erro de auth.
  `--output-format stream-json`/`json` existe nativamente, mas o
  tri-estado é lógica do wrapper — **a verificar** se um subagente nativo
  reporta isso ao orquestrador sem reimplementar o parser.
* **Argv travado por papel** (`--tools`/`--allowedTools` fixos em
  `ROLE_TOOLS`/`PERMISSION_MODES`): o settings schema confirma que a
  propriedade `agent` "Applies the agent's system prompt, tool
  restrictions, and model" — nativo restringe tools/model por agente, mas
  o frontmatter exato de `.claude/agents/*.md` (campos aceitos, herda
  `--restricted`?) não foi verificado — **a verificar**.
* **`--restricted`** (confirmado via `--help`): remove Bash/execução de
  código e WebFetch a menos que listados, ignora settings de
  usuário/projeto/local, confina tools de arquivo, recusa
  `bypassPermissions`. Sem confirmação de que `Task` herde esse modo —
  **a verificar**.
* **Tools por papel via skills isoladas** (`build_skill_plugin`, plugin
  efêmero por invocação): sem evidência local de equivalente nativo.
* **Effort por papel** (`--effort` fixo, validado em `validate_agents`):
  schema confirma `model` fixável por agente nativo; `effort` fixo por
  subagente não foi confirmado — **a verificar**.

## Decisão

Manter o wrapper para os 7 papéis Claude até haver dados de uso reais.
Nenhuma garantia acima tem confirmação local de equivalente nativo
suficiente para abrir mão do lock de escrita e do contrato
PASS/FAIL/BLOCKED hoje testados (`files/tests/test_agent_delegation.py`).

## Como medir

Usar `tools/agents/usage_report.py` sobre `.harness/usage.jsonl` (campos:
`ts, agent, provider, model, status, smoke, duration_s, exit_code,
input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
cost_usd`, gravado por `delegate.py::log_usage`): custo/tokens somados por
papel, taxa de BLOCKED (`blocked / calls`) e duração mediana
(`median_duration_s`), tudo por papel.

## Critérios para revisitar

* Papel Claude com >30 chamadas reais e taxa de BLOCKED nativo (limite de
  conta/permissão, não bug de prompt) abaixo de 2%.
* Custo por chamada do wrapper (overhead do processo `claude --print` +
  plugin efêmero) mensuravelmente maior que o de um `Task` equivalente,
  uma vez medido diretamente — hoje `usage_report.py` só mede o resultado.
* Confirmação local (não mais "a verificar") de lock de escrita nativo
  equivalente, ou de que os writer roles toleram orquestração serializada
  sem lock de arquivo.

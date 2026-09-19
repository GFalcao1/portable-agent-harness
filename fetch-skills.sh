#!/usr/bin/env bash
# Baixa as skills que o harness usa, para uma máquina nova.
#
# Passo explícito e revisável — nunca roda sozinho dentro do install.py.
# install.py só copia de fontes locais já confiadas (cache de plugin ou
# --skills-source); download de rede é decisão separada, feita aqui.
#
# Serve Claude Code CLI e Codex CLI ao mesmo tempo: ambos leem o mesmo
# SKILL.md em disco (delegate.py resolve em .agents/skills, .claude/skills
# ou no cache de plugins, sem distinguir qual CLI vai processar depois).
# O AGY (Gemini) fica de fora por desenho — ROLE_SKILLS não lista
# implementer-bulk: dado de tarefa não deve expandir em slash-command.
#
# Uso:
#   ./fetch-skills.sh                  # só escopo global (~/.claude)
#   ./fetch-skills.sh /caminho/projeto # global + caveman também no projeto
set -euo pipefail

PROJECT="${1:-}"
# -s é variádico: nomes separados por espaço, nunca por vírgula (vírgula faz
# a CLI ler tudo como um único nome inexistente e falhar com exit 1).
CAVEMAN_SKILLS=(caveman caveman-commit caveman-compress caveman-help caveman-review caveman-stats)

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: '$1' não encontrado no PATH — instale antes de continuar." >&2
    exit 1
  }
}

require npx
require claude

echo "== caveman (global) =="
npx -y skills add JuliusBrussee/caveman -g -a claude-code -y -s "${CAVEMAN_SKILLS[@]}"

if [ -n "$PROJECT" ]; then
  [ -d "$PROJECT" ] || { echo "error: projeto não existe: $PROJECT" >&2; exit 1; }
  echo "== caveman (projeto: $PROJECT) =="
  (cd "$PROJECT" && npx -y skills add JuliusBrussee/caveman -a claude-code -y -s "${CAVEMAN_SKILLS[@]}")
fi

echo "== marketplace claude-plugins-official (idempotente) =="
claude plugin marketplace add anthropics/claude-plugins-official

echo "== superpowers (plugin, escopo usuário) =="
claude plugin install superpowers@claude-plugins-official

echo "== mattpocock-skills (plugin, escopo usuário) =="
claude plugin install mattpocock-skills@claude-plugins-official 2>&1 \
  | grep -v "already at the latest version" || true

echo
echo "Pronto. Skills resolvidas em runtime por tools/agents/delegate.py:"
echo "  - caveman/caveman            -> ~/.claude/skills/caveman (+ projeto, se passado)"
echo "  - mattpocock-skills/engineering/tdd -> ~/.claude/plugins/cache/claude-plugins-official/mattpocock-skills"
echo "  - superpowers/executing-plans        -> ~/.claude/plugins/cache/claude-plugins-official/superpowers"
echo
echo "Depois: ./install.sh /caminho/projeto --no-skills --claude-instructions CLAUDE.local.md"

#!/usr/bin/env bash
# Instala o hook post-checkout no repo alvo. O hook symlinka o bloco
# "portable-agent-harness" do .git/info/exclude (mais .venv) para dentro de
# worktrees novas criadas com `git worktree add` — sem ele, delegate.py --root
# <worktree> volta BLOCKED (skill não encontrada / project.json ausente).
#
# Uso: ./install-worktree-hook.sh /caminho/projeto
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:?uso: $0 /caminho/projeto}"
HOOKS_DIR="$(git -C "$TARGET" rev-parse --git-path hooks)"
case "$HOOKS_DIR" in /*) ;; *) HOOKS_DIR="$TARGET/$HOOKS_DIR" ;; esac
DST="$HOOKS_DIR/post-checkout"
if [ -e "$DST" ] && ! grep -q 'portable-agent-harness' "$DST"; then
  echo "error: já existe um post-checkout não gerenciado em $DST — integre manualmente." >&2
  exit 1
fi
mkdir -p "$HOOKS_DIR"
cp "$HERE/git-hooks/post-checkout" "$DST"
chmod +x "$DST"
echo "hook instalado em $DST"

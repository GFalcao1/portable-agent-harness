# Contexto obrigatório do projeto — exemplo preenchido

Exemplo fictício de como preencher a seção "Contexto obrigatório do projeto"
das instruções (`AGENTS.md`/`CLAUDE.md`) para um projeto real. Este arquivo
descreve a **Exemplo API**: uma API HTTP de empréstimo de livros (FastAPI +
PostgreSQL + Redis), com um único ambiente de produção.

Todo papel deve respeitar:

- ambiente único é produção, atrás de um load balancer interno
- backup do banco antes de qualquer deploy (`scripts/backup_db.sh`, gera
  dump em `backups/AAAAMMDD-HHMMSS.sql.gz`)
- nunca fazer push sem OK explícito do usuário
- nunca fazer deploy sem OK explícito do usuário
- nunca excluir dados, tabelas ou arquivos sem OK explícito
- nunca executar migration destrutiva (`DROP`, `ALTER ... DROP COLUMN`) sem
  confirmação e backup recente
- nunca rodar comando contra o banco de produção fora de um script revisado

Convenções adicionais:

- código em `src/`, testes em `tests/`, migrations em `migrations/`
  (Alembic)
- toda rota nova precisa de teste de integração em `tests/test_routes_*.py`
- erros para o cliente usam `ApiError` (nunca `str(exception)` cru na
  resposta)
- segredos só em variáveis de ambiente (`.env`, nunca comitado); use
  `.env.example` como referência de quais existem
- logs estruturados via `core/logging.py`; nunca logar `senha`, `token` ou
  corpo de requisição de autenticação

Testes:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

Suítes nomeadas (usadas pelo verifier via `--test-suite`, ver
`tools/agents/project.json` deste exemplo):

- `unit` — testes de domínio, sem banco
- `integration` — sobe um Postgres de teste via `docker compose`, roda as
  rotas ponta a ponta
- `lint` — `ruff check .`

Não assumir existência de `uv`. Não assumir que o ambiente já tem o venv
criado — o comando acima cria e popula `.venv/` do zero.

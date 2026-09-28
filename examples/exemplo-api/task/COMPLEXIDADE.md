# Catálogo de complexidade — Exemplo API (fictício)

Exemplo preenchido de `task/COMPLEXIDADE.md` para a **Exemplo API**, uma API
de empréstimo de livros (FastAPI + PostgreSQL + Redis). Serve só para
ilustrar como preencher o piso por área e o catálogo de pendências — os
níveis e a rota padrão por nível vêm sem alteração de `files/task/COMPLEXIDADE.md`
do harness.

## Piso por área do código

| Área | Piso | Motivo |
|---|---|---|
| `migrations/`, `src/db/sessao.py` | CRITICAL | Migrations incrementais contra o Postgres de produção |
| `docker-compose.yml`, `Dockerfile`, `.env*` | CRITICAL | Infra nativa e credenciais |
| `src/api/main.py` (CORS, rate limit, auth) | CRITICAL | Gates de segurança da API |
| scripts de `backups/`, exclusão em massa | CRITICAL | Dado destrutivo |
| `src/api/rotas/emprestimos.py`, `rotas/livros.py` | IMPORTANT | Rotas multi-componente com efeito em produção |
| `src/cache/redis_client.py` | IMPORTANT | Concorrência entre reservas simultâneas |
| `src/domain/` (regras de negócio puras) | SMALL | Sem I/O; blast radius contido |
| `tests/`, fixtures | SMALL | Sem efeito em produção |
| `README.md`, `docs/` | TRIVIAL | Documental |

## Catálogo — exemplos de tarefa por lane

<!-- Cada linha real do catálogo é uma unidade de trabalho aberta, com
     evidência de que ainda está pendente. As linhas abaixo são só exemplos
     ilustrativos de cada nível, não um catálogo de verdade. -->

| Id | Nível | Área | Estado | Evidência |
|---|---|---|---|---|
| EX-1 | TRIVIAL | `README.md` | Corrigir link quebrado para o guia de contribuição | `README.md:12` aponta para arquivo removido |
| EX-2 | SMALL | `src/domain/emprestimo.py` | Corrigir cálculo de multa por atraso (arredondamento) | `tests/test_domain/test_emprestimo.py::test_multa_atraso_meio_dia` falha |
| EX-3 | IMPORTANT | `src/api/rotas/emprestimos.py` | Adicionar endpoint de renovação de empréstimo com limite de renovações | Feature pedida, sem rota existente; toca banco e regra de negócio |
| EX-4 | CRITICAL | `migrations/`, `src/cache/redis_client.py` | Migrar o lock de reserva de livro de coluna `SELECT ... FOR UPDATE` para lock distribuído em Redis | Concorrência entre duas reservas do mesmo exemplar; migration de schema + infraestrutura nativa |

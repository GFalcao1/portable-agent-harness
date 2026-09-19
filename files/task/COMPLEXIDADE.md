# Catálogo de complexidade — Projeto Hermes

Este arquivo é a trava de roteamento do workflow de agentes: a lane e a
profundidade das etapas saem daqui, não de opinião no momento da tarefa.

**Complexidade controla a profundidade do workflow, não a prioridade de negócio
nem o estado de conclusão.** Nenhuma linha deste catálogo aprova nada.

## Níveis

| Nível | Significado |
|---|---|
| TRIVIAL | Documental ou mecânico, sem risco comportamental |
| SMALL | Comportamento ou configuração localizada, com blast radius estreito |
| IMPORTANT | Feature multi-componente ou comportamento operacional que exige revisão independente |
| CRITICAL | Segurança, migração, concorrência, recuperação, credenciais, dado destrutivo, infraestrutura nativa, gates de release ou arquitetura acoplada |

Uma unidade de trabalho sobe para o maior risco aplicável. **Nunca é rebaixada
só porque o diff é pequeno.** A classificação é manual e versionada: um modelo
pode recomendar reclassificação, mas o orchestrator decide e registra.

## Rota padrão por nível

| Nível | Workflow padrão | Chamadas Fable |
|---|---|---|
| TRIVIAL | Orchestrator direto | 0 |
| SMALL | Implementer direto (lane B só com `agy` instalada); verifier ao final | 0–1 |
| IMPORTANT | Researcher quando necessário → implementer → code-reviewer (Fable) → verifier | 1 |
| CRITICAL | Researcher → planner (Fable) → requirement gate do orchestrator → implementer → code-reviewer (Fable) → verifier | 2 |

**O planner só é chamado em CRITICAL.** **IMPORTANT e CRITICAL nunca vão para a
lane B.** O Fable consome apenas o limite do administrador; BLOCKED por limite
encerra a etapa sem troca de modelo.

## Piso por área do código

O piso vale para qualquer alteração na área, independentemente do tamanho do diff.

| Área | Piso | Motivo |
|---|---|---|
| `db/session.py`, `migrations/`, `alembic.ini` | CRITICAL | Migrations incrementais em produção, advisory lock |
| `core/redis_client.py` | CRITICAL | Zombie lock com TTL; concorrência entre uploads |
| `docker-compose.yml`, `Dockerfile`, `docker-entrypoint.sh`, `.env*` | CRITICAL | Infra nativa, `read_only`, `cap_drop`, credenciais |
| `api/main.py` (lifespan, CORS, CSP, rate limit) | CRITICAL | Gates de segurança da API |
| `audit/xml_corrector.py` | CRITICAL | Reescreve XML fiscal do cliente (dado destrutivo) |
| Exclusão em massa / limpeza de tabelas / scripts de `backups/` | CRITICAL | Dado destrutivo |
| `audit/produto_classifier.py`, `audit/auditor.py` | IMPORTANT | Orquestração 4C, cache C1, SAVEPOINT por XML |
| `api/routers/auditor.py`, `regras.py`, `acumuladores.py`, `parametrizacao/` | IMPORTANT | Rotas multi-componente; uploads |
| `decree/rag.py`, `scripts/indexar_rag.py`, `scripts/etl_decreto_alagoas.py` | IMPORTANT | RAG e ETL com custo em provider externo |
| `core/logging.py` (`redact_pii`) | IMPORTANT | PII em logs |
| `frontend/` (páginas, CSS isolado, componentes) | SMALL | Blast radius visual; validar com Playwright |
| `tests/`, fixtures | SMALL | Sem efeito em produção |
| `README.md`, `CLAUDE.md`, `FLUXO.md`, `docs/`, `relatorios/`, `PLANO*.md` | TRIVIAL | Documental |
| `legacy/` | TRIVIAL | Isolado; não é importado |

## Catálogo — pendências em aberto (espelha `CLAUDE.md` em 2026-09-18)

| Task | Complexidade | Estado atual | Dependências | Justificativa |
|---|---|---|---|---|
| M19 — Cache C1 grava `ncm_sugerido` com embedding do produto original | IMPORTANT | ABERTA | Nenhuma | Altera associação embedding↔NCM no cache de auto-aprovação; exige revisão independente |
| B4 — Regex de `batch_nome` em `regras.py` | SMALL | ABERTA | Nenhuma | Parsing localizado, sem efeito fora do dashboard |
| B5 — Matching `nome in texto` case-sensitive em acumuladores | SMALL | ABERTA | Nenhuma | Normalização localizada; testes existentes cobrem o router |
| B6 — `session.flush()` fora do SAVEPOINT em `produto_classifier.py` | IMPORTANT | ABERTA | Nenhuma | Toca a fronteira transacional por XML |
| B7 — Cobertura de teste para `corrigir_xml_multi_itens` | SMALL | ABERTA | Nenhuma | Só testes; mas qualquer correção decorrente em `xml_corrector.py` sobe para CRITICAL |
| test_zip_grouping.py — falso positivo conhecido | SMALL | ABERTA | Nenhuma | Ajuste de teste |
| Autenticação — JWT + RBAC por auditor | CRITICAL | PLANEJADA (sprint dedicado) | Sair da rede interna | Credenciais e gate de acesso |
| Observabilidade — correlation ID e OpenTelemetry nas latências 4C | IMPORTANT | PLANEJADA | Nenhuma | Multi-componente, sem risco de dado |
| CSP enforce — trocar Report-Only por enforce | CRITICAL | PLANEJADA (após 1–2 semanas sem violações) | Coleta de relatórios CSP | Gate de segurança do frontend em produção |

Ao abrir uma task nova, acrescente uma linha aqui **antes** de delegar. Sem
linha no catálogo, a lane não tem trava e vira opinião.

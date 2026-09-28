# 15. Contexto obrigatório do Projeto Hermes

Todo papel deve respeitar:

- ambiente único é produção na rede interna
- backup antes de deploy
- nunca fazer push sem OK explícito
- nunca fazer deploy sem OK explícito
- nunca excluir dados ou arquivos sem OK explícito
- nunca executar ação irreversível sem confirmação

Convenções adicionais:

[`CLAUDE.md`](http://CLAUDE.md)

Incluindo:

- `defusedxml` ou `lxml` sem entidades
- nunca expor `str(e)` diretamente ao cliente
- `redact_pii()` em logs relacionados a IA
- SAVEPOINT por XML quando definido pelo projeto

Testes:

```bash
.venv/bin/python -m pytest

```

Não assumir existência de `uv`.

---

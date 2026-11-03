# Integration: gh CLI (GitHub)

> `gh` é a CLI oficial do GitHub. Usado pra criar PRs, issues, repos,
> ler reviews, etc. Auth global via `gh auth login`.

## Pré-requisitos

```bash
gh auth status              # verificar auth + scopes
```

Scopes necessários comuns:
- `repo` (default) — PRs, issues, push
- `delete_repo` — deletar repo (raramente; precisa `gh auth refresh -h github.com -s delete_repo`)
- `workflow` — disparar GitHub Actions

## Comandos comuns no contexto OpenClaw

```bash
# Criar PR (usar HEREDOC pro body conforme CLAUDE.md)
gh pr create --title "feat: ..." --body "$(cat <<'EOF2'
## Summary
- ...

## Test plan
- [x] ...
EOF2
)"

# Listar PRs abertos
gh pr list --state open

# Ver comments de um PR (usado por receiving-code-review)
gh api repos/<org>/<repo>/pulls/<num>/comments

# Issues
gh issue list --state open
gh issue create --title "..." --body "..."
gh issue close <num>

# Repos
gh repo view <org>/<repo>
gh repo create <org>/<slug> --private --source <path> --push
gh repo delete <org>/<slug> --yes   # exige delete_repo scope

# CI
gh run list --workflow="..."
gh run watch <run-id>
gh run view <run-id> --log-failed
```

## Padrões / regras

- **HEREDOC pra body de PR/commit** (preserva newlines): `--body "$(cat <<EOF\n...\nEOF\n)"`
- **NUNCA** `--no-verify` em commits (per CLAUDE.md)
- **NUNCA** force push em main
- Force push em feature branch: OK, mas confirmar com Bernard se PR já existe
- Commits assinados com Co-Authored-By por convenção da Bevox

## Anti-patterns

- NÃO commitar segredos (`gh repo create` pode propagar `.env` se mal gitignored)
- NÃO criar issues/PRs em massa sem contexto — Bernard é quem decide priorização

# CHS Recruta

Sistema de recrutamento e seleção com backend em **Python + FastAPI**, persistência via **SQLAlchemy/PostgreSQL**, autenticação com **RBAC**, trilha de auditoria, testes automatizados, Docker e CI.

> Este repositório é a versão backend-first do CHS Recruta, separada do portfólio principal para facilitar avaliação técnica, execução local e deploy.

## Stack

`Python` · `FastAPI` · `SQLAlchemy 2` · `PostgreSQL` · `Pydantic` · `Pytest` · `Docker` · `GitHub Actions`

## Funcionalidades

- autenticação por sessão bearer e RBAC (`admin` / `recruiter`);
- CRUD de candidatos e vagas;
- normalização de profissão e detecção de duplicidade;
- matching candidato ↔ vaga;
- dashboard e funil de recrutamento;
- referências financeiras;
- trilha de auditoria;
- exportação CSV;
- interface web simples;
- documentação OpenAPI em `/docs`.

## Executar localmente

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload
```

Acesse:

- aplicação: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- healthcheck: `http://127.0.0.1:8000/health`

As credenciais locais do seed são controladas por `DEMO_ADMIN_USERNAME`, `DEMO_ADMIN_PASSWORD` e `DEMO_ADMIN_EMAIL`. Use o seed apenas para desenvolvimento/demonstração e não publique credenciais de administrador em produção.

## Docker

```bash
docker compose up --build
```

## Testes

```bash
python -m pytest -q
```

A CI executa compilação do pacote e testes em cada push/PR.

## Persistência

A aplicação lê `DATABASE_URL`. Em desenvolvimento, quando ela não é definida, usa SQLite local. Em ambiente público/produção, configure PostgreSQL persistente. O deployment de portfólio é preparado para usar PostgreSQL externo sem gravar a string de conexão no repositório.

## Segurança

- PBKDF2-HMAC-SHA256 com salt aleatório;
- tokens de sessão aleatórios, persistindo apenas o hash;
- expiração e revogação de sessões;
- rotas protegidas por autenticação;
- ações administrativas protegidas por role;
- auditoria vinculada ao usuário autenticado.

## Arquitetura

```text
app/
├── main.py
├── database.py
├── models.py
├── schemas.py
├── security.py
├── services.py
└── routers/
    ├── auth.py
    ├── candidates.py
    ├── vacancies.py
    ├── operations.py
    └── users.py

static/
tests/
docs/
```

## Deploy

O repositório inclui `vercel.json`, além de `Dockerfile` e `docker-compose.yml`. Uma URL só deve ser apresentada aqui como backend público após healthcheck externo bem-sucedido.

## Roadmap

Consulte [`docs/MELHORIAS_E_ROADMAP.md`](docs/MELHORIAS_E_ROADMAP.md).

## Desenvolvimento assistido por IA

Ferramentas de IA foram usadas para acelerar pesquisa, implementação, revisão e documentação. As decisões de escopo, arquitetura, validação, testes e revisão técnica permanecem sob responsabilidade do autor.

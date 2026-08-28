# CHS RH

Plataforma SaaS multiempresa para recrutamento e gestão de pessoas. **CHS Recruta** é o módulo ATS.

A fonte permanente do produto é [docs/PRODUCT_PURPOSE.md](docs/PRODUCT_PURPOSE.md).

## Implementado neste marco

- tenants, usuários globais e memberships por empresa;
- sete papéis e permissões por ação;
- senhas Argon2id, MFA TOTP, recuperação, bloqueio e rate limit persistente;
- sessões por dispositivo em cookie HttpOnly/CSRF, revogação e expiração por inatividade;
- acesso privilegiado temporário com MFA, dupla aprovação, motivo e auditoria;
- filtros por tenant e PostgreSQL Row-Level Security;
- Alembic, auditoria estruturada, request ID e soft delete;
- frontend operacional responsivo, busca, cinco paletas e claro/escuro;
- tutorial por permissão com transições, redução de movimento e **Não exibir novamente** persistente;
- candidatos, vagas, candidaturas independentes e pipeline ATS;
- requisições e aprovações, entrevistas, scorecards e ofertas;
- departamentos, colaboradores, onboarding e benefícios;
- contratos, movimentações, ciclos, metas e avaliações de desempenho;
- portal do colaborador com solicitações, férias/ausências e documentos por visibilidade;
- templates idempotentes de onboarding e adesões a benefícios com elegibilidade;
- ajustes de ponto sem sobrescrever marcações, espelhos versionados e lotes de folha idempotentes;
- ponto com hash de integridade e holerites com acesso individual;
- filas idempotentes para eventos eSocial e medição/faturas SaaS internas;
- assistente baseado em fontes autorizadas, citações e abstenção;
- testes de isolamento, RBAC, auditoria, tutorial e privacidade.

O [estado de implementação](docs/IMPLEMENTATION_STATUS.md) separa o que funciona do que ainda depende de integração ou homologação. O sistema não se apresenta como REP-P certificado, motor de folha homologado ou conector oficial do eSocial.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 17 · Pydantic 2 · JavaScript modular · Pytest · Docker

## Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./chs_recruta.db
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Acesse:

- aplicação: http://127.0.0.1:8000
- OpenAPI: http://127.0.0.1:8000/docs
- saúde: http://127.0.0.1:8000/health

Para criar o seed local, defina `DEMO_ADMIN_PASSWORD` com uma senha forte escolhida por você. O usuário padrão é `demo` e a empresa é `empresa-demo`; nenhuma senha é publicada no repositório.

## Docker

```bash
cp .env.example .env
# Preencha POSTGRES_PASSWORD, SECURITY_SECRET_KEY e DEMO_ADMIN_PASSWORD no .env.
docker compose up --build
```

O Compose sobe PostgreSQL, aplica migrations, cria o tenant demonstrativo e inicia a API.

## Configuração

| Variável | Padrão | Uso |
|---|---|---|
| `APP_ENV` | development | use production no ambiente público |
| `DATABASE_URL` | SQLite local | use PostgreSQL persistente em produção |
| `SESSION_TTL_HOURS` | 12 | expiração da sessão |
| `SESSION_IDLE_MINUTES` | 60 | expiração por inatividade |
| `MAX_ACTIVE_SESSIONS` | 5 | limite por usuário |
| `SECURITY_SECRET_KEY` | somente desenvolvimento | chave de criptografia/HMAC; obrigatória via secrets manager em produção |
| `PASSWORD_RESET_TTL_MINUTES` | 20 | validade do link de recuperação |
| `PASSWORD_RESET_URL` | localhost | URL pública HTTPS com `{token}` no fragmento |
| `SMTP_*` | vazio | entrega dos links; `SMTP_HOST`/`SMTP_FROM` são obrigatórios em produção |
| `ALLOWED_ORIGINS` | localhost | origens CORS |
| `AUTO_CREATE_SCHEMA` | SQLite dev | em produção use false + Alembic |
| `TUTORIAL_VERSION` | 5 | reapresenta conteúdo novo |
| `SEED_DEMO` | false | somente ambiente descartável |

## Testes

```bash
python -m compileall -q app
python -m pytest -q
node --check static/app.js
node --check static/advanced.js
node --check static/portal.js
node --check static/workforce.js
node --check static/time_payroll.js
node --check static/security.js
```

## Estrutura

```text
app/
├── config.py, database.py, models.py, schemas.py
├── advanced_models.py, advanced_schemas.py, identity_models.py
├── permissions.py, security.py, services.py
├── main.py, seed.py
└── routers/saas.py
migrations/
static/
tests/
docs/
```

## Documentação

- [Propósito permanente](docs/PRODUCT_PURPOSE.md)
- [Manual completo](docs/USER_MANUAL.md)
- [Arquitetura](docs/ARCHITECTURE.md)
- [Estado e próximos gates](docs/IMPLEMENTATION_STATUS.md)
- [Roadmap mestre](docs/MELHORIAS_E_ROADMAP.md)

## Produção

Antes de dados reais: TLS, secrets manager, SMTP transacional, backups restaurados, PostgreSQL gerenciado, object storage privado, rate limit distribuído, observabilidade, scans, pentest e revisão LGPD/jurídico-contábil. SSO/SCIM e WebAuthn/passkeys seguem como gate enterprise.

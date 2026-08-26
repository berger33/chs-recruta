# Evoluções futuras — fora do escopo atual

O backend atual já cobre o escopo demonstrável do case de portfólio: autenticação/RBAC, candidatos, vagas, matching, dashboard/funil, auditoria, exportação, persistência configurável, testes, Docker e CI. Os itens abaixo são **evoluções possíveis de produto/engenharia**, não requisitos pendentes para executar ou avaliar a versão atual.

## Backend — evoluções possíveis
- Alembic para migrations versionadas em ciclos de evolução do schema.
- Testes de integração adicionais contra PostgreSQL no CI.
- Paginação, filtros e ordenação server-side para volumes maiores.
- Soft delete, constraints e índices adicionais conforme crescimento dos dados.
- Logging estruturado e request IDs para observabilidade de produção.
- Backup/restore e importação CSV/XLSX em fluxos operacionais maiores.
- Jobs assíncronos e webhooks para integrações externas.
- Idempotência e versionamento de API para integrações públicas.

## Produto RH — extensões possíveis
- Pipeline configurável de recrutamento.
- Scorecards e entrevistas estruturadas.
- Agenda e integração com calendário.
- Talent pools, skills e certificações.
- Métricas de time-to-hire/time-to-fill, source-of-hire e aging.

## IA responsável — princípios para qualquer evolução
- Não automatizar decisão final de contratação.
- Não inferir atributos sensíveis.
- Matching deve ser explicável e permitir override humano.
- Manter auditoria das ações relevantes.

# Estado de implementação

**Atualizado em:** 28 de agosto de 2026  
**Fonte de propósito:** [PRODUCT_PURPOSE.md](PRODUCT_PURPOSE.md)  
**Backlog detalhado:** [MELHORIAS_E_ROADMAP.md](MELHORIAS_E_ROADMAP.md)

Este documento separa produto operacional, fundação e trabalho dependente de integração ou homologação. “Modelo criado” não significa integração oficial.

## Resumo

| Área | Estado do marco | Próximo gate |
|---|---|---|
| Multiempresa | tenant, membership e sessão tenant-bound | convite, unidades e console SaaS |
| Isolamento | filtros + PostgreSQL RLS + teste negativo | CI com PostgreSQL real |
| Permissões | 7 papéis, ações e escopo próprio/equipe | RBAC configurável + ABAC |
| Migrations | Alembic baseline e RLS | expand/contract em staging |
| Auditoria | diffs, ator, tenant, IP e request ID | append-only/SIEM |
| Frontend | módulos atuais conectados à API | testes E2E e design system |
| Tutorial | passos por permissão, persistência e redução de movimento | conteúdo por plano |
| ATS | candidatos, vagas, pipeline, requisições/aprovações, entrevistas, scorecards e ofertas | pipeline configurável, portal externo e admissão automática |
| Core RH | departamentos, colaboradores, contratos e movimentações históricas | unidades, cargos versionados e organograma |
| Portal | autoescopo, solicitações, férias/ausências, documentos, ponto, holerite e conhecimento | saldo de férias, assinatura e download seguro |
| Onboarding | templates, tarefas relativas, responsáveis, aplicação idempotente e conclusão | dependências, evidências e assinatura |
| Benefícios | catálogo, elegibilidade por vínculo/departamento/carência e adesões | dependentes, eventos de vida e integrações |
| Ponto | registro inicial, **não REP-P** | provider homologado, ajustes, espelho e fechamento |
| Holerites | hub de metadados | object storage, lotes e reconciliação |
| eSocial | eventos idempotentes, estados, auditoria e UI operacional | XSD, certificado, worker, recibos e homologação |
| RAG | ACL, citações e abstenção | ingestão, embeddings, avaliação e LLM controlado |
| Desempenho | ciclos, metas, avaliações e escopo próprio/equipe | calibração, feedback contínuo, 9-box e PDI |
| Billing | assinatura, plano, medição e faturas internas | gateway, checkout, webhooks assinados e dunning |

## Gate de produção da fundação

1. PostgreSQL gerenciado em staging e teste de RLS no CI;
2. MFA, recuperação de senha e rate limit;
3. logs, métricas, traces, alertas e runbooks;
4. object storage privado e pipeline de arquivos;
5. backup/PITR com restauração evidenciada;
6. lint, type check, SAST, scans, SBOM e pentest;
7. políticas LGPD, retenção, anonimização e direitos do titular.

## Próximo produto vendável

1. pipeline ATS configurável, portal de candidatos e admissão a partir de oferta aceita;
2. unidades, cargos versionados, organograma e centros de custo;
3. saldo/aquisição de férias, object storage, download seguro e assinatura;
4. adapters de ponto, folha e eSocial com filas e homologação;
5. RAG com ingestão, embeddings, avaliações e escalonamento;
6. calibração, feedback contínuo, 9-box e PDI;
7. checkout, portal de cobrança, webhooks assinados e inadimplência.

## Limites explícitos

- Hash de marcação não transforma a solução em REP-P.
- O hub de holerites não calcula folha.
- Subscription não cobra cartões nem emite documento fiscal.
- Uma fatura interna não prova liquidação financeira.
- Um evento eSocial `accepted` representa o estado registrado pela aplicação/adaptador; sem conector homologado não equivale a recibo oficial.
- eSocial, folha e normas trabalhistas exigem validação jurídica, contábil e regulatória atualizada.
- IA auxilia; contratação, carreira, remuneração e desligamento permanecem decisões humanas.

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
| ATS | candidatos, vagas, candidaturas e pipeline | aprovações, entrevistas, ofertas e portal |
| Core RH | departamentos, colaboradores e vínculo de acesso | contratos históricos, unidades e organograma |
| Portal | autoescopo de perfil, ponto, holerite e conhecimento | solicitações, férias e arquivos |
| Onboarding | tarefas, prazo, responsável e conclusão | templates, dependências e assinatura |
| Benefícios | catálogo inicial | elegibilidade, adesão e integrações |
| Ponto | registro inicial, **não REP-P** | provider homologado, ajustes, espelho e fechamento |
| Holerites | hub de metadados | object storage, lotes e reconciliação |
| eSocial | arquitetura de adapter planejada | XSD, certificado, filas e homologação |
| RAG | ACL, citações e abstenção | ingestão, embeddings, avaliação e LLM controlado |
| Desempenho | planejado no propósito | ciclos, metas, feedback e PDI |
| Billing | assinatura, plano, limites e módulos no domínio | gateway, medição, invoices e dunning |

## Gate de produção da fundação

1. PostgreSQL gerenciado em staging e teste de RLS no CI;
2. MFA, recuperação de senha e rate limit;
3. logs, métricas, traces, alertas e runbooks;
4. object storage privado e pipeline de arquivos;
5. backup/PITR com restauração evidenciada;
6. lint, type check, SAST, scans, SBOM e pentest;
7. políticas LGPD, retenção, anonimização e direitos do titular.

## Próximo produto vendável

1. completar ATS: requisição/aprovação, pipeline configurável, entrevistas, scorecards e ofertas;
2. converter contratação em admissão sem redigitação;
3. contratos/vínculos históricos, cargos, unidades e centros de custo;
4. solicitações do colaborador, férias e documentos;
5. adapters de ponto e folha com importação idempotente;
6. RAG com ingestão, embeddings, avaliações e escalonamento;
7. checkout, portal de cobrança, webhooks assinados e inadimplência.

## Limites explícitos

- Hash de marcação não transforma a solução em REP-P.
- O hub de holerites não calcula folha.
- Subscription não cobra cartões nem emite documento fiscal.
- eSocial, folha e normas trabalhistas exigem validação jurídica, contábil e regulatória atualizada.
- IA auxilia; contratação, carreira, remuneração e desligamento permanecem decisões humanas.

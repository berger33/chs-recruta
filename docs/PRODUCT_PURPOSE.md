# Propósito permanente do produto — CHS RH

**Classificação:** fonte de verdade do produto  
**Produto:** CHS RH, tendo CHS Recruta como módulo de ATS  
**Versão do propósito:** 1.0  
**Vigência:** 28 de agosto de 2026

## 1. Função deste documento

Este documento define por que o CHS RH existe, quem ele atende, quais problemas resolve, quais módulos compõem a plataforma e quais princípios não podem ser violados durante sua construção.

Toda decisão de produto, arquitetura, segurança, experiência e priorização deve ser compatível com este documento. Alterações de propósito exigem decisão explícita, justificativa documentada e commit próprio. Roadmaps podem mudar; o propósito permanece estável.

## 2. Missão

Oferecer a empresas de diferentes portes uma plataforma SaaS completa, segura, acessível e intuitiva para administrar toda a jornada de pessoas: da abertura da vaga e candidatura até admissão, vínculo, desenvolvimento, folha, jornada, atendimento interno e desligamento.

O sistema deve reduzir retrabalho, planilhas paralelas, perda de informação e tarefas repetitivas, sem retirar do profissional de RH a responsabilidade pelas decisões humanas.

## 3. Visão

Ser uma central de trabalho confiável para RH, Departamento Pessoal, gestores e colaboradores, reunindo dados, processos, documentos, indicadores e conhecimento corporativo em uma única experiência multiempresa.

## 4. Princípios permanentes

1. **Pessoas antes da automação.** IA e regras auxiliam; decisões de contratação, carreira e desligamento permanecem humanas.
2. **Privacidade desde a origem.** Coletar apenas o necessário, definir finalidade, limitar acesso e aplicar retenção.
3. **Isolamento absoluto entre clientes.** Nenhuma empresa pode acessar dados, arquivos, vetores, logs ou configurações de outra.
4. **Segurança no backend.** A interface nunca é a única barreira de autorização.
5. **Auditoria por padrão.** Alterações relevantes devem registrar ator, empresa, instante, origem, motivo e diferenças.
6. **Dados históricos não são sobrescritos.** Vínculos, cargos, salários, etapas, marcações e documentos precisam de histórico.
7. **Modularidade sem complexidade prematura.** Começar como monólito modular e separar serviços somente quando métricas justificarem.
8. **Python como linguagem principal do backend.** Outras linguagens podem ser usadas quando forem a opção adequada para a experiência do usuário ou integração.
9. **Acessibilidade e clareza.** O sistema deve funcionar por teclado, em celular e desktop, com contraste e linguagem compreensível.
10. **Conformidade demonstrável.** Não basta afirmar conformidade; é necessário produzir evidências, testes, relatórios e trilhas.
11. **Integrações versionadas.** eSocial, folha, ponto e provedores externos mudam e não podem ficar acoplados ao domínio.
12. **Sem funcionalidades decorativas.** Cada módulo precisa resolver uma rotina real e possuir critério de sucesso.

## 5. Usuários e responsabilidades

### Administração do SaaS

- opera planos, módulos, suporte, limites, cobrança, disponibilidade e incidentes;
- não acessa dados do cliente sem autorização, justificativa, tempo limitado e auditoria.

### Administrador da empresa

- configura organização, unidades, identidade visual, usuários, papéis, integrações e políticas;
- acompanha uso, segurança e faturamento do tenant.

### RH e Departamento Pessoal

- executam recrutamento, admissão, cadastro, documentos, jornada, benefícios, folha, férias, desenvolvimento e desligamento;
- acessam somente dados compatíveis com suas responsabilidades.

### Recrutador

- administra requisições, vagas, candidatos, candidaturas, entrevistas, ofertas e banco de talentos.

### Gestor

- solicita e aprova vagas, acompanha equipe, aprova processos e realiza avaliações dentro do seu escopo.

### Colaborador

- consulta e atualiza seus dados permitidos, holerites, documentos, ponto, benefícios, solicitações, tarefas e desenvolvimento.

### Candidato

- candidata-se, acompanha processos autorizados, atualiza dados, gerencia consentimentos e exerce direitos de privacidade.

### Auditor, encarregado ou parceiro

- possui acesso temporário e restrito a relatórios ou processos explicitamente autorizados.

## 6. Escopo funcional completo

### 6.1 Plataforma SaaS

- tenants, empresas legais, estabelecimentos e unidades;
- planos, módulos, limites, trial, assinatura, cobrança e inadimplência;
- identidade visual, timezone, moeda, idioma e calendários;
- feature flags, implantação assistida, importações, suporte e status page;
- exportação e encerramento seguro de conta.

### 6.2 Identidade, permissões e segurança

- usuários globais e memberships por empresa;
- papéis e permissões granulares por módulo e ação;
- escopo por unidade, departamento, equipe e propriedade do dado;
- MFA, sessões, recuperação de senha, SSO e SCIM em planos compatíveis;
- acesso privilegiado just-in-time e trilha imutável.

### 6.3 CHS Recruta — ATS

- requisição e aprovação de vagas;
- portal de carreiras e candidatura responsiva;
- candidatos, currículos, skills, documentos, disponibilidade e preferências;
- candidaturas independentes e múltiplas por candidato;
- pipeline configurável, histórico, SLA, tarefas e automações;
- entrevistas, agenda, scorecards, ofertas e conversão para admissão;
- banco de talentos, comunicação, importação, exportação e integrações;
- validação de conselhos profissionais por adapters;
- matching explicável, revisável e sem decisão automática final;
- dashboards de conversão, tempo, fonte, escassez e produtividade.

### 6.4 Core RH

- pessoa, colaborador, matrícula, vínculos e histórico temporal;
- unidades, departamentos, centros de custo, cargos, níveis e posições;
- organograma, headcount e diretório corporativo;
- movimentações, promoções, transferências e alterações salariais;
- documentos, dependentes, contatos e dados bancários com acesso restrito.

### 6.5 Admissão, onboarding e desligamento

- checklist por cargo, unidade e vínculo;
- coleta e validação documental;
- tarefas interáreas, prazos, responsáveis e evidências;
- contratos, políticas, aceite e assinatura;
- provisionamento, devolução de ativos e revogação de acessos;
- conversão do candidato sem redigitação desnecessária.

### 6.6 Portal do colaborador e gestor

- dados pessoais e solicitações de alteração;
- holerites, informes, contratos, políticas e documentos;
- ponto, espelho, banco de horas, justificativas e aprovações;
- férias, folgas, ausências, atestados e benefícios;
- onboarding, treinamentos, avaliações, PDI e comunicados;
- área do gestor limitada à sua equipe e responsabilidades.

### 6.7 Jornada e ponto

- escalas, turnos, intervalos, marcações, ajustes, espelhos e fechamento;
- banco de horas, horas extras, adicional noturno, atrasos e faltas;
- integrações com provedores de REP como primeira estratégia;
- REP-P próprio somente após projeto regulatório, certificações, registro e homologação;
- registros originais imutáveis e ajustes como eventos separados.

### 6.8 Holerites, folha e eSocial

- hub seguro de holerites e documentos de pagamento;
- importação idempotente e reconciliação por competência e matrícula;
- adapters para sistemas de folha e contabilidade;
- conector eSocial com layouts, XSDs, recibos e reprocessamento versionados;
- motor de folha próprio apenas após decisão específica e homologação contábil.

### 6.9 Benefícios, férias e atendimento de RH

- catálogo, elegibilidade, adesão, dependentes e integrações;
- saldos, solicitações, conflitos, aprovações e calendários;
- casos de RH restritos, prazos, comentários, anexos e legal hold;
- dados de saúde segregados e minimizados.

### 6.10 Desempenho e desenvolvimento

- avaliações, metas, competências, feedback, calibração e 1:1;
- PDI, carreira, sucessão e matriz de talentos;
- treinamentos, trilhas, presenças e certificados;
- pesquisas de clima e pulso com anonimato adequado.

### 6.11 Assistente corporativo RAG

- base de conhecimento com documentos versionados e responsáveis;
- ingestão, OCR, chunks, embeddings, validade e revisão;
- isolamento por tenant e ACL aplicada antes da recuperação;
- respostas com citações, versão da fonte e abstenção quando faltar evidência;
- consultas estruturadas limitadas ao próprio colaborador ou escopo do gestor;
- escalonamento para RH quando a resposta exigir decisão humana;
- proteção contra prompt injection e vazamento entre clientes;
- conteúdo de clientes não utilizado para treinamento por padrão.

### 6.12 Analytics, workflows e integrações

- dashboards e relatórios com catálogo de métricas;
- workflows configuráveis, aprovações, SLAs e notificações;
- API pública, OAuth2, webhooks assinados e sandbox;
- integrações com e-mail, calendário, videoconferência, assinatura, job boards, folha, ponto e benefícios;
- importações CSV/XLSX/SFTP com preview, validação e relatório de erros.

## 7. Requisitos permanentes da experiência

- data e horário de cadastro e atualização visíveis nas telas relevantes;
- auditoria pesquisável por data, horário, ator, ação e entidade;
- busca global no cabeçalho com resultados rápidos e acesso direto;
- filtros salvos e ações em lote seguras;
- modo claro/escuro e temas rosa, ciano, roxo, verde-musgo e laranja;
- rótulos de função separados de permissões técnicas;
- responsividade, atalhos, foco visível e leitor de tela;
- estados de loading, vazio, erro, confirmação e recuperação;
- preferências persistentes por usuário e empresa.

## 8. Tutorial de primeiro acesso

Todo usuário deve receber um tutorial guiado compatível com seu perfil e módulos contratados.

O tutorial deve:

- apresentar navegação, busca, notificações, segurança e suporte;
- ensinar cada área autorizada com passos curtos e objetivos;
- destacar elementos reais da interface, sem bloquear saídas de emergência;
- permitir avançar, voltar, pular e reiniciar pelas configurações;
- oferecer a opção **“Não exibir novamente”**;
- persistir conclusão e preferência por usuário e tenant no backend;
- adaptar passos quando módulos ou permissões mudarem;
- usar transições modernas com fallback e respeitar `prefers-reduced-motion`;
- funcionar por teclado e anunciar mudanças para tecnologias assistivas;
- registrar versão do tutorial para apresentar somente conteúdos realmente novos.

## 9. Limites e compromissos

- o produto não presta aconselhamento jurídico, médico, fiscal ou contábil;
- o chatbot não inventa políticas nem toma decisões trabalhistas;
- atributos sensíveis não são inferidos para recrutamento ou desempenho;
- biometria, geolocalização e dados de saúde exigem avaliação específica;
- nenhuma funcionalidade é anunciada como REP-P, folha homologada ou integração oficial sem evidência;
- ambientes de desenvolvimento e testes não devem usar dados pessoais reais;
- exclusões respeitam retenção legal, bloqueio e legal hold;
- suporte não pode usar impersonação silenciosa.

## 10. Ordem obrigatória de construção

1. multiempresa, isolamento, permissões, migrations, auditoria e frontend operacional;
2. ATS completo;
3. Core RH, portal do colaborador e onboarding;
4. benefícios, férias, ponto e holerites;
5. eSocial e integrações de Departamento Pessoal;
6. RAG corporativo;
7. desempenho, desenvolvimento e pesquisas;
8. cobrança SaaS, integrações enterprise e expansão de escala.

Um módulo pode ser prototipado antes, mas não pode entrar em produção contornando as fundações da etapa 1.

## 11. Critérios de sucesso do produto

- zero vazamento tolerado entre tenants;
- redução mensurável de planilhas e retrabalho;
- rastreabilidade de processos e alterações;
- fluxo completo da vaga ao colaborador sem redigitação desnecessária;
- autoatendimento seguro de colaboradores e gestores;
- indicadores reconciliados e compreensíveis;
- respostas RAG fundamentadas e permissionadas;
- implantação guiada para novos clientes;
- experiência acessível em celular e desktop;
- operação comercial sustentável por módulos e planos.

## 12. Regra de alteração

Mudanças neste documento devem conter:

1. problema ou oportunidade;
2. impacto em clientes, privacidade, segurança e arquitetura;
3. módulos e personas afetados;
4. decisão aprovada;
5. atualização de roadmap, documentação e critérios de teste;
6. commit exclusivo ou claramente identificado.

# Manual de uso — CHS RH

**Versão:** 1.4
**Público:** administradores, RH, recrutadores, gestores, colaboradores e auditores  
**Data:** 28 de agosto de 2026

## Primeiros cinco minutos

### Entrar

1. Abra o endereço fornecido pela empresa.
2. Informe usuário ou e-mail corporativo.
3. Digite sua senha.
4. Se tiver acesso a várias organizações, informe ou selecione a empresa correta.
5. Clique em **Entrar com segurança**.

No ambiente local demonstrativo, o usuário é `demo` e a empresa é `empresa-demo`. A senha é definida pelo administrador em `DEMO_ADMIN_PASSWORD` e nunca fica publicada no repositório.

### Tutorial de primeiro acesso

O tutorial abre automaticamente e mostra somente áreas compatíveis com seu papel.

- **Continuar** avança.
- **Voltar** retorna.
- **Pular por agora** fecha sem concluir.
- **Não exibir novamente após encerrar** salva sua escolha na empresa atual.
- **Concluir** registra a versão vista.
- **Refazer tutorial**, no rodapé do menu, permite reabrir a qualquer momento.

O tutorial destaca elementos reais, muda de módulo quando necessário e reduz animações conforme a preferência do sistema operacional. A escolha é persistida por usuário e empresa, inclusive em outro dispositivo.

### Entender a tela

- O cartão superior mostra empresa ativa e papel.
- O menu exibe somente módulos autorizados.
- A busca do cabeçalho encontra candidatos e colaboradores permitidos.
- O ícone de meio círculo alterna claro/escuro.
- No celular, o menu abre pelo cabeçalho.
- **Sair** revoga a sessão atual.

## Segurança da conta

Todas as pessoas têm acesso a **Segurança da conta**. As operações são aplicadas ao usuário global; eventos e acessos privilegiados continuam vinculados à empresa correta.

### Habilitar autenticação em duas etapas (MFA)

1. Abra **Segurança da conta**.
2. Em **Autenticação em duas etapas**, clique em **Habilitar MFA**.
3. Confirme sua senha atual.
4. No aplicativo autenticador de sua preferência, adicione uma conta pela chave manual ou URI exibida.
5. Informe o primeiro código de seis dígitos para concluir.
6. Copie os códigos de recuperação exibidos uma única vez e guarde-os fora do computador e do celular usados para entrar.

Após habilitar ou desabilitar MFA, as outras sessões são encerradas. No próximo login, a senha válida abre um desafio de cinco minutos. Informe o código do aplicativo; se perder o autenticador, use um código de recuperação, que é consumido no primeiro uso. Um mesmo código TOTP não pode ser reutilizado.

Use **Novos códigos** para invalidar o conjunto anterior e gerar outro. Essa operação exige senha e MFA. Use **Desabilitar MFA** somente quando necessário; ela também exige os dois fatores. TOTP melhora a proteção, mas códigos ainda podem ser capturados por phishing: nunca os informe fora da tela oficial do CHS RH.

### Recuperar uma senha

1. Na tela de entrada, informe usuário ou e-mail.
2. Clique em **Esqueci minha senha**.
3. A tela sempre apresenta a mesma confirmação, exista ou não a conta; isso evita exposição de usuários cadastrados.
4. Abra o link enviado ao e-mail e crie uma senha com ao menos 15 caracteres.
5. Confirme a nova senha e entre novamente.

O link expira em 20 minutos, funciona uma vez e é invalidado quando um novo pedido é criado. A redefinição encerra todas as sessões. Em desenvolvimento, o sistema pode abrir o formulário diretamente; em produção, o administrador deve configurar o SMTP e o endereço público correto.

### Bloqueio e tentativas excessivas

Após cinco falhas de senha, a conta fica bloqueada por 15 minutos. A resposta continua genérica para não confirmar a existência da conta. Além disso, login, MFA, recuperação, redefinição e confirmação de identidade têm limites por IP ou identidade. Se aparecer **Muitas tentativas**, aguarde o período indicado e não repita automaticamente.

### Alterar a senha

1. Abra **Segurança da conta** e clique em **Alterar senha**.
2. Informe a senha atual, uma nova senha de ao menos 15 caracteres e a confirmação.
3. Se MFA estiver ativo, informe também o código.
4. Salve. As outras sessões serão encerradas.

Prefira uma frase-senha longa e exclusiva. O sistema rejeita senhas comuns e combinações que contenham partes óbvias do usuário, nome ou e-mail.

### Revisar e encerrar sessões

Em **Sessões e dispositivos**, confira dispositivo, IP, último uso, vencimento, estado e indicação de acesso privilegiado.

- **Encerrar** revoga um dispositivo específico.
- **Encerrar todas as outras** preserva apenas a sessão atual.
- **Sair** encerra a sessão atual.

Sessões também expiram depois de 60 minutos sem atividade ou 12 horas no total, salvo configuração mais restritiva. Há no máximo cinco sessões ativas por usuário; as mais antigas são encerradas quando o limite é excedido.

### Solicitar acesso privilegiado temporário

Use este fluxo para uma necessidade excepcional sem ampliar permanentemente o papel:

1. Habilite MFA e clique em **Confirmar identidade**. A confirmação vale por dez minutos.
2. Em **Acesso privilegiado temporário**, clique em **Solicitar acesso**.
3. Escolha uma permissão que seu papel ainda não possui, defina duração entre 5 e 120 minutos e descreva um motivo verificável com pelo menos 15 caracteres.
4. Outro proprietário ou administrador, nunca o próprio solicitante, revisa o pedido e registra uma justificativa.
5. Depois da aprovação, clique em **Ativar**. O sistema abre uma sessão separada e mostra o vencimento no cabeçalho da página.
6. Ao terminar, clique em **Revogar** ou saia. O vencimento ou a revogação invalida todas as sessões vinculadas à concessão.

A elevação só funciona dentro de uma empresa à qual o usuário já pertence. Ela não cria acesso cruzado entre clientes e não permite suporte por impersonação silenciosa.

### Revisar eventos de segurança

A lista final mostra tipo, resultado, data/hora, IP e request ID. Usuários comuns veem os próprios eventos; proprietário e administrador com `security.manage` veem eventos da empresa ativa. Use o request ID para investigação sem compartilhar senha, código MFA, token ou código de recuperação.

## Papéis

| Papel | Uso típico | Escopo |
|---|---|---|
| Proprietário | responsável pelo tenant | todas as áreas atuais |
| Administrador | implantação e operação | todas as áreas atuais |
| RH | pessoas e Departamento Pessoal | ATS, Core RH, jornada, conhecimento e auditoria |
| Recrutador | Talent Acquisition | candidatos, vagas, pipeline e indicadores |
| Gestor | liderança | leituras autorizadas, equipe e autoatendimento |
| Colaborador | autoatendimento | próprios ponto/holerite e conhecimento |
| Auditor | evidência | leitura e auditoria |

O backend valida a permissão novamente. Nunca use credenciais de outra pessoa.

## Visão geral

Acompanhe candidatos, vagas/posições, candidaturas, contratações, colaboradores, onboarding e conversão. Tudo corresponde apenas à empresa ativa.

## ATS

### Cadastrar candidato

1. Abra **Candidatos** e clique em **+ Candidato**.
2. Informe nome e profissão.
3. Complete cidade, contato, registro e origem.
4. Selecione status e escreva apenas observações necessárias.
5. Salve.

O sistema normaliza profissões comuns, verifica possível duplicidade por nome e contato/registro e cria auditoria. A busca filtra a lista. **Exportar CSV** exporta somente a empresa ativa e deixa evidência.

### Criar vaga

1. Abra **Vagas** e clique em **+ Vaga**.
2. Informe código único na empresa, título, profissão, cidade e posições.
3. Use rascunho na preparação e aberta quando pronta.
4. Descreva e salve.

### Pipeline

1. Abra **Pipeline ATS**.
2. Clique em **+ Candidatura**.
3. Selecione candidato e vaga.
4. Defina etapa, pontuação opcional e observações.
5. Salve.
6. Use **Mover para…** para atualizar a etapa.

Candidaturas são independentes: a mesma pessoa pode participar de várias vagas sem perder histórico.

### Requisições e aprovação

1. Abra **ATS avançado** e clique em **+ Requisição**.
2. Informe título, departamento, quantidade, justificativa e responsável pela aprovação.
3. Salve como rascunho ou envie para aprovação.
4. O aprovador autorizado escolhe **Aprovar** ou **Rejeitar**.
5. Consulte a situação antes de iniciar a seleção.

### Entrevistas, scorecards e ofertas

1. Em **ATS avançado**, agende a entrevista vinculada à candidatura.
2. Informe entrevistador, tipo, data/hora e local ou link.
3. Depois da conversa, registre o scorecard com critérios objetivos, nota e recomendação.
4. Para a pessoa selecionada, crie uma oferta com cargo, remuneração, data prevista e validade.
5. Atualize o status da oferta. Ao registrar uma oferta aceita, a candidatura avança para **Contratado** e o histórico preserva a transição.

Não registre atributos protegidos ou comentários discriminatórios. Uma nota auxilia a decisão, mas não autoriza decisão automática.

### Boas práticas

Colete somente dados necessários, não infira atributos sensíveis, use critérios relacionados ao trabalho, trate duplicidades e mantenha a decisão humana.

## Core RH e acessos

### Criar acesso

1. Abra **Configurações**.
2. Clique em **+ Acesso**.
3. Informe usuário, nome, e-mail e senha inicial.
4. Escolha o menor papel necessário.
5. Envie a credencial por canal seguro.

### Cadastrar colaborador

1. Abra **Colaboradores** e clique em **+ Colaborador**.
2. Informe matrícula, nome, e-mail, cargo e situação.
3. Defina admissão e departamento.
4. Vincule o acesso existente para habilitar autoatendimento.
5. Salve.

A matrícula é única dentro da empresa. O vínculo ao User determina “meus dados”, próprio ponto e próprios holerites.

### Contratos e movimentações

1. Abra **Contratos** e clique em **+ Contrato**.
2. Selecione colaborador, tipo, datas, jornada e remuneração aplicável.
3. Use **+ Movimentação** para promoção, transferência, reajuste, afastamento ou desligamento.
4. Informe vigência e motivo objetivo; não substitua o histórico anterior.
5. Confira a trilha de auditoria após alterações relevantes.

O cadastro mestre descreve o estado atual; contratos e movimentações preservam a história. Valores sensíveis devem ser acessíveis apenas aos papéis necessários.

## Onboarding

### Criar um template

1. Abra **Onboarding** e clique em **Novo template**.
2. Dê um nome ao checklist e descreva quando ele deve ser usado.
3. Cadastre uma tarefa por linha no formato mostrado na tela: dias relativos, responsável, título e descrição.
4. Use responsáveis `employee`, `manager`, `hr`, `it` ou `facilities`.
5. Revise a ordem e salve.

### Aplicar e acompanhar

1. Clique em **Aplicar template**.
2. Escolha template, colaborador e data-base; sem data-base, o sistema usa admissão e depois a data atual.
3. Confirme. Cada template pode ser aplicado uma única vez ao mesmo colaborador.
4. Acompanhe tarefas pendentes, em andamento e concluídas.
5. Para uma exceção, use **Tarefa avulsa**.
6. Após a entrega e evidência aplicável, clique em **Concluir**.

Crie tarefas separadas para RH, gestor, TI e Facilities.

## Benefícios

### Administrar

1. Abra **Benefícios** e clique em **+ Benefício**.
2. Informe nome, categoria, fornecedor e custo do colaborador.
3. Em **Regra**, defina vínculo exigido e carência; regras de departamento também estão disponíveis na API.
4. Confira solicitações e escolha **Ativar** ou **Rejeitar** conforme política/evidência.
5. Ao ativar, valide vigência e contribuições do colaborador/empresa.

### Solicitar adesão

1. O colaborador abre **Benefícios** e consulta o motivo de elegibilidade.
2. Em um plano elegível, clica em **Solicitar**.
3. Acompanha o pedido até ativação ou rejeição.
4. Enquanto pendente, pode cancelar a própria solicitação.

O backend recalcula vínculo, departamento e carência antes de aceitar o pedido. Dependentes, eventos de vida, descontos em folha e comunicação com operadoras ainda exigem evolução e integrações.

## Ponto

### Configurar escalas

1. O RH abre **Ponto** e clica em **Nova escala**.
2. Informa nome, carga semanal, intervalo e tolerância operacional.
3. Clica em **Atribuir escala**, seleciona colaborador e vigência.
4. Confere as datas: o sistema bloqueia escalas sobrepostas para a mesma pessoa.

### Registrar a jornada

1. O colaborador abre **Ponto** e clica em **Registrar marcação**.
2. Escolhe entrada, início/fim de intervalo ou saída.
3. Confere data e hora, adiciona observação quando necessário e salva.
4. Gestores consultam somente a equipe direta; o RH autorizado consulta a empresa.

Cada marcação bruta recebe hash de integridade e não pode ser reescrita pelo fluxo de correção. Marcações administrativas só podem entrar por usuário autorizado e fonte identificada como provedor ou importação.

### Corrigir uma marcação

1. Clique em **Solicitar ajuste**.
2. Use **add** para uma marcação ausente, **replace** para substituir o efeito de uma marcação ou **void** para anulá-la.
3. Informe motivo verificável e, quando aplicável, a nova data, hora e tipo.
4. O gestor da equipe ou RH aprova ou rejeita. O gestor não aprova o próprio ajuste.
5. Enquanto pendente, o solicitante pode cancelar. A marcação bruta continua preservada em todos os casos.

### Calcular e fechar o espelho

1. O RH clica em **Calcular espelho**, escolhe colaborador e competência `AAAA-MM`.
2. Confere minutos apurados e anomalias de pares incompletos ou duplicados.
3. O colaborador envia o espelho aberto.
4. O gestor ou RH aprova; o RH autorizado fecha a competência.
5. O fechamento grava hash. Um recálculo posterior não altera o fechado: cria nova versão ligada à anterior.

Este módulo mantém trilha técnica e segregação, mas **não é declarado como REP-P homologado**. Uso oficial exige aderência integral à Portaria MTP nº 671, comprovantes/arquivos e assinatura aplicáveis, além de homologação jurídica e trabalhista da implantação. Consulte as [orientações oficiais sobre REP](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/inspecao-do-trabalho/fiscalizacao-do-trabalho/rep) e a [Portaria nº 671 compilada](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/legislacao/portarias-1/portarias-vigentes-3/PDFPortarian671de8denovembrode2021compilada03.06.2024.pdf).

## Holerites

### Importar e publicar uma competência

1. O RH autorizado abre **Holerites** e clica em **Importar lote**.
2. Informa competência `AAAA-MM`, sistema de origem e uma chave idempotente única.
3. Cola uma linha por colaborador no formato `matrícula|bruto|descontos|líquido|arquivo|storage_key|sha256`.
4. Importa o lote. O sistema valida matrícula da empresa, checksum e a igualdade `bruto - descontos = líquido`.
5. Move o lote de **uploaded** para **validated** somente após a conferência da folha de origem.
6. Move de **validated** para **published** para liberar os demonstrativos aos colaboradores.

Repetir a mesma chave idempotente não duplica a competência. Lotes publicados não voltam de estado; uma correção deve usar novo lote e nova chave conforme a política da empresa.

### Consultar como colaborador

1. Abra **Holerites**.
2. Consulte apenas os próprios demonstrativos já publicados.
3. Confira competência, valores bruto, descontos, líquido, arquivo e checksum.

O sistema importa e distribui resultados; **não calcula folha** e não substitui sistema contábil/fiscal. O marco atual gerencia metadados: download seguro em produção exige object storage privado, antivírus, criptografia e URLs assinadas de curta duração. Integrações bancárias, contabilização, encargos e eventos de folha do eSocial continuam dependentes de conectores e validação profissional.

## Portal do colaborador

Abra **Meu portal** para visualizar pendências e documentos compatíveis com seu papel.

### Enviar uma solicitação

1. Clique em **+ Solicitação**.
2. Escolha a categoria, informe assunto, prioridade e descreva a necessidade.
3. Salve e acompanhe os estados enviado, em análise, aprovado, rejeitado ou concluído.
4. Enquanto ainda estiver em análise, use **Cancelar** se a demanda deixar de ser necessária.
5. Gestores veem somente a equipe direta; RH autorizado administra toda a empresa.

### Solicitar férias ou ausência

1. Clique em **Solicitar ausência**.
2. Escolha férias, folga, licença, afastamento ou outro tipo definido pela empresa.
3. Informe início, fim e observação necessária.
4. Envie para análise do gestor/RH e acompanhe a decisão.
5. O sistema bloqueia outra solicitação enviada/aprovada que se sobreponha ao mesmo período.

O total atual representa dias corridos do intervalo. Saldo, período aquisitivo, feriados, regras sindicais e cálculo oficial ainda precisam de parametrização e validação trabalhista.

### Consultar documentos

Documentos marcados para o colaborador aparecem no portal; arquivos **Somente RH** permanecem ocultos. A publicação atual registra metadados, chave privada e checksum. Download/visualização em produção depende de object storage protegido, antivírus e URL assinada curta.

## Desempenho

1. O RH abre **Desempenho** e cria um ciclo com início, fim e período de avaliação.
2. Gestor e colaborador registram metas permitidas, com descrição, peso e prazo.
3. Durante a avaliação, registre evidências profissionais e notas conforme a política da empresa.
4. O colaborador acessa os próprios itens; o gestor acessa a equipe direta; RH e perfis autorizados administram o ciclo.
5. Antes de concluir, verifique coerência, vieses e direito de revisão.

Calibração, feedback contínuo, 9-box e PDI ainda são evoluções planejadas. O sistema não deve decidir sozinho promoção, remuneração ou desligamento.

## eSocial

1. Abra **eSocial** e clique em **+ Evento**.
2. Informe tipo, competência, chave idempotente e payload previamente validado.
3. Enfileire o evento e acompanhe processamento, aceite, rejeição ou cancelamento.
4. Em rejeição, corrija a origem e gere uma nova tentativa controlada; não duplique a mesma chave.
5. Confira protocolo e auditoria quando o adapter oficial estiver configurado.

Esta tela implementa preparação e acompanhamento. Sem certificado, XSD, assinatura, transmissão e recibo por conector homologado, ela **não comprova envio oficial**.

## Cobrança SaaS

Área exclusiva da plataforma:

1. Abra **Cobrança SaaS** para consultar medição por competência.
2. Registre ou reconcilie quantidades por métrica, como usuários ativos ou armazenamento.
3. Gere a fatura interna com competência, vencimento, moeda e valor.
4. Atualize seu estado somente após retorno confiável do gateway.
5. Compare o resumo de uso, faturas abertas e vencidas.

O ledger interno não processa cartão, Pix, nota fiscal nem liquidação. Essas operações dependem de gateway e webhooks assinados.

## Assistente corporativo

### Publicar fonte

1. Abra **Assistente** e clique em **+ Documento**.
2. Informe título e conteúdo aprovado.
3. Escolha visibilidade: Todos, Gestores/RH ou Somente RH.
4. Salve.

### Perguntar

1. Escreva pergunta objetiva.
2. Clique em **Perguntar**.
3. Leia a resposta e confira as citações.
4. Sem fonte, procure o RH.

O filtro de empresa e ACL ocorre antes da recuperação. O assistente se abstém sem evidência e não substitui política oficial nem decisão humana.

## Auditoria

Abra **Auditoria** para conferir data/hora, ator, ação, entidade, detalhes e request ID. Use a trilha para investigação e prestação de contas. Um evento prova a operação registrada, não a correção jurídica de todo o processo.

## Aparência e busca

Em **Configurações**, escolha rosa, ciano, roxo, verde-musgo ou laranja. Claro/escuro é salvo no navegador. A busca global começa com dois caracteres e respeita permissões.

## Rotina por perfil

### RH

1. confira indicadores e onboarding;
2. trate candidatos/candidaturas;
3. atualize colaboradores;
4. publique documentos e fontes aprovadas;
5. revise auditoria e exceções;
6. encerre a sessão em equipamento compartilhado.

### Colaborador

1. confira tarefas;
2. registre/consulte ponto conforme política;
3. consulte próprios holerites;
4. use o assistente conferindo fontes;
5. solicite ao RH correção de vínculo ou dado.

### Auditor

1. confirme empresa e período;
2. compare ator, entidade, diffs e request ID;
3. exporte evidências só quando autorizado;
4. registre conclusão sem alterar dados operacionais.

## Problemas comuns

| Situação | Causa | Ação |
|---|---|---|
| Credenciais inválidas | usuário/senha incorretos | confirme ou solicite redefinição |
| Sem empresa ativa | membership/tenant inativo | administrador revisa acesso |
| Permissão insuficiente | papel não permite ação | solicite revisão do papel |
| Possível duplicidade | mesmo nome + contato/registro | atualize o cadastro existente |
| Perfil não vinculado | User sem Employee | RH cria ou vincula matrícula |
| Documento já existe | competência/tipo repetidos | revise o lote |
| Ausência sobreposta | solicitação ativa no período | revise ou cancele a solicitação anterior |
| Portal sem perfil | acesso não vinculado à matrícula | RH vincula User e Employee na empresa correta |
| Assistente sem fonte | nenhuma fonte autorizada | consulte o RH |
| Evento eSocial rejeitado | validação ou retorno do adapter | confira erro, origem e chave idempotente |
| Fatura interna em aberto | sem confirmação do gateway | reconcilie pelo identificador externo |
| Sessão expirada | tempo atingido/revogação | entre novamente |

## Segurança e privacidade

- use conta individual;
- confirme a empresa ativa antes de cadastrar/exportar;
- não compartilhe senha, token ou certificado;
- minimize dados e não use dados reais em testes;
- não envie holerites ou dados de saúde por canais não aprovados;
- saia em dispositivos compartilhados;
- comunique imediatamente possível acesso indevido;
- decisões de emprego permanecem humanas.

## Solicitar suporte

Informe empresa e papel, módulo, data/hora, request ID, mensagem, passos, impacto e captura sem dados excessivos. Nunca envie senha, token, certificado ou folha completa em chamado não protegido.

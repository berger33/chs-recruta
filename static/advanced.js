const {api, views, render, head, esc, badge, fmt, money, openForm, toast} = window.CHS;
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const viewRoot = $("#view");

function empty(title, copy) {
  return `<div class="empty"><strong>${esc(title)}</strong><br>${esc(copy)}</div>`;
}

function options(items, value, label) {
  return items.map((item) => ({value: item[value], label: item[label]}));
}

views.atsAdvanced = async function atsAdvanced() {
  const [requisitions, interviews, offers, applications] = await Promise.all([
    api.get("/api/ats/requisitions"),
    api.get("/api/ats/interviews"),
    api.get("/api/ats/offers"),
    api.get("/api/applications"),
  ]);
  viewRoot.innerHTML = head(
    "ATS avançado",
    "Aprovações de headcount, entrevistas estruturadas, scorecards e ofertas.",
    '<button class="primary" id="new-requisition">+ Requisição</button><button id="new-interview">Agendar entrevista</button><button id="new-offer">Criar oferta</button>',
  ) + `<section class="kpis">
    <article class="kpi"><small>Requisições pendentes</small><strong>${requisitions.filter(item => item.status === "pending").length}</strong></article>
    <article class="kpi"><small>Entrevistas</small><strong>${interviews.length}</strong></article>
    <article class="kpi"><small>Ofertas abertas</small><strong>${offers.filter(item => ["draft", "sent"].includes(item.status)).length}</strong></article>
    <article class="kpi"><small>Candidaturas</small><strong>${applications.length}</strong></article>
  </section><section class="grid">
    <article class="panel"><h2>Requisições de pessoal</h2><div class="panel-body list">${requisitions.map(item => `
      <div class="item"><div><strong>${esc(item.code)} — ${esc(item.title)}</strong><small>${item.positions} posição(ões)</small></div>
      <div>${badge(item.status)} ${item.status === "pending" ? `<button data-approve="${item.id}">Aprovar</button>` : ""}</div></div>`).join("") || empty("Sem requisições", "Envie a primeira solicitação de headcount.")}</div></article>
    <article class="panel"><h2>Próximas entrevistas</h2><div class="panel-body list">${interviews.map(item => `
      <div class="item"><div><strong>Candidatura #${item.application_id}</strong><small>${fmt(item.scheduled_at)} · ${esc(item.location || "Local a definir")}</small></div>${badge(item.status)}</div>`).join("") || empty("Sem entrevistas", "Agende uma entrevista estruturada.")}</div></article>
  </section>`;

  $("#new-requisition").addEventListener("click", async () => {
    await openForm("Nova requisição", [
      {name: "code", label: "Código", required: true},
      {name: "title", label: "Título", required: true},
      {name: "reason", label: "Motivo", type: "select", value: "replacement", options: ["replacement", "growth", "temporary"]},
      {name: "positions", label: "Posições", type: "number", value: 1, required: true},
      {name: "description", label: "Justificativa", type: "textarea", full: true},
    ], payload => api.post("/api/ats/requisitions", {...payload, positions: Number(payload.positions), department_id: null}));
    toast("Requisição enviada para aprovação."); render("atsAdvanced");
  });
  $$('[data-approve]').forEach(button => button.addEventListener("click", async () => {
    await api.post(`/api/ats/requisitions/${button.dataset.approve}/decision`, {approved: true, reason: "Aprovado no painel"});
    toast("Requisição aprovada."); render("atsAdvanced");
  }));
  $("#new-interview").addEventListener("click", async () => {
    if (!applications.length) return toast("Cadastre uma candidatura primeiro.");
    await openForm("Agendar entrevista", [
      {name: "application_id", label: "Candidatura", type: "select", required: true, options: applications.map(item => ({value: item.id, label: `Candidatura #${item.id}`}))},
      {name: "scheduled_at", label: "Data e hora", type: "datetime-local", required: true},
      {name: "duration_minutes", label: "Duração (min)", type: "number", value: 60},
      {name: "location", label: "Local ou link"},
      {name: "notes", label: "Orientações", type: "textarea", full: true},
    ], payload => api.post("/api/ats/interviews", {...payload, application_id: Number(payload.application_id), duration_minutes: Number(payload.duration_minutes), scheduled_at: new Date(payload.scheduled_at).toISOString(), interviewer_ids: [window.CHS.context.user_id]}));
    toast("Entrevista agendada."); render("atsAdvanced");
  });
  $("#new-offer").addEventListener("click", async () => {
    if (!applications.length) return toast("Cadastre uma candidatura primeiro.");
    await openForm("Nova oferta", [
      {name: "application_id", label: "Candidatura", type: "select", required: true, options: applications.map(item => ({value: item.id, label: `Candidatura #${item.id}`}))},
      {name: "salary", label: "Salário", type: "number", required: true},
      {name: "start_date", label: "Início previsto", type: "date"},
      {name: "notes", label: "Condições", type: "textarea", full: true},
    ], payload => api.post("/api/ats/offers", {...payload, application_id: Number(payload.application_id), salary: Number(payload.salary), currency: "BRL", start_date: payload.start_date || null, expires_at: null}));
    toast("Oferta criada."); render("atsAdvanced");
  });
};

views.contracts = async function contracts() {
  const [contracts, movements, employees] = await Promise.all([
    api.get("/api/core-hr/contracts"), api.get("/api/core-hr/movements"), api.get("/api/employees"),
  ]);
  const names = new Map(employees.map(item => [item.id, item.full_name]));
  viewRoot.innerHTML = head("Contratos e movimentações", "Histórico de vínculos sem sobrescrever o passado.", '<button class="primary" id="new-contract">+ Contrato</button><button id="new-movement">Movimentação</button>') + `
    <section class="grid"><article class="panel"><h2>Contratos</h2><div class="table"><table><thead><tr><th>Colaborador</th><th>Número</th><th>Tipo</th><th>Salário</th><th>Status</th></tr></thead><tbody>
    ${contracts.map(item => `<tr><td>${esc(names.get(item.employee_id) || `#${item.employee_id}`)}</td><td>${esc(item.contract_number)}</td><td>${esc(item.contract_type)}</td><td>${money(item.salary)}</td><td>${badge(item.status)}</td></tr>`).join("") || `<tr><td colspan="5">${empty("Sem contratos", "Cadastre o primeiro vínculo histórico.")}</td></tr>`}
    </tbody></table></div></article><article class="panel"><h2>Movimentações</h2><div class="panel-body list">${movements.map(item => `<div class="item"><div><strong>${esc(names.get(item.employee_id) || `#${item.employee_id}`)}</strong><small>${esc(item.movement_type)} · ${fmt(item.effective_date)}</small></div></div>`).join("") || empty("Sem movimentações", "Promoções e transferências aparecerão aqui.")}</div></article></section>`;
  $("#new-contract").addEventListener("click", async () => {
    await openForm("Novo contrato", [
      {name: "employee_id", label: "Colaborador", type: "select", required: true, options: options(employees, "id", "full_name")},
      {name: "contract_number", label: "Número", required: true}, {name: "contract_type", label: "Tipo", value: "clt"},
      {name: "start_date", label: "Início", type: "date", required: true}, {name: "end_date", label: "Término", type: "date"},
      {name: "weekly_hours", label: "Horas semanais", type: "number", value: 44}, {name: "salary", label: "Salário", type: "number", required: true},
      {name: "status", label: "Status", type: "select", value: "active", options: ["planned", "active", "suspended", "ended"]},
    ], payload => api.post("/api/core-hr/contracts", {...payload, employee_id: Number(payload.employee_id), weekly_hours: Number(payload.weekly_hours), salary: Number(payload.salary), currency: "BRL", end_date: payload.end_date || null}));
    toast("Contrato cadastrado."); render("contracts");
  });
  $("#new-movement").addEventListener("click", async () => {
    await openForm("Nova movimentação", [
      {name: "employee_id", label: "Colaborador", type: "select", required: true, options: options(employees, "id", "full_name")},
      {name: "movement_type", label: "Tipo", type: "select", options: ["promotion", "transfer", "salary_change", "leave", "return"]},
      {name: "effective_date", label: "Vigência", type: "date", required: true}, {name: "reason", label: "Motivo"},
    ], payload => api.post("/api/core-hr/movements", {...payload, employee_id: Number(payload.employee_id), before_data: {}, after_data: {}}));
    toast("Movimentação registrada."); render("contracts");
  });
};

views.performance = async function performance() {
  const [cycles, goals] = await Promise.all([api.get("/api/performance/cycles"), api.get("/api/performance/goals")]);
  const canManage = window.CHS.context.permissions.includes("performance.manage");
  let employees = [];
  if (canManage) employees = await api.get("/api/employees");
  viewRoot.innerHTML = head("Desempenho", "Ciclos, metas e avaliações com escopo individual e de equipe.", canManage ? '<button class="primary" id="new-cycle">+ Ciclo</button><button id="new-goal">Nova meta</button>' : "") + `
    <section class="kpis"><article class="kpi"><small>Ciclos</small><strong>${cycles.length}</strong></article><article class="kpi"><small>Metas visíveis</small><strong>${goals.length}</strong></article><article class="kpi"><small>Metas concluídas</small><strong>${goals.filter(item => item.progress === 100).length}</strong></article><article class="kpi"><small>Progresso médio</small><strong>${goals.length ? Math.round(goals.reduce((sum, item) => sum + item.progress, 0) / goals.length) : 0}%</strong></article></section>
    <section class="grid"><article class="panel"><h2>Ciclos</h2><div class="panel-body list">${cycles.map(item => `<div class="item"><div><strong>${esc(item.name)}</strong><small>${fmt(item.start_date)} — ${fmt(item.end_date)}</small></div>${badge(item.status)}</div>`).join("") || empty("Sem ciclos", "Crie um ciclo de avaliação.")}</div></article>
    <article class="panel"><h2>Metas</h2><div class="panel-body list">${goals.map(item => `<div class="item"><div><strong>${esc(item.title)}</strong><small>${esc(item.target_value || "Sem alvo")}</small></div><strong>${item.progress}%</strong></div>`).join("") || empty("Sem metas", "As metas autorizadas aparecerão aqui.")}</div></article></section>`;
  $("#new-cycle")?.addEventListener("click", async () => {
    await openForm("Novo ciclo", [{name: "name", label: "Nome", required: true}, {name: "start_date", label: "Início", type: "date", required: true}, {name: "end_date", label: "Fim", type: "date", required: true}, {name: "description", label: "Descrição", type: "textarea", full: true}], payload => api.post("/api/performance/cycles", payload));
    toast("Ciclo criado."); render("performance");
  });
  $("#new-goal")?.addEventListener("click", async () => {
    if (!cycles.length) return toast("Crie um ciclo primeiro.");
    await openForm("Nova meta", [{name: "cycle_id", label: "Ciclo", type: "select", required: true, options: options(cycles, "id", "name")}, {name: "employee_id", label: "Colaborador", type: "select", required: true, options: options(employees, "id", "full_name")}, {name: "title", label: "Meta", required: true}, {name: "target_value", label: "Alvo"}, {name: "description", label: "Descrição", type: "textarea", full: true}], payload => api.post("/api/performance/goals", {...payload, cycle_id: Number(payload.cycle_id), employee_id: Number(payload.employee_id), progress: 0, status: "not_started"}));
    toast("Meta criada."); render("performance");
  });
};

views.esocial = async function esocial() {
  const events = await api.get("/api/esocial/events");
  viewRoot.innerHTML = head("eSocial", "Fila idempotente e versionada. O envio externo requer certificado e adapter homologado.", '<button class="primary" id="new-esocial">+ Evento</button>') + `<section class="panel table"><table><thead><tr><th>Evento</th><th>Referência</th><th>Layout</th><th>Status</th><th>Tentativas</th><th>Ação</th></tr></thead><tbody>${events.map(item => {
    const next = {draft: "validated", validated: "queued", rejected: "queued"}[item.status];
    return `<tr><td><strong>${esc(item.event_type)}</strong><small>${esc(item.idempotency_key)}</small></td><td>${esc(item.reference)}</td><td>${esc(item.layout_version)}</td><td>${badge(item.status)}</td><td>${item.attempts}</td><td>${next ? `<button data-esocial="${item.id}" data-next="${next}">Mover para ${next}</button>` : "—"}</td></tr>`;
  }).join("") || `<tr><td colspan="6">${empty("Sem eventos", "Crie um evento para validação local.")}</td></tr>`}</tbody></table></section>`;
  $("#new-esocial").addEventListener("click", async () => {
    await openForm("Novo evento eSocial", [{name: "event_type", label: "Tipo", value: "S-2200", required: true}, {name: "reference", label: "Referência"}, {name: "idempotency_key", label: "Chave de idempotência", required: true}, {name: "payload", label: "Payload JSON", type: "textarea", value: "{}", full: true, required: true}], payload => api.post("/api/esocial/events", {...payload, employee_id: null, layout_version: "S-1.3", payload: JSON.parse(payload.payload)}));
    toast("Evento criado como rascunho."); render("esocial");
  });
  $$('[data-esocial]').forEach(button => button.addEventListener("click", async () => {
    await api.patch(`/api/esocial/events/${button.dataset.esocial}`, {status: button.dataset.next, receipt: "", error_message: ""});
    toast("Estado do evento atualizado."); render("esocial");
  }));
};

views.billing = async function billing() {
  const [usage, invoices] = await Promise.all([api.get("/api/billing/usage"), api.get("/api/billing/invoices")]);
  let summary = null;
  try { summary = await api.get("/api/billing/summary"); } catch { /* assinatura ainda não configurada */ }
  viewRoot.innerHTML = head("Cobrança SaaS", "Plano, medição e faturas. Gateway e emissão fiscal permanecem adapters externos.", '<button class="primary" id="new-usage">Registrar uso</button><button id="new-invoice">Nova fatura</button>') + `
    <section class="kpis"><article class="kpi"><small>Plano</small><strong>${esc(summary?.plan_code || "—")}</strong></article><article class="kpi"><small>Status</small><strong>${esc(summary?.subscription_status || "—")}</strong></article><article class="kpi"><small>Limite</small><strong>${summary?.employee_limit || 0}</strong></article><article class="kpi"><small>Faturas abertas</small><strong>${summary?.open_invoices.length || 0}</strong></article></section>
    <section class="grid"><article class="panel"><h2>Consumo</h2><div class="panel-body list">${usage.map(item => `<div class="item"><div><strong>${esc(item.metric)}</strong><small>${esc(item.period)}</small></div><strong>${item.quantity}</strong></div>`).join("") || empty("Sem consumo", "Registre uma métrica mensal.")}</div></article>
    <article class="panel"><h2>Faturas</h2><div class="panel-body list">${invoices.map(item => `<div class="item"><div><strong>${esc(item.number)}</strong><small>${esc(item.period)} · vence ${fmt(item.due_date)}</small></div><div>${money(item.amount)} ${badge(item.status)}</div></div>`).join("") || empty("Sem faturas", "Crie uma fatura interna.")}</div></article></section>`;
  $("#new-usage").addEventListener("click", async () => {
    await openForm("Registrar uso", [{name: "metric", label: "Métrica", value: "employees", required: true}, {name: "period", label: "Período AAAA-MM", required: true}, {name: "quantity", label: "Quantidade", type: "number", required: true}], payload => api.put("/api/billing/usage", {...payload, quantity: Number(payload.quantity)}));
    toast("Uso atualizado."); render("billing");
  });
  $("#new-invoice").addEventListener("click", async () => {
    await openForm("Nova fatura", [{name: "number", label: "Número", required: true}, {name: "period", label: "Período AAAA-MM", required: true}, {name: "amount", label: "Valor", type: "number", required: true}, {name: "due_date", label: "Vencimento", type: "date", required: true}], payload => api.post("/api/billing/invoices", {...payload, amount: Number(payload.amount), currency: "BRL", provider_reference: ""}));
    toast("Fatura criada como rascunho."); render("billing");
  });
};

$$('#nav [data-view]').filter(button => ["atsAdvanced", "contracts", "performance", "esocial", "billing"].includes(button.dataset.view)).forEach(button => {
  button.addEventListener("click", () => document.startViewTransition ? document.startViewTransition(() => render(button.dataset.view)) : render(button.dataset.view));
});

document.addEventListener("chs:ready", event => {
  const permissions = new Set(event.detail.permissions);
  $$('#nav [data-view]').forEach(button => {
    const required = button.dataset.permission;
    if (required && !permissions.has(required)) button.hidden = true;
  });
});

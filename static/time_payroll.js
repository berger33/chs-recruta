const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const emptyState = (title, detail) => `<div class="empty"><strong>${title}</strong><small>${detail}</small></div>`;

function registerTimePayrollViews() {
  if (!window.CHS || window.CHS.views.timePayrollAdvanced) return;
  const {api, views, head, esc, badge, fmt, money, openForm, toast} = window.CHS;
  views.timePayrollAdvanced = true;

  views.time = async function timeManagement() {
    const context = window.CHS.context;
    const canManage = context.permissions.includes("time.manage");
    const canApprove = context.permissions.includes("time.adjust.approve");
    const canClose = context.permissions.includes("time.close");
    const canMark = context.permissions.includes("time.own");
    const [entries, adjustments, timesheets, summary, employees, schedules] = await Promise.all([
      api.get("/api/time-entries"),
      api.get("/api/time-management/adjustment-requests"),
      api.get("/api/time-management/timesheets"),
      api.get("/api/portal/summary").catch(() => ({employee_id: null, employee_name: null})),
      context.permissions.includes("employees.read") ? api.get("/api/employees") : Promise.resolve([]),
      canClose ? api.get("/api/time-management/schedules") : Promise.resolve([]),
    ]);
    const names = new Map(employees.map(item => [item.id, item.full_name]));
    const actions = [
      canMark && summary.employee_id ? '<button class="primary" id="mark-time">Registrar marcação</button>' : "",
      canMark && summary.employee_id ? '<button id="request-adjustment">Solicitar ajuste</button>' : "",
      canClose ? '<button id="calculate-timesheet">Calcular espelho</button><button id="new-schedule">Nova escala</button><button id="assign-schedule">Atribuir escala</button>' : "",
    ].join("");
    const adjustmentAction = item => {
      if (canApprove && item.status === "requested" && (canManage || item.employee_id !== summary.employee_id)) return `<button data-adjustment="${item.id}" data-approved="true">Aprovar</button><button data-adjustment="${item.id}" data-approved="false">Rejeitar</button>`;
      if (item.status === "requested" && item.employee_id === summary.employee_id) return `<button data-cancel-adjustment="${item.id}">Cancelar</button>`;
      return "";
    };
    const timesheetAction = item => {
      if (item.status === "open" && (canManage || item.employee_id === summary.employee_id)) return `<button data-timesheet="${item.id}" data-status="submitted">Enviar</button>`;
      if (item.status === "submitted" && canApprove && (canManage || item.employee_id !== summary.employee_id)) return `<button data-timesheet="${item.id}" data-status="approved">Aprovar</button>`;
      if (item.status === "approved" && canClose) return `<button data-timesheet="${item.id}" data-status="locked">Fechar</button>`;
      return "";
    };
    $("#view").innerHTML = head("Jornada e ponto", "Marcações originais, ajustes aprováveis e espelhos versionados. Não é REP-P homologado.", actions) + `
      <section class="kpis"><article class="kpi"><small>Marcações visíveis</small><strong>${entries.length}</strong></article><article class="kpi"><small>Ajustes pendentes</small><strong>${adjustments.filter(item => item.status === "requested").length}</strong></article><article class="kpi"><small>Espelhos</small><strong>${timesheets.length}</strong></article><article class="kpi"><small>Escalas</small><strong>${schedules.length}</strong></article></section>
      <section class="grid"><article class="panel"><h2>Marcações brutas</h2><div class="panel-body list">${entries.slice(0, 30).map(item => `<div class="item"><div><strong>${esc(item.kind)}</strong><small>${fmt(item.recorded_at)} · ${esc(item.source)}</small></div><small>${esc(item.integrity_hash.slice(0, 10))}…</small></div>`).join("") || emptyState("Sem marcações", "Registros imutáveis aparecerão aqui.")}</div></article>
      <article class="panel"><h2>Ajustes</h2><div class="panel-body list">${adjustments.map(item => `<div class="item"><div><strong>${esc(item.action)}</strong><small>${esc(names.get(item.employee_id) || (item.employee_id === summary.employee_id ? summary.employee_name : `#${item.employee_id}`))} · ${esc(item.reason)}</small></div><div>${badge(item.status)} ${adjustmentAction(item)}</div></div>`).join("") || emptyState("Sem ajustes", "Solicitações preservam as batidas originais.")}</div></article></section>
      <section class="panel"><h2>Espelhos por competência</h2><div class="panel-body list">${timesheets.map(item => `<div class="item"><div><strong>${esc(item.competence)} · versão ${item.version}</strong><small>${esc(names.get(item.employee_id) || (item.employee_id === summary.employee_id ? summary.employee_name : `#${item.employee_id}`))} · ${item.summary.worked_minutes || 0} min · ${item.summary.anomaly_count || 0} anomalia(s)</small></div><div>${badge(item.status)} ${timesheetAction(item)}</div></div>`).join("") || emptyState("Sem espelhos", "RH calcula o primeiro espelho da competência.")}</div></section>`;

    $("#mark-time")?.addEventListener("click", async () => {
      await openForm("Registrar marcação", [{name: "kind", label: "Tipo", type: "select", value: "entrada", options: ["entrada", "inicio_intervalo", "fim_intervalo", "saida"]}, {name: "recorded_at", label: "Data e hora", type: "datetime-local", required: true}, {name: "note", label: "Observação"}], payload => api.post("/api/time-entries", {employee_id: summary.employee_id, kind: payload.kind, recorded_at: payload.recorded_at, source: "manual", note: payload.note}));
      toast("Marcação original registrada."); window.CHS.render("time");
    });
    $("#request-adjustment")?.addEventListener("click", async () => {
      await openForm("Solicitar ajuste", [{name: "action", label: "Ação", type: "select", value: "add", options: ["add", "replace", "void"]}, {name: "original_entry_id", label: "Marcação original", type: "select", options: [{value: "", label: "Nenhuma"}, ...entries.map(item => ({value: item.id, label: `${item.kind} · ${fmt(item.recorded_at)}`}))]}, {name: "requested_kind", label: "Novo tipo", type: "select", options: [{value: "", label: "Nenhum"}, "entrada", "inicio_intervalo", "fim_intervalo", "saida"]}, {name: "requested_at", label: "Novo horário", type: "datetime-local"}, {name: "reason", label: "Motivo e evidência", type: "textarea", full: true, required: true}], payload => api.post("/api/time-management/adjustment-requests", {action: payload.action, original_entry_id: payload.original_entry_id ? Number(payload.original_entry_id) : null, requested_kind: payload.requested_kind || null, requested_at: payload.requested_at || null, reason: payload.reason}));
      toast("Ajuste enviado para aprovação."); window.CHS.render("time");
    });
    $("#calculate-timesheet")?.addEventListener("click", async () => {
      await openForm("Calcular espelho", [{name: "employee_id", label: "Colaborador", type: "select", options: employees.map(item => ({value: item.id, label: item.full_name})), required: true}, {name: "competence", label: "Competência AAAA-MM", required: true}], payload => api.post("/api/time-management/timesheets/calculate", {employee_id: Number(payload.employee_id), competence: payload.competence}));
      toast("Espelho calculado com trilha de versão."); window.CHS.render("time");
    });
    $("#new-schedule")?.addEventListener("click", async () => {
      await openForm("Nova escala", [{name: "name", label: "Nome", required: true}, {name: "weekly_minutes", label: "Minutos semanais", type: "number", value: 2640}, {name: "break_minutes", label: "Intervalo em minutos", type: "number", value: 60}, {name: "tolerance_minutes", label: "Tolerância em minutos", type: "number", value: 10}], payload => api.post("/api/time-management/schedules", {...payload, timezone: "America/Sao_Paulo", weekly_minutes: Number(payload.weekly_minutes), break_minutes: Number(payload.break_minutes), tolerance_minutes: Number(payload.tolerance_minutes), active: true}));
      toast("Escala criada."); window.CHS.render("time");
    });
    $("#assign-schedule")?.addEventListener("click", async () => {
      await openForm("Atribuir escala", [{name: "employee_id", label: "Colaborador", type: "select", options: employees.map(item => ({value: item.id, label: item.full_name})), required: true}, {name: "schedule_id", label: "Escala", type: "select", options: schedules.map(item => ({value: item.id, label: item.name})), required: true}, {name: "effective_from", label: "Início", type: "date", required: true}, {name: "effective_to", label: "Fim", type: "date"}], payload => api.post("/api/time-management/employee-schedules", {employee_id: Number(payload.employee_id), schedule_id: Number(payload.schedule_id), effective_from: payload.effective_from, effective_to: payload.effective_to || null}));
      toast("Escala atribuída."); window.CHS.render("time");
    });
    $$('[data-adjustment]').forEach(button => button.addEventListener("click", async () => {
      await api.post(`/api/time-management/adjustment-requests/${button.dataset.adjustment}/decision`, {approved: button.dataset.approved === "true", review_notes: "Decisão registrada pela interface"});
      toast("Ajuste decidido."); window.CHS.render("time");
    }));
    $$('[data-cancel-adjustment]').forEach(button => button.addEventListener("click", async () => {
      await api.post(`/api/time-management/adjustment-requests/${button.dataset.cancelAdjustment}/cancel`);
      toast("Solicitação de ajuste cancelada."); window.CHS.render("time");
    }));
    $$('[data-timesheet]').forEach(button => button.addEventListener("click", async () => {
      await api.patch(`/api/time-management/timesheets/${button.dataset.timesheet}`, {status: button.dataset.status});
      toast("Estado do espelho atualizado."); window.CHS.render("time");
    }));
  };

  views.payroll = async function payrollManagement() {
    const context = window.CHS.context;
    const canManage = context.permissions.includes("payroll.manage");
    const [statements, legacyDocuments, batches] = await Promise.all([
      api.get("/api/payroll/statements"),
      api.get("/api/payroll-documents"),
      canManage ? api.get("/api/payroll/batches") : Promise.resolve([]),
    ]);
    $("#view").innerHTML = head("Folha e holerites", "Lotes reconciliados e idempotentes. O sistema não calcula folha nem substitui validação contábil.", canManage ? '<button class="primary" id="import-payroll">Importar lote</button>' : "") + `
      ${canManage ? `<section class="panel"><h2>Lotes</h2><div class="panel-body list">${batches.map(batch => { const next = {uploaded: "validated", validated: "published"}[batch.status]; return `<div class="item"><div><strong>${esc(batch.competence)} · ${esc(batch.source)}</strong><small>${batch.row_count} registro(s) · líquido ${money(batch.total_net)}</small></div><div>${badge(batch.status)} ${next ? `<button data-batch="${batch.id}" data-status="${next}">Mover para ${next}</button>` : ""}</div></div>`; }).join("") || emptyState("Sem lotes", "Importe uma competência reconciliada.")}</div></section>` : ""}
      <section class="panel table"><h2>Demonstrativos</h2><table><thead><tr><th>Competência</th><th>Arquivo</th><th>Bruto</th><th>Descontos</th><th>Líquido</th><th>Publicação</th></tr></thead><tbody>${statements.map(item => `<tr><td>${esc(item.competence)}</td><td><strong>${esc(item.filename)}</strong><small>${esc(item.checksum.slice(0, 12))}…</small></td><td>${money(item.gross_amount)}</td><td>${money(item.deduction_amount)}</td><td><strong>${money(item.net_amount)}</strong></td><td>${fmt(item.published_at)}</td></tr>`).join("") || `<tr><td colspan="6">${emptyState("Nenhum demonstrativo", "Holerites publicados aparecerão aqui.")}</td></tr>`}</tbody></table></section>
      ${legacyDocuments.length ? `<section class="panel"><h2>Documentos legados</h2><div class="panel-body list">${legacyDocuments.map(item => `<div class="item"><div><strong>${esc(item.filename)}</strong><small>${esc(item.competence)} · ${esc(item.kind)}</small></div>${fmt(item.published_at)}</div>`).join("")}</div></section>` : ""}`;

    $("#import-payroll")?.addEventListener("click", async () => {
      await openForm("Importar lote de folha", [{name: "competence", label: "Competência AAAA-MM", required: true}, {name: "source", label: "Sistema de origem", required: true}, {name: "idempotency_key", label: "Chave idempotente", required: true}, {name: "rows", label: "Uma linha: matrícula|bruto|descontos|líquido|arquivo|storage_key|sha256", type: "textarea", full: true, required: true}], payload => {
        const rows = payload.rows.split("\n").filter(Boolean).map((line, index) => { const [employee_number, gross_amount, deduction_amount, net_amount, filename, storage_key, checksum] = line.split("|"); if (!checksum) throw new Error(`Linha ${index + 1} incompleta.`); return {employee_number, gross_amount: Number(gross_amount), deduction_amount: Number(deduction_amount), net_amount: Number(net_amount), currency: "BRL", filename, storage_key, checksum}; });
        return api.post("/api/payroll/batches", {competence: payload.competence, source: payload.source, idempotency_key: payload.idempotency_key, rows});
      });
      toast("Lote importado para validação."); window.CHS.render("payroll");
    });
    $$('[data-batch]').forEach(button => button.addEventListener("click", async () => {
      await api.patch(`/api/payroll/batches/${button.dataset.batch}`, {status: button.dataset.status});
      toast("Lote atualizado."); window.CHS.render("payroll");
    }));
  };
}

registerTimePayrollViews();

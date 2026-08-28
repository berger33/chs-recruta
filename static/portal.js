const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

function bindPortal() {
  if (!window.CHS) return;
  if (window.CHS.views.portal) return;
  const {api, views, head, esc, badge, fmt, openForm, toast} = window.CHS;

  views.portal = async function portal() {
    const context = window.CHS.context;
    const canManage = context.permissions.includes("portal.manage");
    const canTeam = context.permissions.includes("portal.team");
    const canFiles = context.permissions.includes("employee_files.manage");
    const [summary, requests, leaves, files, employees] = await Promise.all([
      api.get("/api/portal/summary"),
      api.get("/api/portal/requests"),
      api.get("/api/portal/leave-requests"),
      api.get("/api/portal/files"),
      canManage || canFiles ? api.get("/api/employees") : Promise.resolve([]),
    ]);
    const canDecide = canManage || canTeam;
    const requestActions = item => {
      if (canDecide && ["submitted", "in_review", "approved"].includes(item.status)) {
        return `<button data-request="${item.id}" data-status="${item.status === "approved" ? "resolved" : "approved"}">${item.status === "approved" ? "Concluir" : "Aprovar"}</button>${item.status !== "approved" ? `<button data-request="${item.id}" data-status="rejected">Rejeitar</button>` : ""}`;
      }
      return summary.employee_id === item.employee_id && ["submitted", "in_review"].includes(item.status) ? `<button data-request="${item.id}" data-status="cancelled">Cancelar</button>` : "—";
    };
    const leaveActions = item => {
      if (canDecide && item.status === "submitted") return `<button data-leave="${item.id}" data-status="approved">Aprovar</button><button data-leave="${item.id}" data-status="rejected">Rejeitar</button>`;
      return summary.employee_id === item.employee_id && item.status === "submitted" ? `<button data-leave="${item.id}" data-status="cancelled">Cancelar</button>` : "—";
    };
    const fileAction = canFiles ? '<button id="new-file">Publicar documento</button>' : "";
    $("#view").innerHTML = head("Portal do colaborador", summary.employee_name ? `Olá, ${esc(summary.employee_name)}. Acompanhe sua jornada em um só lugar.` : "Atendimento, ausências e documentos da empresa.", `<button class="primary" id="new-request">+ Solicitação</button><button id="new-leave">Solicitar ausência</button>${fileAction}`) + `
      <section class="kpis"><article class="kpi"><small>Solicitações abertas</small><strong>${summary.open_requests}</strong></article><article class="kpi"><small>Ausências pendentes</small><strong>${summary.pending_leave_requests}</strong></article><article class="kpi"><small>Documentos</small><strong>${summary.available_files}</strong></article></section>
      <section class="panel table"><h2>Solicitações</h2><table><thead><tr><th>Assunto</th><th>Categoria</th><th>Prioridade</th><th>Status</th><th>Atualização</th><th>Ação</th></tr></thead><tbody>${requests.map(item => `<tr><td><strong>${esc(item.subject)}</strong><small>${esc(item.description || "Sem descrição")}</small></td><td>${esc(item.category)}</td><td>${badge(item.priority)}</td><td>${badge(item.status)}</td><td>${fmt(item.updated_at)}</td><td>${requestActions(item)}</td></tr>`).join("") || '<tr><td colspan="6"><div class="empty"><strong>Nenhuma solicitação</strong><small>Crie a primeira quando precisar de atendimento.</small></div></td></tr>'}</tbody></table></section>
      <section class="grid"><article class="panel"><h2>Férias e ausências</h2><div class="panel-body list">${leaves.map(item => `<div class="item"><div><strong>${esc(item.leave_type)}</strong><small>${fmt(item.start_date)} a ${fmt(item.end_date)} · ${item.total_days} dia(s)</small></div><div>${badge(item.status)} ${leaveActions(item)}</div></div>`).join("") || '<div class="empty"><strong>Nenhuma ausência</strong><small>Solicitações aparecerão aqui.</small></div>'}</div></article>
      <article class="panel"><h2>Documentos</h2><div class="panel-body list">${files.map(item => `<div class="item"><div><strong>${esc(item.filename)}</strong><small>${esc(item.category)} · ${fmt(item.created_at)}</small></div>${badge(item.visibility)}</div>`).join("") || '<div class="empty"><strong>Nenhum documento</strong><small>Documentos liberados aparecerão aqui.</small></div>'}</div></article></section>`;

    $("#new-request").addEventListener("click", async () => {
      const target = canManage ? [{name: "employee_id", label: "Colaborador", type: "select", options: employees.map(item => ({value: item.id, label: item.full_name})), required: true}] : [];
      await openForm("Nova solicitação", [...target, {name: "category", label: "Categoria", type: "select", options: ["cadastro", "beneficios", "documentos", "ponto", "pagamento", "outros"], required: true}, {name: "subject", label: "Assunto", required: true}, {name: "priority", label: "Prioridade", type: "select", value: "normal", options: ["low", "normal", "high", "urgent"]}, {name: "description", label: "Descrição", type: "textarea", full: true}], payload => api.post("/api/portal/requests", {...payload, employee_id: payload.employee_id ? Number(payload.employee_id) : null}));
      toast("Solicitação enviada."); window.CHS.render("portal");
    });
    $("#new-leave").addEventListener("click", async () => {
      const target = canManage ? [{name: "employee_id", label: "Colaborador", type: "select", options: employees.map(item => ({value: item.id, label: item.full_name})), required: true}] : [];
      await openForm("Solicitar férias ou ausência", [...target, {name: "leave_type", label: "Tipo", type: "select", options: ["ferias", "folga", "licenca", "afastamento", "outros"], required: true}, {name: "start_date", label: "Início", type: "date", required: true}, {name: "end_date", label: "Fim", type: "date", required: true}, {name: "reason", label: "Observação", type: "textarea", full: true}], payload => api.post("/api/portal/leave-requests", {...payload, employee_id: payload.employee_id ? Number(payload.employee_id) : null}));
      toast("Ausência enviada para análise."); window.CHS.render("portal");
    });
    $("#new-file")?.addEventListener("click", async () => {
      await openForm("Publicar documento", [{name: "employee_id", label: "Colaborador", type: "select", options: employees.map(item => ({value: item.id, label: item.full_name})), required: true}, {name: "category", label: "Categoria", required: true}, {name: "filename", label: "Nome do arquivo", required: true}, {name: "storage_key", label: "Chave no armazenamento privado", required: true}, {name: "checksum", label: "Checksum SHA-256", required: true}, {name: "mime_type", label: "MIME type", value: "application/pdf"}, {name: "visibility", label: "Visibilidade", type: "select", value: "employee", options: ["employee", "hr_only"]}, {name: "expires_on", label: "Validade", type: "date"}], payload => api.post("/api/portal/files", {...payload, employee_id: Number(payload.employee_id), expires_on: payload.expires_on || null}));
      toast("Metadados do documento publicados."); window.CHS.render("portal");
    });
    $$('[data-request]').forEach(button => button.addEventListener("click", async () => {
      await api.patch(`/api/portal/requests/${button.dataset.request}`, {status: button.dataset.status, resolution: "", assigned_to_id: null});
      toast("Solicitação atualizada."); window.CHS.render("portal");
    }));
    $$('[data-leave]').forEach(button => button.addEventListener("click", async () => {
      await api.patch(`/api/portal/leave-requests/${button.dataset.leave}`, {status: button.dataset.status, decision_notes: ""});
      toast("Ausência atualizada."); window.CHS.render("portal");
    }));
  };

}

document.addEventListener("chs:ready", bindPortal, {once: true});
bindPortal();

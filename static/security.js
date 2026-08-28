const {api, views, head, esc, badge, fmt, openForm, toast} = window.CHS;
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const permissionLabels = {
  "audit.read": "Consultar auditoria",
  "payroll.manage": "Administrar folha e holerites",
  "employee_files.manage": "Administrar arquivos de colaboradores",
  "knowledge.manage": "Administrar conhecimento corporativo",
  "esocial.manage": "Administrar eventos eSocial",
  "contracts.manage": "Administrar contratos",
  "performance.manage": "Administrar desempenho",
  "reports.read": "Consultar relatórios",
};
const eventLabels = {
  login: "Login",
  login_mfa: "Verificação MFA",
  login_mfa_challenge: "Desafio MFA",
  logout: "Saída",
  mfa_enabled: "MFA habilitado",
  mfa_disabled: "MFA desabilitado",
  password_changed: "Senha alterada",
  password_change: "Tentativa de alterar senha",
  password_reset_requested: "Recuperação solicitada",
  password_reset_completed: "Senha recuperada",
  session_revoked: "Sessão revogada",
  sessions_revoked: "Sessões revogadas",
  step_up: "Confirmação de identidade",
  tenant_switch: "Troca de empresa",
};

function empty(title, copy) {
  return `<div class="empty"><strong>${esc(title)}</strong><br>${esc(copy)}</div>`;
}

function notice(title, message, action = "Entendi") {
  let dialog = $("#security-notice");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "security-notice";
    dialog.innerHTML = '<header><div><p class="eyebrow">Segurança</p><h2></h2></div></header><section class="security-notice-body"><pre></pre></section><footer><button class="primary"></button></footer>';
    document.body.append(dialog);
  }
  $("h2", dialog).textContent = title;
  $("pre", dialog).textContent = message;
  const button = $("button", dialog);
  button.textContent = action;
  dialog.showModal();
  return new Promise(resolve => button.addEventListener("click", () => {
    dialog.close();
    $("pre", dialog).textContent = "";
    resolve();
  }, {once: true}));
}

async function confirmIdentity() {
  await openForm("Confirmar identidade", [
    {name: "password", label: "Senha atual", type: "password", required: true, minlength: 8},
    {name: "code", label: "Código MFA ou de recuperação", required: true, minlength: 6},
  ], payload => api.post("/api/security/step-up", payload));
  toast("Identidade confirmada por 10 minutos.");
}

async function enableMfa() {
  const setup = await openForm("Preparar autenticação em duas etapas", [
    {name: "password", label: "Confirme sua senha atual", type: "password", required: true, minlength: 8},
  ], payload => api.post("/api/security/mfa/setup", payload));
  await notice(
    "Cadastre no aplicativo autenticador",
    `Chave manual:\n${setup.secret}\n\nURI de provisionamento:\n${setup.provisioning_uri}`,
    "Já cadastrei",
  );
  const enabled = await openForm("Validar o primeiro código", [
    {name: "code", label: "Código de 6 dígitos", required: true, minlength: 6, pattern: "\\d{6}"},
  ], payload => api.post("/api/security/mfa/enable", payload));
  await notice(
    "Guarde seus códigos de recuperação",
    `Cada código funciona uma única vez. Guarde-os fora deste dispositivo.\n\n${enabled.recovery_codes.join("\n")}`,
  );
  toast("MFA habilitado. Outras sessões foram encerradas.");
}

function sessionState(item) {
  if (item.revoked_at) return badge("revogada");
  if (new Date(item.expires_at) <= new Date()) return badge("expirada");
  return badge(item.current ? "atual" : "ativa");
}

function grantActions(item, context, canManage) {
  const own = item.requested_by_user_id === context.user_id;
  const expired = item.status === "approved" && item.expires_at && new Date(item.expires_at) <= new Date();
  const actions = [];
  if (item.status === "requested" && canManage && !own) {
    actions.push(`<button data-grant-decision="${item.id}" data-approved="true">Aprovar</button>`);
    actions.push(`<button data-grant-decision="${item.id}" data-approved="false">Rejeitar</button>`);
  }
  if (item.status === "approved" && own && !expired) actions.push(`<button class="primary" data-grant-activate="${item.id}">Ativar</button>`);
  if ((item.status === "requested" || (item.status === "approved" && !expired)) && (own || canManage)) actions.push(`<button data-grant-revoke="${item.id}">${item.status === "requested" ? "Cancelar" : "Revogar"}</button>`);
  return actions.join(" ");
}

function grantState(item) {
  if (item.status === "approved" && item.expires_at && new Date(item.expires_at) <= new Date()) return "expirado";
  return item.status;
}

views.security = async function security() {
  const context = window.CHS.context;
  const canManage = context.permissions.includes("security.manage");
  const [mfa, sessions, grants, events] = await Promise.all([
    api.get("/api/security/mfa"),
    api.get("/api/security/sessions"),
    api.get("/api/security/privileged-access"),
    api.get("/api/security/events?limit=50"),
  ]);
  const availablePermissions = Object.entries(permissionLabels)
    .filter(([value]) => !context.permissions.includes(value));
  const mfaActions = mfa.enabled
    ? '<button id="step-up">Confirmar identidade</button><button id="recovery-codes">Novos códigos</button><button id="disable-mfa">Desabilitar MFA</button>'
    : '<button class="primary" id="enable-mfa">Habilitar MFA</button>';
  const actions = `${context.privileged_until ? `<span class="privileged-indicator">Acesso privilegiado até ${fmt(context.privileged_until)}</span>` : ""}<button id="change-password">Alterar senha</button>`;
  $("#view").innerHTML = head("Segurança da conta", "Proteção de identidade, dispositivos e elevação temporária de acesso.", actions) + `
    <section class="security-grid">
      <article class="panel"><h2>Autenticação em duas etapas</h2><div class="panel-body">
        <div class="security-summary"><div><strong>${mfa.enabled ? "Proteção ativa" : "Proteção recomendada"}</strong><small>${mfa.enabled ? `${mfa.recovery_codes_remaining} código(s) de recuperação disponível(is)` : "Use um aplicativo autenticador compatível com TOTP."}</small></div>${badge(mfa.enabled ? "habilitada" : "desabilitada")}</div>
        <div class="actions security-actions">${mfaActions}</div>
      </div></article>
      <article class="panel"><h2>Sessões e dispositivos</h2><div class="panel-body list">
        ${sessions.map(item => `<div class="item security-item"><div><strong>${esc(item.device_name || "Dispositivo")}${item.privileged ? " · acesso privilegiado" : ""}</strong><small>${esc(item.ip_address || "IP não informado")} · vista ${fmt(item.last_seen_at)} · expira ${fmt(item.expires_at)}</small></div><div>${sessionState(item)} ${!item.revoked_at && !item.current ? `<button data-session-revoke="${item.id}">Encerrar</button>` : ""}</div></div>`).join("") || empty("Sem sessões", "Nenhuma sessão foi encontrada.")}
        <div class="actions"><button id="revoke-other-sessions">Encerrar todas as outras</button></div>
      </div></article>
    </section>
    <section class="panel security-section"><h2>Acesso privilegiado temporário</h2><div class="panel-body">
      <div class="security-copy"><p>Permissões sensíveis são concedidas por tempo limitado, com motivo, MFA e aprovação de outra pessoa autorizada.</p>${availablePermissions.length ? '<button class="primary" id="request-privileged">Solicitar acesso</button>' : ""}</div>
      <div class="list">${grants.map(item => `<div class="item security-item"><div><strong>${item.requested_permissions.map(value => esc(permissionLabels[value] || value)).join(", ")}</strong><small>${esc(item.reason)} · ${item.requested_duration_minutes} min · solicitado ${fmt(item.created_at)}${item.expires_at ? ` · válido até ${fmt(item.expires_at)}` : ""}${item.review_notes ? ` · ${esc(item.review_notes)}` : ""}</small></div><div>${badge(grantState(item))} ${grantActions(item, context, canManage)}</div></div>`).join("") || empty("Nenhuma solicitação", "A elevação de acesso sempre deixa evidência.")}</div>
    </div></section>
    <section class="panel security-section"><h2>${canManage ? "Eventos de segurança da empresa" : "Seus eventos de segurança"}</h2><div class="panel-body list">
      ${events.map(item => `<div class="item security-item"><div><strong>${esc(eventLabels[item.event_type] || item.event_type)}</strong><small>${fmt(item.created_at)} · ${esc(item.ip_address || "IP não informado")} · ${esc(item.request_id || "sem request ID")}</small></div>${badge(item.outcome)}</div>`).join("") || empty("Sem eventos", "Eventos de autenticação e proteção aparecerão aqui.")}
    </div></section>`;

  $("#enable-mfa")?.addEventListener("click", async () => { await enableMfa(); window.CHS.render("security"); });
  $("#step-up")?.addEventListener("click", confirmIdentity);
  $("#recovery-codes")?.addEventListener("click", async () => {
    const result = await openForm("Gerar novos códigos de recuperação", [
      {name: "password", label: "Senha atual", type: "password", required: true, minlength: 8},
      {name: "code", label: "Código MFA ou de recuperação", required: true, minlength: 6},
    ], payload => api.post("/api/security/mfa/recovery-codes", payload));
    await notice("Novos códigos de recuperação", result.recovery_codes.join("\n"));
    window.CHS.render("security");
  });
  $("#disable-mfa")?.addEventListener("click", async () => {
    await openForm("Desabilitar MFA", [
      {name: "password", label: "Senha atual", type: "password", required: true, minlength: 8},
      {name: "code", label: "Código MFA ou de recuperação", required: true, minlength: 6},
    ], payload => api.post("/api/security/mfa/disable", payload));
    toast("MFA desabilitado e outras sessões encerradas."); window.CHS.render("security");
  });
  $("#change-password")?.addEventListener("click", async () => {
    await openForm("Alterar senha", [
      {name: "current_password", label: "Senha atual", type: "password", required: true, minlength: 8},
      {name: "new_password", label: "Nova senha (mínimo de 15 caracteres)", type: "password", required: true, minlength: 15},
      {name: "confirm_password", label: "Confirmar nova senha", type: "password", required: true, minlength: 15},
      ...(mfa.enabled ? [{name: "mfa_code", label: "Código MFA ou de recuperação", required: true, minlength: 6}] : []),
    ], payload => api.post("/api/security/password/change", payload));
    toast("Senha alterada e outras sessões encerradas."); window.CHS.render("security");
  });
  $$("[data-session-revoke]").forEach(button => button.addEventListener("click", async () => {
    await api.delete(`/api/security/sessions/${button.dataset.sessionRevoke}`);
    toast("Sessão encerrada."); window.CHS.render("security");
  }));
  $("#revoke-other-sessions")?.addEventListener("click", async () => {
    await api.post("/api/security/sessions/revoke-others", {});
    toast("Outras sessões encerradas."); window.CHS.render("security");
  });
  $("#request-privileged")?.addEventListener("click", async () => {
    await openForm("Solicitar acesso privilegiado", [
      {name: "permission", label: "Permissão temporária", type: "select", required: true, options: availablePermissions.map(([value, label]) => ({value, label}))},
      {name: "duration_minutes", label: "Duração", type: "select", value: "30", options: [{value: "15", label: "15 minutos"}, {value: "30", label: "30 minutos"}, {value: "60", label: "60 minutos"}, {value: "120", label: "120 minutos"}]},
      {name: "reason", label: "Motivo verificável", type: "textarea", full: true, required: true, minlength: 15},
    ], payload => api.post("/api/security/privileged-access", {requested_permissions: [payload.permission], reason: payload.reason, duration_minutes: Number(payload.duration_minutes)}));
    toast("Solicitação enviada para aprovação independente."); window.CHS.render("security");
  });
  $$("[data-grant-decision]").forEach(button => button.addEventListener("click", async () => {
    const approved = button.dataset.approved === "true";
    await openForm(approved ? "Aprovar acesso temporário" : "Rejeitar acesso temporário", [
      {name: "review_notes", label: "Justificativa da decisão", type: "textarea", full: true, required: true, minlength: 5},
    ], payload => api.post(`/api/security/privileged-access/${button.dataset.grantDecision}/decision`, {approved, review_notes: payload.review_notes}));
    toast("Decisão registrada com auditoria."); window.CHS.render("security");
  }));
  $$("[data-grant-activate]").forEach(button => button.addEventListener("click", async () => {
    await api.post(`/api/security/privileged-access/${button.dataset.grantActivate}/activate`, {});
    toast("Sessão privilegiada ativada."); location.reload();
  }));
  $$("[data-grant-revoke]").forEach(button => button.addEventListener("click", async () => {
    await api.post(`/api/security/privileged-access/${button.dataset.grantRevoke}/revoke`, {});
    toast("Acesso temporário cancelado ou revogado."); location.reload();
  }));
};

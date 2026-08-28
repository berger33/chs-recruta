const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const emptyState = (title, detail) => `<div class="empty"><strong>${title}</strong><small>${detail}</small></div>`;

function registerWorkforceViews() {
  if (!window.CHS || window.CHS.views.onboardingAdvanced) return;
  const {api, views, head, esc, badge, fmt, money, openForm, toast} = window.CHS;

  views.onboardingAdvanced = true;
  views.onboarding = async function onboarding() {
    const [items, employees, templates] = await Promise.all([
      api.get("/api/onboarding"),
      api.get("/api/employees"),
      api.get("/api/workforce/onboarding/templates"),
    ]);
    const names = new Map(employees.map(item => [item.id, item.full_name]));
    $("#view").innerHTML = head("Onboarding", "Checklists reutilizáveis, responsáveis e prazos relativos à admissão.", '<button class="primary" id="apply-template">Aplicar template</button><button id="new-template">Novo template</button><button id="new-task">Tarefa avulsa</button>') + `
      <section class="grid"><article class="panel"><h2>Templates</h2><div class="panel-body list">${templates.map(template => `<div class="item"><div><strong>${esc(template.name)}</strong><small>${template.items.length} tarefa(s) · ${esc(template.description || "Sem descrição")}</small></div>${badge(template.active ? "ativo" : "inativo")}</div>`).join("") || emptyState("Nenhum template", "Crie um checklist padrão para admissões.")}</div></article>
      <article class="panel"><h2>Resumo</h2><div class="panel-body list"><div class="item"><span>Pendentes</span><strong>${items.filter(item => item.status === "pendente").length}</strong></div><div class="item"><span>Em andamento</span><strong>${items.filter(item => item.status === "em_andamento").length}</strong></div><div class="item"><span>Concluídas</span><strong>${items.filter(item => item.status === "concluida").length}</strong></div></div></article></section>
      <section class="panel"><h2>Tarefas por colaborador</h2><div class="panel-body list">${items.map(item => `<div class="item"><div><strong>${esc(item.title)}</strong><small>${esc(names.get(item.employee_id) || `#${item.employee_id}`)} · ${fmt(item.due_date)}</small></div><div>${badge(item.status)} ${item.status !== "concluida" ? `<button data-complete="${item.id}">Concluir</button>` : ""}</div></div>`).join("") || emptyState("Nenhuma tarefa", "Aplique um template ou crie uma tarefa avulsa.")}</div></section>`;

    $("#new-template").addEventListener("click", async () => {
      await openForm("Novo template", [{name: "name", label: "Nome", required: true}, {name: "description", label: "Descrição", type: "textarea", full: true}, {name: "items", label: "Tarefas — uma por linha: dias|responsável|título|descrição", type: "textarea", value: "0|employee|Conferir dados|Revise seus dados cadastrais\n1|manager|Boas-vindas|Apresente a equipe", full: true, required: true}], payload => {
        const items = payload.items.split("\n").filter(Boolean).map((line, index) => {
          const [days, role, title, ...description] = line.split("|");
          if (!title || !["employee", "manager", "hr", "it", "facilities"].includes(role)) throw new Error(`Linha ${index + 1} inválida.`);
          return {title: title.trim(), description: description.join("|").trim(), due_offset_days: Number(days), assigned_role: role, position: index + 1, required: true};
        });
        return api.post("/api/workforce/onboarding/templates", {name: payload.name, description: payload.description, active: true, items});
      });
      toast("Template criado."); window.CHS.render("onboarding");
    });
    $("#apply-template").addEventListener("click", async () => {
      await openForm("Aplicar template", [{name: "template_id", label: "Template", type: "select", required: true, options: templates.filter(item => item.active).map(item => ({value: item.id, label: item.name}))}, {name: "employee_id", label: "Colaborador", type: "select", required: true, options: employees.map(item => ({value: item.id, label: item.full_name}))}, {name: "anchor_date", label: "Data-base (opcional)", type: "date"}], payload => api.post(`/api/workforce/onboarding/templates/${Number(payload.template_id)}/apply`, {employee_id: Number(payload.employee_id), anchor_date: payload.anchor_date || null}));
      toast("Checklist aplicado sem duplicidade."); window.CHS.render("onboarding");
    });
    $("#new-task").addEventListener("click", async () => {
      await openForm("Tarefa avulsa", [{name: "employee_id", label: "Colaborador", type: "select", required: true, options: employees.map(item => ({value: item.id, label: item.full_name}))}, {name: "title", label: "Tarefa", required: true}, {name: "due_date", label: "Prazo", type: "date"}, {name: "description", label: "Orientações", type: "textarea", full: true}], payload => api.post("/api/onboarding", {...payload, employee_id: Number(payload.employee_id), due_date: payload.due_date || null, status: "pendente", assigned_to_id: null}));
      toast("Tarefa criada."); window.CHS.render("onboarding");
    });
    $$('[data-complete]').forEach(button => button.addEventListener("click", async () => {
      await api.patch(`/api/onboarding/${button.dataset.complete}`, {status: "concluida"});
      toast("Tarefa concluída."); window.CHS.render("onboarding");
    }));
  };

  views.benefits = async function benefits() {
    const context = window.CHS.context;
    const canManage = context.permissions.includes("benefits.manage");
    const [plans, enrollments, employees, eligibility] = await Promise.all([
      api.get("/api/benefits"),
      api.get("/api/workforce/benefits/enrollments"),
      canManage ? api.get("/api/employees") : Promise.resolve([]),
      canManage ? Promise.resolve([]) : api.get("/api/workforce/benefits/eligibility"),
    ]);
    const names = new Map(employees.map(item => [item.id, item.full_name]));
    const planNames = new Map(plans.map(item => [item.id, item.name]));
    const action = canManage ? '<button class="primary" id="new-benefit">+ Benefício</button><button id="new-enrollment">Nova adesão</button>' : "";
    $("#view").innerHTML = head("Benefícios", "Catálogo, elegibilidade, solicitações e vigências.", action) + `
      <section class="grid"><article class="panel"><h2>Catálogo e elegibilidade</h2><div class="panel-body list">${plans.map(plan => {
        const status = eligibility.find(item => item.plan_id === plan.id);
        const request = status?.eligible && !enrollments.some(item => item.plan_id === plan.id && ["requested", "active"].includes(item.status)) ? `<button data-enroll="${plan.id}">Solicitar</button>` : "";
        const rule = canManage ? `<button data-rule="${plan.id}">Regra</button>` : "";
        return `<div class="item"><div><strong>${esc(plan.name)}</strong><small>${esc(plan.provider)} · ${money(plan.employee_cost)}${status ? ` · ${esc(status.reason)}` : ""}</small></div><div>${status ? badge(status.eligible ? "elegível" : "não elegível") : ""} ${request} ${rule}</div></div>`;
      }).join("") || emptyState("Nenhum benefício", "Cadastre o primeiro plano.")}</div></article>
      <article class="panel"><h2>Adesões</h2><div class="panel-body list">${enrollments.map(item => `<div class="item"><div><strong>${esc(planNames.get(item.plan_id) || `Plano #${item.plan_id}`)}</strong><small>${canManage ? esc(names.get(item.employee_id) || `Colaborador #${item.employee_id}`) : `Solicitado em ${fmt(item.requested_at)}`}</small></div><div>${badge(item.status)} ${canManage && item.status === "requested" ? `<button data-benefit-decision="${item.id}" data-status="active">Ativar</button><button data-benefit-decision="${item.id}" data-status="rejected">Rejeitar</button>` : ""}${canManage && item.status === "active" ? `<button data-benefit-decision="${item.id}" data-status="cancelled">Encerrar</button>` : ""}${!canManage && item.status === "requested" ? `<button data-benefit-decision="${item.id}" data-status="cancelled">Cancelar</button>` : ""}</div></div>`).join("") || emptyState("Nenhuma adesão", "As solicitações aparecerão aqui.")}</div></article></section>`;

    $("#new-benefit")?.addEventListener("click", async () => {
      await openForm("Novo benefício", [{name: "name", label: "Nome", required: true}, {name: "category", label: "Categoria"}, {name: "provider", label: "Fornecedor"}, {name: "employee_cost", label: "Custo do colaborador", type: "number", value: 0}], payload => api.post("/api/benefits", {...payload, employee_cost: Number(payload.employee_cost), active: true}));
      toast("Benefício cadastrado."); window.CHS.render("benefits");
    });
    $("#new-enrollment")?.addEventListener("click", async () => {
      await openForm("Nova adesão", [{name: "employee_id", label: "Colaborador", type: "select", required: true, options: employees.map(item => ({value: item.id, label: item.full_name}))}, {name: "plan_id", label: "Benefício", type: "select", required: true, options: plans.map(item => ({value: item.id, label: item.name}))}, {name: "effective_on", label: "Início pretendido", type: "date"}], payload => api.post("/api/workforce/benefits/enrollments", {employee_id: Number(payload.employee_id), plan_id: Number(payload.plan_id), effective_on: payload.effective_on || null}));
      toast("Adesão criada para análise."); window.CHS.render("benefits");
    });
    $$('[data-rule]').forEach(button => button.addEventListener("click", async () => {
      await openForm("Regra de elegibilidade", [{name: "employment_status", label: "Vínculo exigido", type: "select", value: "ativo", options: [{value: "", label: "Qualquer"}, "pre_admissao", "ativo", "afastado", "desligado"]}, {name: "minimum_tenure_days", label: "Carência em dias", type: "number", value: 0}], payload => api.put(`/api/workforce/benefits/${button.dataset.rule}/eligibility`, {department_id: null, employment_status: payload.employment_status, minimum_tenure_days: Number(payload.minimum_tenure_days), active: true}));
      toast("Regra atualizada."); window.CHS.render("benefits");
    }));
    $$('[data-enroll]').forEach(button => button.addEventListener("click", async () => {
      await api.post("/api/workforce/benefits/enrollments", {plan_id: Number(button.dataset.enroll), employee_id: null, effective_on: null});
      toast("Adesão solicitada."); window.CHS.render("benefits");
    }));
    $$('[data-benefit-decision]').forEach(button => button.addEventListener("click", async () => {
      await api.patch(`/api/workforce/benefits/enrollments/${button.dataset.benefitDecision}`, {status: button.dataset.status, effective_on: null, ends_on: null, employee_contribution: null, employer_contribution: null, decision_notes: ""});
      toast("Adesão atualizada."); window.CHS.render("benefits");
    }));
  };
}

registerWorkforceViews();

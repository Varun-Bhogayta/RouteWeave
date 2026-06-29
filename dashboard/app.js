/* RouteWeave Dashboard — Vanilla JS, zero dependencies */
(function () {
  "use strict";

  const API = window.location.origin;
  let editingTierId = null;

  // ── Navigation ─────────────────────────────────────────────
  document.querySelectorAll(".nav-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var view = btn.dataset.view;
      showView(view);
    });
  });

  function showView(name) {
    document.querySelectorAll(".view").forEach(function (v) { v.classList.remove("active"); });
    document.querySelectorAll(".nav-btn").forEach(function (b) { b.classList.remove("active"); });
    var viewEl = document.getElementById("view-" + name);
    var navEl = document.getElementById("nav-" + name);
    if (viewEl) viewEl.classList.add("active");
    if (navEl) navEl.classList.add("active");
    if (name === "tiers") loadTiers();
    if (name === "budget") loadBudget();
  }

  function showEditView(tier) {
    document.querySelectorAll(".view").forEach(function (v) { v.classList.remove("active"); });
    document.getElementById("view-edit").classList.add("active");
    var title = document.getElementById("edit-title");
    var form = document.getElementById("tier-form");
    var idField = document.getElementById("field-id");
    hideFormError();

    if (tier) {
      editingTierId = tier.id;
      title.textContent = "Edit Tier";
      idField.value = tier.id;
      idField.readOnly = true;
      document.getElementById("field-label").value = tier.label;
      document.getElementById("field-model").value = tier.model;
      document.getElementById("field-provider").value = tier.provider;
      document.getElementById("field-max-tokens").value = tier.cost_limit.max_tokens_per_request;
      document.getElementById("field-max-usd").value = tier.cost_limit.max_usd_per_day || "";
      setCheckboxes("complexity", tier.conditions.complexity);
      setCheckboxes("category", tier.conditions.category);
    } else {
      editingTierId = null;
      title.textContent = "Add New Tier";
      form.reset();
      idField.readOnly = false;
    }
  }

  function setCheckboxes(name, values) {
    document.querySelectorAll('input[name="' + name + '"]').forEach(function (cb) {
      cb.checked = values.indexOf(cb.value) !== -1;
    });
  }

  function getCheckedValues(name) {
    var vals = [];
    document.querySelectorAll('input[name="' + name + '"]:checked').forEach(function (cb) {
      vals.push(cb.value);
    });
    return vals;
  }

  // ── Buttons ────────────────────────────────────────────────
  document.getElementById("btn-add-tier").addEventListener("click", function () { showEditView(null); });
  document.getElementById("btn-cancel-edit").addEventListener("click", function () { showView("tiers"); });
  document.getElementById("btn-cancel-form").addEventListener("click", function () { showView("tiers"); });
  document.getElementById("btn-refresh-budget").addEventListener("click", function () { loadBudget(); });
  document.getElementById("btn-send-test").addEventListener("click", function () { sendTest(); });

  // ── Form submit ────────────────────────────────────────────
  document.getElementById("tier-form").addEventListener("submit", function (e) {
    e.preventDefault();
    saveTier();
  });

  // ── API helpers ────────────────────────────────────────────
  function api(method, path, body) {
    var opts = { method: method, headers: { "Content-Type": "application/json" } };
    if (body) opts.body = JSON.stringify(body);
    return fetch(API + path, opts).then(function (r) {
      if (!r.ok) return r.json().then(function (d) { throw d; });
      return r.json();
    });
  }

  // ── Load Tiers ─────────────────────────────────────────────
  function loadTiers() {
    var grid = document.getElementById("tier-grid");
    grid.innerHTML = '<div class="loading"><span class="spinner"></span>Loading tiers...</div>';
    api("GET", "/tiers").then(function (data) {
      if (!data.tiers || data.tiers.length === 0) {
        grid.innerHTML = '<div class="empty-state"><p>No tiers configured.</p><button class="btn btn-primary" onclick="document.getElementById(\'btn-add-tier\').click()">+ Add Your First Tier</button></div>';
        return;
      }
      grid.innerHTML = "";
      data.tiers.forEach(function (t) { grid.appendChild(createTierCard(t)); });
    }).catch(function (err) {
      grid.innerHTML = '<div class="empty-state"><p>Failed to load tiers.</p></div>';
    });
  }

  function createTierCard(tier) {
    var card = document.createElement("div");
    card.className = "tier-card";
    var complexityChips = tier.conditions.complexity.map(function (c) { return '<span class="chip">' + c + '</span>'; }).join("");
    var categoryChips = tier.conditions.category.map(function (c) { return '<span class="chip">' + c + '</span>'; }).join("");
    var usdCap = tier.cost_limit.max_usd_per_day !== null ? "$" + tier.cost_limit.max_usd_per_day.toFixed(2) + "/day" : "unlimited";

    card.innerHTML =
      '<div class="tier-card-header">' +
        '<div><div class="tier-card-title">' + esc(tier.label) + '</div><div class="tier-card-id">' + esc(tier.id) + '</div></div>' +
        '<span class="provider-badge ' + tier.provider + '">' + tier.provider + '</span>' +
      '</div>' +
      '<div class="tier-card-body"><div class="tier-meta">' +
        '<div class="tier-meta-row"><span class="tier-meta-label">Model</span><span class="tier-meta-value">' + esc(tier.model) + '</span></div>' +
        '<div class="tier-meta-row"><span class="tier-meta-label">Complexity</span><div>' + complexityChips + '</div></div>' +
        '<div class="tier-meta-row"><span class="tier-meta-label">Category</span><div>' + categoryChips + '</div></div>' +
        '<div class="tier-meta-row"><span class="tier-meta-label">Token cap</span><span class="tier-meta-value">' + tier.cost_limit.max_tokens_per_request.toLocaleString() + '</span></div>' +
        '<div class="tier-meta-row"><span class="tier-meta-label">USD cap</span><span class="tier-meta-value">' + usdCap + '</span></div>' +
      '</div></div>' +
      '<div class="tier-card-footer"></div>';

    var footer = card.querySelector(".tier-card-footer");
    var editBtn = document.createElement("button");
    editBtn.className = "btn btn-ghost btn-sm";
    editBtn.textContent = "Edit";
    editBtn.addEventListener("click", function () { showEditView(tier); });

    var delBtn = document.createElement("button");
    delBtn.className = "btn btn-danger btn-sm";
    delBtn.textContent = "Delete";
    delBtn.addEventListener("click", function () { deleteTier(tier.id); });

    footer.appendChild(editBtn);
    footer.appendChild(delBtn);
    return card;
  }

  // ── Save Tier ──────────────────────────────────────────────
  function saveTier() {
    var complexity = getCheckedValues("complexity");
    var category = getCheckedValues("category");
    if (complexity.length === 0) { showFormError("Select at least one complexity level."); return; }
    if (category.length === 0) { showFormError("Select at least one category."); return; }

    var maxUsd = document.getElementById("field-max-usd").value;
    var tierData = {
      id: document.getElementById("field-id").value.trim(),
      label: document.getElementById("field-label").value.trim(),
      model: document.getElementById("field-model").value.trim(),
      provider: document.getElementById("field-provider").value,
      conditions: { complexity: complexity, category: category },
      cost_limit: {
        max_tokens_per_request: parseInt(document.getElementById("field-max-tokens").value, 10),
        max_usd_per_day: maxUsd ? parseFloat(maxUsd) : null
      },
      fallback: null
    };

    var method = editingTierId ? "PUT" : "POST";
    var path = editingTierId ? "/tiers/" + editingTierId : "/tiers";

    api(method, path, tierData).then(function () {
      return api("POST", "/reload");
    }).then(function () {
      showView("tiers");
    }).catch(function (err) {
      var msg = (err && err.detail && err.detail.message) ? err.detail.message : "Failed to save tier.";
      showFormError(msg);
    });
  }

  // ── Delete Tier ────────────────────────────────────────────
  function deleteTier(id) {
    if (!confirm("Delete tier '" + id + "'?")) return;
    api("DELETE", "/tiers/" + id).then(function () {
      return api("POST", "/reload");
    }).then(function () {
      loadTiers();
    }).catch(function () {
      alert("Failed to delete tier.");
    });
  }

  // ── Budget ─────────────────────────────────────────────────
  function loadBudget() {
    var tbody = document.getElementById("budget-tbody");
    var dateEl = document.getElementById("budget-date");
    tbody.innerHTML = '<tr><td colspan="4" class="loading"><span class="spinner"></span>Loading...</td></tr>';

    Promise.all([api("GET", "/budget"), api("GET", "/tiers")]).then(function (results) {
      var budgetData = results[0];
      var tiersData = results[1];
      dateEl.textContent = budgetData.date;
      tbody.innerHTML = "";

      var tierMap = {};
      tiersData.tiers.forEach(function (t) { tierMap[t.id] = t; });

      tiersData.tiers.forEach(function (t) {
        var spent = budgetData.tiers[t.id] || 0;
        var cap = t.cost_limit.max_usd_per_day;
        var row = document.createElement("tr");

        var pct = 0;
        var barColor = "green";
        var capText = "unlimited";
        var barHtml = '<span style="color:var(--text-muted)">unlimited</span>';

        if (cap !== null) {
          pct = Math.min((spent / cap) * 100, 100);
          capText = "$" + cap.toFixed(2);
          if (pct >= 90) barColor = "red";
          else if (pct >= 70) barColor = "amber";
          barHtml = '<div class="usage-bar-container"><div class="usage-bar ' + barColor + '" style="width:' + pct.toFixed(1) + '%"></div></div><div class="usage-text">' + pct.toFixed(1) + '%</div>';
        }

        row.innerHTML =
          '<td>' + esc(t.id) + '</td>' +
          '<td>' + capText + '</td>' +
          '<td>$' + spent.toFixed(4) + '</td>' +
          '<td>' + barHtml + '</td>';
        tbody.appendChild(row);
      });

      if (tiersData.tiers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No tiers configured.</td></tr>';
      }
    }).catch(function () {
      tbody.innerHTML = '<tr><td colspan="4" class="empty-state">Failed to load budget data.</td></tr>';
    });
  }

  // ── Test Prompt ────────────────────────────────────────────
  function sendTest() {
    var prompt = document.getElementById("test-prompt").value.trim();
    if (!prompt) return;
    var role = document.getElementById("test-role").value;
    var resultEl = document.getElementById("test-result");
    resultEl.style.display = "block";
    resultEl.innerHTML = '<div class="loading"><span class="spinner"></span>Routing prompt...</div>';

    api("POST", "/route", { prompt: prompt, user_role: role, conversation_history: [], budget_state: {} })
      .then(function (data) {
        resultEl.innerHTML =
          '<div class="result-card">' +
            '<div class="result-card-header"><span class="tier-name">' + esc(data.tier_id) + ' → ' + esc(data.model) + '</span><span class="latency">' + data.latency_ms.toFixed(1) + 'ms</span></div>' +
            '<div class="result-card-body">' +
              '<div class="result-section"><div class="result-section-title">Classifier Output</div><div class="result-json">' + esc(JSON.stringify(data.classifier_output, null, 2)) + '</div></div>' +
              '<div class="result-section"><div class="result-section-title">Response</div><div class="result-response">' + esc(data.response) + '</div></div>' +
              '<div class="result-section"><div class="result-meta"><span>Provider: ' + esc(data.provider) + '</span><span>Cost: $' + data.estimated_cost_usd.toFixed(4) + '</span></div></div>' +
            '</div>' +
          '</div>';
      })
      .catch(function (err) {
        var errKey = (err && err.detail && err.detail.error) ? err.detail.error : "unknown_error";
        var errMsg = (err && err.detail && err.detail.message) ? err.detail.message : JSON.stringify(err);
        resultEl.innerHTML =
          '<div class="error-card"><div class="error-card-title">' + esc(errKey) + '</div><div class="error-card-message">' + esc(errMsg) + '</div></div>';
      });
  }

  // ── Health check ───────────────────────────────────────────
  function checkHealth() {
    var dot = document.getElementById("health-dot");
    var text = document.getElementById("health-text");
    api("GET", "/health").then(function (data) {
      dot.className = "status-dot ok";
      text.textContent = data.tier_count + " tiers | Redis " + (data.redis_connected ? "✓" : "✗");
    }).catch(function () {
      dot.className = "status-dot error";
      text.textContent = "Disconnected";
    });
  }

  // ── Helpers ────────────────────────────────────────────────
  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function showFormError(msg) {
    var el = document.getElementById("form-error");
    el.textContent = msg;
    el.classList.add("visible");
  }

  function hideFormError() {
    var el = document.getElementById("form-error");
    el.textContent = "";
    el.classList.remove("visible");
  }

  // ── Init ───────────────────────────────────────────────────
  loadTiers();
  checkHealth();
  setInterval(checkHealth, 30000);
})();

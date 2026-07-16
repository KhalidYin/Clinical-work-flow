(function () {
  "use strict";

  const state = {
    studies: [],
    selectedStudyId: "",
    status: null,
    events: [],
    reviews: [],
    artifacts: [],
    context: null,
    provenance: null,
    audit: [],
    selectedArtifactId: "",
    activeRunId: "",
    loading: false,
  };

  const stageLabels = {
    protocol_analysis: "Protocol",
    sap_generation: "SAP",
    sdtm_spec: "SDTM Spec",
    sdtm_programming: "SDTM Program",
    adam_spec: "ADaM Spec",
    adam_programming: "ADaM Program",
    tfl_shell_design: "TFL Shell",
    tfl_programming: "TFL Program",
    qc_validation: "QC",
    submission_packaging: "Submission",
  };

  const runStateLabels = {
    idle: "Idle",
    queued: "Queued",
    running: "Running",
    blocked_review: "Blocked by review",
    blocked_error: "Blocked by error",
    failed: "Failed",
    completed: "Completed",
  };

  const decisionLabels = {
    approved: "批准",
    modified: "修改后批准",
    rejected: "拒绝",
  };

  const $ = (id) => document.getElementById(id);

  document.addEventListener("DOMContentLoaded", init);

  async function init() {
    bindEvents();
    await loadStudies();
    routeFromHash();
  }

  function bindEvents() {
    $("refresh-studies").addEventListener("click", async () => {
      await loadStudies();
      if (state.selectedStudyId) {
        await loadStudy(state.selectedStudyId);
      }
    });
    $("study-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-study-id]");
      if (button) {
        const nextStudyId = button.dataset.studyId;
        if (nextStudyId === state.selectedStudyId) {
          loadStudy(nextStudyId);
        } else {
          window.location.hash = `#/studies/${encodeURIComponent(nextStudyId)}`;
        }
      }
    });
    window.addEventListener("hashchange", routeFromHash);
    $("run-form").addEventListener("submit", submitRunRequest);
    $("resume-run").addEventListener("click", submitResumeRequest);
    $("review-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-submit-review]");
      if (button) {
        submitReviewDecision(button.dataset.submitReview);
      }
    });
    $("artifact-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-artifact-id]");
      if (button) {
        selectArtifact(button.dataset.artifactId);
      }
    });
    $("audit-filter").addEventListener("change", renderAudit);
    $("audit-filter").addEventListener("change", () => {
      setAuditFilterUrl($("audit-filter").value);
    });
  }

  async function loadStudies() {
    setApiStatus("loading", "API 连接中");
    setText("study-list-message", "正在读取 Study 列表…");
    try {
      const payload = await apiGet("/api/v1/studies");
      state.studies = payload.studies || [];
      renderStudies(payload.partial_errors || []);
      setApiStatus("ok", "API 已连接");
    } catch (error) {
      state.studies = [];
      renderStudies([]);
      setApiStatus("danger", "API 错误");
      setText("study-list-message", `读取失败：${error.message}`);
    }
  }

  function routeFromHash() {
    const match = window.location.hash.match(/^#\/studies\/([^/]+)$/);
    if (!match) {
      state.selectedStudyId = "";
      state.status = null;
      state.events = [];
      state.reviews = [];
      state.artifacts = [];
      state.context = null;
      state.provenance = null;
      state.audit = [];
      state.selectedArtifactId = "";
      state.activeRunId = "";
      renderAll();
      return;
    }
    const studyId = decodeURIComponent(match[1]);
    if (studyId !== state.selectedStudyId) {
      state.selectedStudyId = studyId;
      loadStudy(studyId);
    }
  }

  async function loadStudy(studyId) {
    state.loading = true;
    renderAll();
    try {
      const [status, events, reviews, artifacts, context, provenance, audit] = await Promise.all([
        apiGet(`/api/v1/studies/${encodeURIComponent(studyId)}/status`),
        apiGet(`/api/v1/studies/${encodeURIComponent(studyId)}/events`),
        apiGet(`/api/v1/studies/${encodeURIComponent(studyId)}/reviews`),
        apiGet(`/api/v1/studies/${encodeURIComponent(studyId)}/artifacts`),
        apiGet(`/api/v1/studies/${encodeURIComponent(studyId)}/context`),
        apiGet(`/api/v1/studies/${encodeURIComponent(studyId)}/provenance`),
        apiGet(`/api/v1/studies/${encodeURIComponent(studyId)}/audit`),
      ]);
      state.status = status;
      state.events = events.events || [];
      state.reviews = reviews.reviews || [];
      state.artifacts = artifacts.artifacts || [];
      state.context = context;
      state.provenance = provenance;
      state.audit = audit.events || [];
      if (
        state.selectedArtifactId &&
        !state.artifacts.some((artifact) => artifact.artifact_id === state.selectedArtifactId)
      ) {
        state.selectedArtifactId = "";
      }
      state.activeRunId = latestRunId(state.events) || storedRunId(studyId);
      if (state.activeRunId) {
        localStorage.setItem(runStorageKey(studyId), state.activeRunId);
      }
      setApiStatus("ok", "API 已连接");
    } catch (error) {
      state.status = null;
      state.events = [];
      state.reviews = [];
      state.artifacts = [];
      state.context = null;
      state.provenance = null;
      state.audit = [];
      state.selectedArtifactId = "";
      setApiStatus("danger", "API 错误");
      setText("run-message", `Study 读取失败：${error.message}`);
    } finally {
      state.loading = false;
      renderAll();
    }
  }

  function renderAll() {
    renderStudies([]);
    renderDashboard();
    renderRunPanel();
    renderEvents();
    renderReviews();
    renderArtifacts();
    renderContextProvenance();
    renderAudit();
  }

  function renderStudies(partialErrors) {
    const list = $("study-list");
    const selected = state.selectedStudyId;
    if (!state.studies.length) {
      list.innerHTML = `<div class="empty-state">未发现 Study。请先在 clinical-studies 下创建或复制 Study。</div>`;
    } else {
      list.innerHTML = state.studies
        .map((study) => {
          const current = study.study_id === selected;
          return `
            <button class="study-card" type="button" data-study-id="${escapeAttr(study.study_id)}"
              aria-current="${current ? "true" : "false"}">
              <strong>${escapeHtml(study.study_id)}</strong>
              <span>${escapeHtml(study.title || "未命名 protocol")}</span>
              <span class="mono">${escapeHtml(stageLabel(study.current_stage))} · ${escapeHtml(study.run_state)}</span>
              <span>${study.pending_review_count || 0} pending review</span>
            </button>
          `;
        })
        .join("");
    }
    if (partialErrors.length) {
      setText("study-list-message", `部分 Study 无法读取：${partialErrors.length}`);
    } else if (!state.studies.length) {
      setText("study-list-message", "");
    } else {
      setText("study-list-message", `${state.studies.length} 个 Study 可用`);
    }
    setText("selected-study-label", selected || "未选择 Study");
  }

  function renderDashboard() {
    const hasStudy = Boolean(state.selectedStudyId && state.status);
    $("dashboard-empty").hidden = hasStudy || state.loading;
    $("dashboard-content").hidden = !hasStudy;
    if (state.loading) {
      $("dashboard-empty").hidden = false;
      setText("dashboard-empty", "正在加载 Study 状态…");
      return;
    }
    if (!state.selectedStudyId) {
      $("dashboard-empty").hidden = false;
      setText("dashboard-empty", "请选择左侧 Study。选择后会从 Application API 读取状态，不在浏览器推断阶段。");
      return;
    }
    if (!state.status) {
      $("dashboard-empty").hidden = false;
      setText("dashboard-empty", "当前 Study 状态不可用。");
      return;
    }

    const currentStage = currentStageFromPayload(state.status);
    setText("current-stage", stageLabel(currentStage));
    setText("run-state", runStateLabel(state.status.run_state));
    setText("pending-review-count", String(state.status.pending_review_count));
    setText(
      "incomplete-reasons",
      state.status.incomplete_reasons && state.status.incomplete_reasons.length
        ? `${state.status.incomplete_reasons.length} issue`
        : "完整"
    );
    setText(
      "knowledge-lock",
      `Knowledge: ${state.status.knowledge_lock ? state.status.knowledge_lock.status : "n/a"}`
    );

    $("stage-timeline").innerHTML = (state.status.stages || [])
      .map((stage) => `
        <li class="stage-item stage-${escapeAttr(stage.status)}">
          <small>#${stage.ordinal}</small>
          <strong>${escapeHtml(stageLabel(stage.stage_id))}</strong>
          <span class="status-pill ${statusClass(stage.status)}">${escapeHtml(stage.status)}</span>
          <small>${stage.canonical_artifact_count} canonical · ${stage.draft_artifact_count} draft</small>
        </li>
      `)
      .join("");
  }

  function renderRunPanel() {
    const selected = Boolean(state.selectedStudyId && state.status);
    const stageSelect = $("target-stage");
    stageSelect.innerHTML = selected
      ? (state.status.stage_order || [])
          .map((stage) => `<option value="${escapeAttr(stage)}">${escapeHtml(stageLabel(stage))}</option>`)
          .join("")
      : `<option value="">请选择 Study</option>`;

    const runState = state.status ? state.status.run_state : "idle";
    const hasPendingReview = state.status ? state.status.pending_review_count > 0 : false;
    const activeBlocks = ["queued", "running", "blocked_error"].includes(runState);
    $("start-run").disabled = !selected || hasPendingReview || activeBlocks;
    $("resume-run").disabled = !selected || !state.activeRunId || hasPendingReview;
    setText("active-run-id", state.activeRunId ? `run: ${state.activeRunId}` : "run: n/a");

    if (!selected) {
      setText("run-help", "选择 Study 后才能提交 run request。");
    } else if (hasPendingReview) {
      setText("run-help", "当前有待审核 packet；请先在 Review Inbox 提交 DecisionReceipt。");
    } else if (activeBlocks) {
      setText("run-help", `当前运行状态为 ${runState}；前端不直接启动第二个 run。`);
    } else {
      setText("run-help", "run/resume 只写 durable request 和事件；Runtime 执行仍由后续受控流程消费。");
    }
  }

  function renderEvents() {
    const list = $("event-list");
    if (!state.selectedStudyId) {
      list.innerHTML = `<li class="event-item">选择 Study 后显示事件。</li>`;
      return;
    }
    if (!state.events.length) {
      list.innerHTML = `<li class="event-item">暂无事件。</li>`;
      return;
    }
    list.innerHTML = state.events
      .slice(-8)
      .reverse()
      .map((event) => `
        <li class="event-item">
          <strong>${escapeHtml(event.event_type)}</strong><br />
          <span>${escapeHtml(event.event_id)}</span>
        </li>
      `)
      .join("");
  }

  function renderReviews() {
    const reviews = state.reviews || [];
    setText("review-count", `${reviews.length} review${reviews.length === 1 ? "" : "s"}`);
    if (!state.selectedStudyId) {
      $("review-list").innerHTML = `<div class="empty-state">选择 Study 后显示 ReviewPacket。</div>`;
      return;
    }
    if (!reviews.length) {
      $("review-list").innerHTML = `<div class="empty-state">当前没有 ReviewPacket。</div>`;
      return;
    }
    $("review-list").innerHTML = reviews.map(renderReviewCard).join("");
  }

  function renderArtifacts() {
    const artifacts = state.artifacts || [];
    setText("artifact-count", `${artifacts.length} artifact${artifacts.length === 1 ? "" : "s"}`);
    if (!state.selectedStudyId) {
      $("artifact-list").innerHTML = `<div class="empty-state">选择 Study 后显示 artifact。</div>`;
      $("artifact-detail").innerHTML = `<div class="empty-state">选择 artifact 后显示注册引用、hash 和预览。</div>`;
      return;
    }
    if (!artifacts.length) {
      $("artifact-list").innerHTML = `<div class="empty-state">当前没有已登记 artifact。</div>`;
      $("artifact-detail").innerHTML = `<div class="empty-state">尚无 artifact 可预览。</div>`;
      return;
    }
    $("artifact-list").innerHTML = artifacts
      .map((artifact) => `
        <button
          class="artifact-card"
          type="button"
          data-artifact-id="${escapeAttr(artifact.artifact_id)}"
          aria-current="${artifact.artifact_id === state.selectedArtifactId ? "true" : "false"}"
        >
          <strong>${escapeHtml(artifact.display_name || artifact.artifact_id)}</strong>
          <span>
            <span class="status-pill ${statusClass(artifact.artifact_state)}">${escapeHtml(artifact.artifact_state)}</span>
            <span class="status-pill status-muted">${escapeHtml(artifact.artifact_type)}</span>
          </span>
          <span class="mono">${escapeHtml(shortHash(artifact.sha256))}</span>
        </button>
      `)
      .join("");
    const selected = artifacts.find((artifact) => artifact.artifact_id === state.selectedArtifactId);
    if (!selected && !state.selectedArtifactId) {
      $("artifact-detail").innerHTML = `<div class="empty-state">选择 artifact 后显示注册引用、hash 和预览。</div>`;
    }
  }

  async function selectArtifact(artifactId) {
    if (!state.selectedStudyId) {
      return;
    }
    state.selectedArtifactId = artifactId;
    renderArtifacts();
    setText("artifact-message", "正在读取 artifact 详情…");
    try {
      const detail = await apiGet(
        `/api/v1/studies/${encodeURIComponent(state.selectedStudyId)}/artifacts/${encodeURIComponent(artifactId)}`
      );
      renderArtifactDetail(detail);
      setText("artifact-message", "");
    } catch (error) {
      setText("artifact-message", `Artifact 读取失败：${error.message}`);
    }
  }

  function renderArtifactDetail(detail) {
    const artifact = detail.artifact;
    const ref = detail.registered_ref;
    $("artifact-detail").innerHTML = `
      <h3>${escapeHtml(artifact.display_name || artifact.artifact_id)}</h3>
      <dl class="metadata-list">
        <dt>Artifact ID</dt>
        <dd class="mono">${escapeHtml(artifact.artifact_id)}</dd>
        <dt>State / Type</dt>
        <dd>${escapeHtml(artifact.artifact_state)} / ${escapeHtml(artifact.artifact_type)}</dd>
        <dt>Registered ref</dt>
        <dd class="mono">${escapeHtml(ref.container_id)}:${escapeHtml(ref.relative_path)}</dd>
        <dt>SHA-256</dt>
        <dd class="mono">${escapeHtml(ref.sha256)}</dd>
        <dt>Provenance ID</dt>
        <dd class="mono">${escapeHtml(artifact.provenance_id || "n/a")}</dd>
      </dl>
      <div class="preview-box">${renderPreview(detail.preview)}</div>
    `;
  }

  function renderPreview(preview) {
    if (!preview) {
      return `<div class="empty-state">该 artifact 暂不支持浏览器预览。</div>`;
    }
    if (preview.kind === "csv") {
      const rows = preview.rows || [];
      if (!rows.length) {
        return `<div class="empty-state">CSV 无数据行。row_count=${preview.row_count || 0}</div>`;
      }
      const columns = Object.keys(rows[0]);
      return `
        <p class="help-text">CSV preview: showing ${rows.length} of ${preview.row_count} rows</p>
        <div class="table-wrap">
          <table>
            <thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead>
            <tbody>
              ${rows.map((row) => `
                <tr>${columns.map((column) => `<td>${escapeHtml(row[column])}</td>`).join("")}</tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    }
    if (preview.kind === "text") {
      return `<pre>${escapeHtml(preview.value || "")}</pre>`;
    }
    return `<pre>${escapeHtml(JSON.stringify(preview.value, null, 2))}</pre>`;
  }

  function renderContextProvenance() {
    if (!state.selectedStudyId) {
      $("context-content").innerHTML = `<div class="empty-state">选择 Study 后显示 context/provenance。</div>`;
      setText("context-lock", "lock: n/a");
      return;
    }
    const context = state.context || {};
    const provenance = state.provenance || {};
    const lock = context.bundle_lock || {};
    setText("context-lock", `lock: ${lock.version || "n/a"}`);
    const sections = [
      ["Source refs", context.source_refs || []],
      ["Rule refs", context.rule_refs || []],
      ["Study decisions", context.study_decision_refs || []],
      ["Traceability refs", provenance.traceability_refs || []],
    ];
    $("context-content").innerHTML = `
      <div class="reference-card">
        <h3>Bundle lock</h3>
        <p class="mono">${escapeHtml(lock.version || "n/a")} · ${escapeHtml(shortHash(lock.sha256))}</p>
      </div>
      ${sections.map(([title, refs]) => renderReferenceSection(title, refs)).join("")}
      <div class="reference-card">
        <h3>Explicit gaps</h3>
        ${(context.gaps || []).length
          ? `<ul>${context.gaps.map((gap) => `<li class="mono">${escapeHtml(gap)}</li>`).join("")}</ul>`
          : `<p class="help-text">无显式 gap。</p>`}
      </div>
    `;
  }

  function renderReferenceSection(title, refs) {
    return `
      <div class="reference-card">
        <h3>${escapeHtml(title)}</h3>
        ${refs.length
          ? `<ul>${refs.map((ref) => `
              <li>
                <span class="status-pill status-muted">${escapeHtml(ref.ref_type)}</span>
                <span class="mono">${escapeHtml(ref.ref_id)}</span>
                <span class="mono">${escapeHtml(shortHash(ref.sha256))}</span>
              </li>
            `).join("")}</ul>`
          : `<p class="help-text">无引用。</p>`}
      </div>
    `;
  }

  function renderAudit() {
    const filter = $("audit-filter").value || getAuditFilterFromUrl();
    const eventTypes = Array.from(new Set((state.audit || []).map((event) => event.event_type))).sort();
    $("audit-filter").innerHTML = [
      `<option value="">全部事件</option>`,
      ...eventTypes.map((type) => `<option value="${escapeAttr(type)}">${escapeHtml(type)}</option>`),
    ].join("");
    $("audit-filter").value = eventTypes.includes(filter) ? filter : "";
    const filtered = $("audit-filter").value
      ? (state.audit || []).filter((event) => event.event_type === $("audit-filter").value)
      : (state.audit || []);
    if (!state.selectedStudyId) {
      $("audit-list").innerHTML = `<li class="empty-state">选择 Study 后显示 audit timeline。</li>`;
      setText("audit-message", "");
      return;
    }
    setText("audit-message", `${filtered.length} / ${(state.audit || []).length} events`);
    if (!filtered.length) {
      $("audit-list").innerHTML = `<li class="empty-state">没有匹配事件。</li>`;
      return;
    }
    $("audit-list").innerHTML = filtered
      .slice()
      .reverse()
      .map((event) => `
        <li class="audit-item">
          <div>
            <strong>${escapeHtml(event.event_type)}</strong>
            <span class="mono">${escapeHtml(event.event_id)}</span>
          </div>
          <p>${escapeHtml(event.occurred_at || "")} · ${escapeHtml(event.stage_id || "n/a")}</p>
          ${renderRelatedRefs(event.related_refs || [])}
        </li>
      `)
      .join("");
  }

  function renderRelatedRefs(refs) {
    if (!refs.length) {
      return `<p class="help-text">No related refs.</p>`;
    }
    return `
      <ul class="related-refs">
        ${refs.map((ref) => `
          <li>
            <span>${escapeHtml(ref.ref_type)}</span>
            <span class="mono">${escapeHtml(ref.ref_id)}</span>
            <span class="mono">${escapeHtml(shortHash(ref.sha256))}</span>
          </li>
        `).join("")}
      </ul>
    `;
  }

  function renderReviewCard(review) {
    const findings = review.findings || [];
    const requiredFindings = findings.filter((finding) => !finding.auto_approved);
    const canSubmit = review.decision_state === "pending" && requiredFindings.length > 0;
    return `
      <article class="review-card" data-review-id="${escapeAttr(review.review_id)}">
        <div class="review-card-header">
          <div>
            <h3>${escapeHtml(review.review_id)}</h3>
            <p class="help-text">${escapeHtml(review.agent_summary || "无摘要")}</p>
            <p class="mono">packet: ${escapeHtml(shortHash(review.packet_sha256))}</p>
          </div>
          <span class="status-pill ${statusClass(review.decision_state)}">${escapeHtml(review.decision_state)}</span>
        </div>
        <div class="review-decision-form">
          <label>
            Reviewer
            <input id="${domId(review.review_id, "reviewer")}" placeholder="请输入审核人姓名" ${canSubmit ? "" : "disabled"} />
          </label>
          ${findings.map((finding) => renderFinding(review, finding, canSubmit)).join("")}
          <button
            class="button button-primary"
            type="button"
            data-submit-review="${escapeAttr(review.review_id)}"
            ${canSubmit ? "" : "disabled"}
          >
            提交 DecisionReceipt
          </button>
        </div>
      </article>
    `;
  }

  function renderFinding(review, finding, canSubmit) {
    const findingDomId = domId(review.review_id, finding.finding_id);
    const disabled = canSubmit && !finding.auto_approved ? "" : "disabled";
    const autoNote = finding.auto_approved ? `<span class="status-pill status-ok">auto-approved</span>` : "";
    return `
      <section class="finding-card" aria-label="${escapeAttr(finding.finding_id)}">
        <div>
          <div class="finding-meta">
            <span class="status-pill status-muted">${escapeHtml(finding.finding_id)}</span>
            <span class="status-pill ${statusClass(finding.severity)}">${escapeHtml(finding.severity)}</span>
            ${autoNote}
          </div>
          <h4>${escapeHtml(finding.title)}</h4>
          <p>${escapeHtml(finding.rationale)}</p>
        </div>
        <dl>
          <dt>Location</dt>
          <dd class="mono">${escapeHtml(finding.location)}</dd>
          <dt>Current</dt>
          <dd>${escapeHtml(finding.current_value)}</dd>
          <dt>Proposed</dt>
          <dd>${escapeHtml(finding.proposed_value)}</dd>
        </dl>
        <div class="decision-options" role="radiogroup" aria-label="Decision for ${escapeAttr(finding.finding_id)}">
          ${Object.entries(decisionLabels).map(([value, label]) => `
            <label>
              <input type="radio" name="${findingDomId}-decision" value="${value}" ${disabled} />
              ${label}
            </label>
          `).join("")}
        </div>
        <label>
          Modified value
          <input id="${findingDomId}-modified" ${disabled} placeholder="decision=modified 时必填" />
        </label>
        <label>
          Rejection reason
          <select id="${findingDomId}-reason" ${disabled}>
            <option value="insufficient_evidence">insufficient_evidence</option>
            <option value="incorrect_variable_mapping">incorrect_variable_mapping</option>
            <option value="incorrect_derivation">incorrect_derivation</option>
            <option value="wrong_ct_value">wrong_ct_value</option>
            <option value="other">other</option>
          </select>
        </label>
        <label>
          Comment
          <input id="${findingDomId}-comment" ${disabled} maxlength="500" placeholder="可选说明" />
        </label>
      </section>
    `;
  }

  async function submitRunRequest(event) {
    event.preventDefault();
    if (!state.selectedStudyId || !state.status) {
      return;
    }
    setText("run-message", "正在提交 run request…");
    const body = {
      intent: $("run-intent").value.trim(),
      target_stage: $("target-stage").value,
      dataset: $("run-dataset").value.trim() || null,
      dry_run: false,
    };
    try {
      const response = await apiPost(
        `/api/v1/studies/${encodeURIComponent(state.selectedStudyId)}/runs`,
        body
      );
      state.activeRunId = response.run_id;
      localStorage.setItem(runStorageKey(state.selectedStudyId), response.run_id);
      setText("run-message", `Run request accepted: ${response.run_id}`);
      await loadStudy(state.selectedStudyId);
      await loadStudies();
    } catch (error) {
      setText("run-message", `提交失败：${error.message}`);
    }
  }

  async function submitResumeRequest() {
    if (!state.selectedStudyId || !state.activeRunId) {
      return;
    }
    setText("run-message", "正在提交 resume request…");
    try {
      const cursor = state.events.length ? state.events[state.events.length - 1].event_id : undefined;
      const response = await apiPost(
        `/api/v1/studies/${encodeURIComponent(state.selectedStudyId)}/runs/${encodeURIComponent(state.activeRunId)}/resume`,
        { reason: "operator_resume", last_seen_event_cursor: cursor }
      );
      setText("run-message", `Resume accepted: ${response.run_state}`);
      await loadStudy(state.selectedStudyId);
    } catch (error) {
      setText("run-message", `Resume 失败：${error.message}`);
    }
  }

  async function submitReviewDecision(reviewId) {
    const review = state.reviews.find((item) => item.review_id === reviewId);
    if (!review) {
      return;
    }
    const reviewer = $(domId(reviewId, "reviewer")).value.trim();
    if (reviewer.length < 2) {
      setText("review-message", "Reviewer 至少需要 2 个字符。");
      return;
    }
    const decisions = [];
    for (const finding of (review.findings || []).filter((item) => !item.auto_approved)) {
      const id = domId(reviewId, finding.finding_id);
      const selected = document.querySelector(`input[name="${id}-decision"]:checked`);
      if (!selected) {
        setText("review-message", `请先选择 ${finding.finding_id} 的 decision。`);
        return;
      }
      const decision = {
        finding_id: finding.finding_id,
        decision: selected.value,
      };
      const modifiedValue = $(id + "-modified").value.trim();
      const comment = $(id + "-comment").value.trim();
      if (selected.value === "modified") {
        if (!modifiedValue) {
          setText("review-message", `${finding.finding_id} 修改后批准需要 modified_value。`);
          return;
        }
        decision.modified_value = modifiedValue;
      }
      if (selected.value === "rejected") {
        decision.rejection_reason = $(id + "-reason").value;
      }
      if (comment) {
        decision.comment = comment;
      }
      decisions.push(decision);
    }
    setText("review-message", "正在写入 DecisionReceipt…");
    try {
      const response = await apiPost(
        `/api/v1/studies/${encodeURIComponent(state.selectedStudyId)}/reviews/${encodeURIComponent(reviewId)}/decisions`,
        {
          review_id: reviewId,
          packet_sha256: review.packet_sha256,
          reviewer,
          decisions,
        }
      );
      setText("review-message", `DecisionReceipt 已写入：${response.decision_receipt_id}`);
      await loadStudy(state.selectedStudyId);
      await loadStudies();
    } catch (error) {
      setText("review-message", `审核提交失败：${error.message}`);
    }
  }

  async function apiGet(path) {
    const response = await fetch(path, { headers: { Accept: "application/json" } });
    return parseResponse(response);
  }

  async function apiPost(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": newIdempotencyKey(),
      },
      body: JSON.stringify(body),
    });
    return parseResponse(response);
  }

  async function parseResponse(response) {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || payload.code || `HTTP ${response.status}`);
    }
    return payload;
  }

  function latestRunId(events) {
    for (const event of [...events].reverse()) {
      const refs = event.related_refs || [];
      const runRef = refs.find((ref) => ref.ref_type === "run");
      if (runRef) {
        return runRef.ref_id;
      }
    }
    return "";
  }

  function currentStageFromPayload(status) {
    const active = (status.stages || []).find((stage) =>
      ["blocked_review", "blocked_error", "ready", "running"].includes(stage.status)
    );
    if (active) {
      return active.stage_id;
    }
    const completed = (status.stages || []).filter((stage) => stage.status === "completed");
    return completed.length ? completed[completed.length - 1].stage_id : status.stage_order[0];
  }

  function stageLabel(stage) {
    return stageLabels[stage] || stage || "-";
  }

  function runStateLabel(runState) {
    return runStateLabels[runState] || runState || "-";
  }

  function statusClass(status) {
    if (["completed", "confirmed", "approved", "decided"].includes(status)) {
      return "status-ok";
    }
    if (["blocked_review", "warning", "pending", "queued", "running"].includes(status)) {
      return "status-warn";
    }
    if (["blocked_error", "failed", "critical", "rejected", "invalid"].includes(status)) {
      return "status-danger";
    }
    return "status-muted";
  }

  function setApiStatus(kind, text) {
    const node = $("api-status");
    node.textContent = text;
    node.className = `status-pill status-${kind === "loading" ? "warn" : kind}`;
  }

  function setText(id, text) {
    $(id).textContent = text;
  }

  function runStorageKey(studyId) {
    return `clinical.console.run.${studyId}`;
  }

  function storedRunId(studyId) {
    return localStorage.getItem(runStorageKey(studyId)) || "";
  }

  function getAuditFilterFromUrl() {
    return new URLSearchParams(window.location.search).get("audit") || "";
  }

  function setAuditFilterUrl(value) {
    const url = new URL(window.location.href);
    if (value) {
      url.searchParams.set("audit", value);
    } else {
      url.searchParams.delete("audit");
    }
    window.history.replaceState(null, "", url.toString());
  }

  function newIdempotencyKey() {
    const random = Math.random().toString(36).slice(2, 12);
    return `ui-${Date.now()}-${random}`;
  }

  function domId() {
    return Array.from(arguments)
      .join("-")
      .replace(/[^A-Za-z0-9_-]+/g, "-");
  }

  function shortHash(value) {
    return value ? `${value.slice(0, 10)}…` : "n/a";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replaceAll("`", "&#096;");
  }
})();

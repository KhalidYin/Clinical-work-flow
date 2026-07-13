import {
  REJECTION_REASON_LABELS,
  REJECTION_REASONS,
  ReviewFinding,
  ReviewPacket,
} from "./schema";

export function renderReviewPanelHtml(packet: ReviewPacket, nonce: string): string {
  const packetJson = JSON.stringify(packet).replace(/</g, "\\u003c");
  const actionableCount = packet.findings.filter((finding) => !finding.auto_approved).length;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Clinical Review Panel</title>
  <style>${panelCss()}</style>
</head>
<body>
  <header class="topbar">
    <div>
      <p class="eyebrow">${escapeHtml(packet.review_type)}</p>
      <h1>${escapeHtml(packet.review_id)}</h1>
    </div>
    <button type="button" class="icon-button" id="refresh" aria-label="Refresh queue" title="Refresh queue">Refresh</button>
  </header>

  <section class="summary">
    <dl>
      <div><dt>Urgency</dt><dd>${escapeHtml(packet.urgency)}</dd></div>
      <div><dt>Findings</dt><dd>${packet.findings.length}</dd></div>
      <div><dt>Actionable</dt><dd>${actionableCount}</dd></div>
      <div><dt>Auto</dt><dd>${packet.auto_approved_count}</dd></div>
    </dl>
    <p>${escapeHtml(packet.agent_summary)}</p>
    <div class="sources">${packet.source_documents.map((source) => `<span>${escapeHtml(source)}</span>`).join("")}</div>
  </section>

  <main>
    <div id="errors" class="errors" hidden></div>
    ${packet.findings.map(renderFinding).join("")}
  </main>

  <footer class="submitbar">
    <label class="reviewer">
      <span>Reviewer</span>
      <input id="reviewer" type="text" autocomplete="name" placeholder="Name or initials">
    </label>
    <label class="notes">
      <span>General notes</span>
      <textarea id="general-notes" rows="2" placeholder="Optional"></textarea>
    </label>
    <button type="button" class="primary" id="submit">Submit decisions</button>
  </footer>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const reviewPacket = ${packetJson};

    function updatePanels(container) {
      const decision = container.querySelector('input[type="radio"]:checked')?.value;
      container.querySelector('[data-panel="reject"]').hidden = decision !== 'rejected';
      container.querySelector('[data-panel="modify"]').hidden = decision !== 'modified';
    }

    function showErrors(errors) {
      const target = document.getElementById('errors');
      if (!errors.length) {
        target.hidden = true;
        target.innerHTML = '';
        return;
      }
      target.hidden = false;
      target.innerHTML = '<strong>Resolve before submitting</strong><ul>' +
        errors.map((error) => '<li>' + escapeText(error) + '</li>').join('') +
        '</ul>';
      target.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }

    function escapeText(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      })[char]);
    }

    function collectReceipt() {
      const receipt = {
        review_id: reviewPacket.review_id,
        reviewer: document.getElementById('reviewer').value.trim(),
        timestamp: new Date().toISOString(),
        decisions: [],
      };
      const generalNotes = document.getElementById('general-notes').value.trim();
      if (generalNotes) {
        receipt.general_notes = generalNotes;
      }

      for (const finding of document.querySelectorAll('.finding')) {
        if (finding.dataset.autoApproved === 'true') {
          continue;
        }
        const selected = finding.querySelector('input[type="radio"]:checked');
        const decision = {
          finding_id: finding.dataset.findingId,
          decision: selected ? selected.value : ''
        };
        if (decision.decision === 'rejected') {
          const reason = finding.querySelector('[data-field="rejection_reason"]').value;
          const correction = finding.querySelector('[data-field="human_correction"]').value.trim();
          const reference = finding.querySelector('[data-field="reference"]').value.trim();
          const comment = finding.querySelector('[data-field="reject_comment"]').value.trim();
          if (reason) decision.rejection_reason = reason;
          if (correction) decision.human_correction = correction;
          if (reference) decision.reference = reference;
          if (comment) decision.comment = comment;
        }
        if (decision.decision === 'modified') {
          const modifiedValue = finding.querySelector('[data-field="modified_value"]').value.trim();
          const comment = finding.querySelector('[data-field="modify_comment"]').value.trim();
          if (modifiedValue) decision.modified_value = modifiedValue;
          if (comment) decision.comment = comment;
        }
        receipt.decisions.push(decision);
      }

      return receipt;
    }

    function validateReceipt(receipt) {
      const errors = [];
      if (!receipt.reviewer || receipt.reviewer.length < 2) {
        errors.push('Reviewer is required.');
      }
      for (const decision of receipt.decisions) {
        if (!decision.decision) {
          errors.push('Finding ' + decision.finding_id + ': decision is required.');
        }
        if (decision.decision === 'modified' && !decision.modified_value) {
          errors.push('Finding ' + decision.finding_id + ': modified value is required.');
        }
        if (decision.decision === 'rejected') {
          if (!decision.rejection_reason) {
            errors.push('Finding ' + decision.finding_id + ': rejection reason is required.');
          }
          if (
            decision.rejection_reason &&
            decision.rejection_reason !== 'insufficient_evidence' &&
            (!decision.human_correction || decision.human_correction.length < 10)
          ) {
            errors.push('Finding ' + decision.finding_id + ': correction must be at least 10 characters.');
          }
        }
      }
      return errors;
    }

    document.querySelectorAll('.finding').forEach((finding) => {
      finding.querySelectorAll('input[type="radio"]').forEach((radio) => {
        radio.addEventListener('change', () => updatePanels(finding));
      });
      updatePanels(finding);
    });

    document.getElementById('submit').addEventListener('click', () => {
      const receipt = collectReceipt();
      const errors = validateReceipt(receipt);
      showErrors(errors);
      if (!errors.length) {
        vscode.postMessage({ type: 'submitDecision', receipt });
      }
    });

    document.getElementById('refresh').addEventListener('click', () => {
      vscode.postMessage({ type: 'refresh' });
    });

    window.addEventListener('message', (event) => {
      if (event.data?.type === 'validationErrors') {
        showErrors(event.data.errors || []);
      }
    });
  </script>
</body>
</html>`;
}

export function renderStatusHtml(title: string, body: string, nonce: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
  <style>${panelCss()}</style>
</head>
<body>
  <section class="empty">
    <p class="eyebrow">Review Queue</p>
    <h1>${escapeHtml(title)}</h1>
    <p>${escapeHtml(body)}</p>
    <button type="button" class="primary" id="refresh">Refresh</button>
  </section>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    document.getElementById('refresh').addEventListener('click', () => {
      vscode.postMessage({ type: 'refresh' });
    });
  </script>
</body>
</html>`;
}

function renderFinding(finding: ReviewFinding): string {
  const disabled = finding.auto_approved ? " disabled" : "";
  const autoBadge = finding.auto_approved ? '<span class="badge ok">Auto approved</span>' : "";

  return `<article class="finding" data-finding-id="${escapeHtml(finding.id)}" data-auto-approved="${finding.auto_approved}">
    <header>
      <div>
        <p class="eyebrow">${escapeHtml(finding.category)} / ${escapeHtml(finding.severity)}</p>
        <h2>${escapeHtml(finding.title)}</h2>
      </div>
      ${autoBadge}
    </header>
    <dl class="finding-meta">
      <div><dt>Location</dt><dd>${escapeHtml(finding.location)}</dd></div>
      <div><dt>Evidence</dt><dd>${finding.evidence_refs.map((ref) => `<span>${escapeHtml(ref)}</span>`).join("")}</dd></div>
    </dl>
    <div class="comparison">
      <section>
        <h3>Current</h3>
        <pre>${escapeHtml(finding.current_value)}</pre>
      </section>
      <section>
        <h3>Proposed</h3>
        <pre>${escapeHtml(finding.proposed_value)}</pre>
      </section>
    </div>
    <p class="rationale">${escapeHtml(finding.rationale)}</p>
    <fieldset class="decision-group"${disabled}>
      <legend>Decision</legend>
      <label><input type="radio" name="decision-${escapeAttribute(finding.id)}" value="approved" checked> Approve</label>
      <label><input type="radio" name="decision-${escapeAttribute(finding.id)}" value="rejected"> Reject</label>
      <label><input type="radio" name="decision-${escapeAttribute(finding.id)}" value="modified"> Modify</label>
    </fieldset>
    <section class="conditional" data-panel="reject">
      <label>
        <span>Rejection reason</span>
        <select data-field="rejection_reason"${disabled}>
          <option value="">Select reason</option>
          ${REJECTION_REASONS.map((reason) => `<option value="${reason}">${escapeHtml(REJECTION_REASON_LABELS[reason])}</option>`).join("")}
        </select>
      </label>
      <label>
        <span>Human correction</span>
        <textarea data-field="human_correction" rows="4" placeholder="Required unless reason is insufficient evidence"${disabled}></textarea>
      </label>
      <label>
        <span>Reference</span>
        <input data-field="reference" type="text" placeholder="Protocol/SAP/CDISC reference"${disabled}>
      </label>
      <label>
        <span>Comment</span>
        <textarea data-field="reject_comment" rows="2" placeholder="Optional"${disabled}></textarea>
      </label>
    </section>
    <section class="conditional" data-panel="modify">
      <label>
        <span>Modified value</span>
        <textarea data-field="modified_value" rows="4" placeholder="Replacement value"${disabled}></textarea>
      </label>
      <label>
        <span>Comment</span>
        <textarea data-field="modify_comment" rows="2" placeholder="Optional"${disabled}></textarea>
      </label>
    </section>
  </article>`;
}

function panelCss(): string {
  return `
    :root {
      color-scheme: light dark;
      --border-soft: color-mix(in srgb, var(--vscode-foreground) 18%, transparent);
      --panel: color-mix(in srgb, var(--vscode-editor-background) 94%, var(--vscode-foreground) 6%);
      --muted: var(--vscode-descriptionForeground);
      --accent: var(--vscode-focusBorder);
      --danger: var(--vscode-inputValidation-errorBorder);
      --ok: var(--vscode-testing-iconPassed);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 12px;
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      font: var(--vscode-font-size) var(--vscode-font-family);
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: 17px; line-height: 1.25; font-weight: 650; }
    h2 { font-size: 14px; line-height: 1.35; font-weight: 650; }
    h3 { color: var(--muted); font-size: 11px; font-weight: 650; text-transform: uppercase; }
    .topbar, .finding > header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
    }
    .topbar { margin-bottom: 12px; }
    .eyebrow {
      color: var(--muted);
      font-size: 10px;
      letter-spacing: 0;
      text-transform: uppercase;
      margin-bottom: 4px;
    }
    .summary, .finding, .empty {
      border: 1px solid var(--border-soft);
      border-radius: 8px;
      background: var(--panel);
    }
    .summary { padding: 10px; margin-bottom: 12px; }
    .summary dl, .finding-meta {
      display: grid;
      gap: 8px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin: 0 0 10px;
    }
    dt { color: var(--muted); font-size: 10px; text-transform: uppercase; }
    dd { margin: 2px 0 0; overflow-wrap: anywhere; }
    .sources, .finding-meta dd {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }
    .sources span, .finding-meta span, .badge {
      border: 1px solid var(--border-soft);
      border-radius: 999px;
      padding: 2px 6px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
    }
    .badge.ok { color: var(--ok); }
    .finding { padding: 10px; margin-bottom: 12px; }
    .finding-meta { grid-template-columns: 1fr; margin-top: 10px; }
    .comparison {
      display: grid;
      gap: 8px;
      margin: 10px 0;
    }
    pre {
      margin: 4px 0 0;
      padding: 8px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      border: 1px solid var(--border-soft);
      border-radius: 6px;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      font-family: var(--vscode-editor-font-family);
      font-size: 12px;
    }
    .rationale { color: var(--muted); line-height: 1.45; margin-bottom: 10px; }
    .decision-group {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 4px;
      border: 0;
      padding: 0;
      margin: 0;
    }
    .decision-group legend {
      grid-column: 1 / -1;
      color: var(--muted);
      font-size: 10px;
      text-transform: uppercase;
      margin-bottom: 4px;
    }
    .decision-group label {
      min-height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      border: 1px solid var(--border-soft);
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
    }
    .decision-group input { margin: 0; }
    .conditional {
      display: grid;
      gap: 8px;
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid var(--border-soft);
    }
    .conditional[hidden] { display: none; }
    label span { display: block; color: var(--muted); font-size: 11px; margin-bottom: 4px; }
    input, textarea, select {
      width: 100%;
      min-height: 30px;
      padding: 6px 8px;
      border: 1px solid var(--vscode-input-border, var(--border-soft));
      border-radius: 6px;
      color: var(--vscode-input-foreground);
      background: var(--vscode-input-background);
      font: inherit;
    }
    textarea { resize: vertical; }
    input:focus, textarea:focus, select:focus, button:focus {
      outline: 1px solid var(--accent);
      outline-offset: 1px;
    }
    button {
      min-height: 32px;
      border: 1px solid var(--border-soft);
      border-radius: 6px;
      color: var(--vscode-button-secondaryForeground);
      background: var(--vscode-button-secondaryBackground);
      cursor: pointer;
      font: inherit;
    }
    button:hover { background: var(--vscode-button-secondaryHoverBackground); }
    .primary {
      color: var(--vscode-button-foreground);
      background: var(--vscode-button-background);
      border-color: var(--vscode-button-background);
    }
    .primary:hover { background: var(--vscode-button-hoverBackground); }
    .submitbar {
      position: sticky;
      bottom: 0;
      display: grid;
      gap: 8px;
      margin: 12px -12px -12px;
      padding: 10px 12px 12px;
      border-top: 1px solid var(--border-soft);
      background: var(--vscode-editor-background);
    }
    .errors {
      border: 1px solid var(--danger);
      border-radius: 8px;
      padding: 8px 10px;
      margin-bottom: 12px;
      color: var(--vscode-inputValidation-errorForeground);
      background: var(--vscode-inputValidation-errorBackground);
    }
    .errors ul { margin: 6px 0 0; padding-left: 18px; }
    .empty { padding: 14px; }
    .empty p { color: var(--muted); line-height: 1.45; margin: 8px 0 12px; }
    @media (min-width: 720px) {
      body { padding: 16px; }
      .comparison { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .summary dl { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    }
  `;
}

function escapeHtml(value: string | number | boolean): string {
  return String(value).replace(/[&<>"']/g, (char) => {
    const replacements: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return replacements[char];
  });
}

function escapeAttribute(value: string): string {
  return escapeHtml(value).replace(/\s+/g, "_");
}

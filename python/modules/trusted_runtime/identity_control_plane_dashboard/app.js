"use strict";

const state = { agentId: "" };
const elements = {
  agentSelect: document.querySelector("#agent-select"),
  refreshButton: document.querySelector("#refresh-button"),
  loadStatus: document.querySelector("#load-status"),
  integrityBanner: document.querySelector("#integrity-banner"),
  integrityTitle: document.querySelector("#integrity-title"),
  integrityMessage: document.querySelector("#integrity-message"),
  controlPlaneCards: document.querySelector("#control-plane-cards"),
  publicationDigest: document.querySelector("#publication-digest"),
  triggerRefs: document.querySelector("#trigger-refs"),
  controlPlaneFindings: document.querySelector("#control-plane-findings"),
  overviewCards: document.querySelector("#overview-cards"),
  timelineDigest: document.querySelector("#timeline-digest"),
  profileVersions: document.querySelector("#profile-versions"),
  timelineList: document.querySelector("#timeline-list"),
  eventCount: document.querySelector("#event-count"),
  evidenceLinks: document.querySelector("#evidence-links"),
  recordPanel: document.querySelector("#record-panel"),
  recordJson: document.querySelector("#record-json"),
  closeRecord: document.querySelector("#close-record"),
};

function apiPath(agentId, suffix = "") {
  const base = `/api/v1/agents/${encodeURIComponent(agentId)}`;
  return suffix ? `${base}/${suffix}` : base;
}

async function fetchJson(url) {
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message || payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function text(tagName, value, className = "") {
  const node = document.createElement(tagName);
  node.textContent = value == null ? "—" : String(value);
  if (className) node.className = className;
  return node;
}

function card(label, value) {
  const node = document.createElement("article");
  node.className = "card";
  node.append(text("p", label, "label"), text("p", value, "value"));
  return node;
}

function setStatus(message) {
  elements.loadStatus.textContent = message;
}

function shortRef(value) {
  const raw = String(value || "");
  if (raw.length <= 38) return raw || "—";
  return `${raw.slice(0, 19)}…${raw.slice(-14)}`;
}

function showIntegrity(title, message) {
  elements.integrityTitle.textContent = title;
  elements.integrityMessage.textContent = message;
  elements.integrityBanner.hidden = false;
}

function renderControlPlane(payload) {
  const health = payload.health || {};
  const trigger = payload.trigger || {};
  elements.controlPlaneCards.replaceChildren(
    card("Catalog generation", payload.generation),
    card("Publication integrity", payload.integrity_status),
    card("Authoritative agents", `${payload.authoritative_agent_count}/${payload.agent_count}`),
    card("Publisher lag", health.publisher_lag_seconds == null ? "—" : `${health.publisher_lag_seconds}s`),
    card("Pending requests", health.pending_request_count ?? 0),
    card("Quarantined", health.quarantined_request_count ?? 0),
    card("Active signing key", payload.active_key_id),
    card("Trigger agents", (trigger.agent_ids || []).length),
  );
  elements.publicationDigest.textContent = payload.publication_digest
    ? `publication digest · ${payload.publication_digest}`
    : "publication digest unavailable";

  const refs = (trigger.tail_event_refs || []).map((value, index) => {
    const item = document.createElement("li");
    item.textContent = `${index + 1}. ${value}`;
    return item;
  });
  if (!refs.length) refs.push(text("li", "No triggering references available."));
  elements.triggerRefs.replaceChildren(...refs);

  const findings = payload.findings || [];
  if (!findings.length) {
    elements.controlPlaneFindings.replaceChildren(
      text("p", "Publication, checkpoint, and trigger metadata agree.", "ok"),
    );
  } else {
    elements.controlPlaneFindings.replaceChildren(
      ...findings.map((finding) => {
        const node = document.createElement("div");
        node.className = "finding";
        node.append(
          text("span", finding.code || "UNKNOWN", "finding-code"),
          text("p", finding.message || "Control Plane finding"),
        );
        return node;
      }),
    );
  }
  if (!payload.authoritative) {
    showIntegrity(
      "Control Plane status is not authoritative",
      "Publication, checkpoint, or trigger evidence failed verification.",
    );
  }

  const manifest = payload.links?.acceptance_manifest;
  elements.evidenceLinks.dataset.manifest = manifest || "";
}

function renderTimelineOverview(payload) {
  const timeline = payload.timeline || {};
  const integrity = timeline.integrity || {};
  const profile = payload.active_profile || payload.observed_active_profile || {};
  elements.overviewCards.replaceChildren(
    card("Agent", payload.agent_id),
    card("Lifecycle status", timeline.status || "unknown"),
    card("Timeline integrity", payload.integrity_status),
    card("Authoritative profile", payload.authoritative ? `v${profile.version}` : "withheld"),
    card("Durable events", integrity.event_count ?? timeline.events?.length ?? 0),
    card("Findings", payload.findings?.length ?? 0),
  );
  elements.timelineDigest.textContent = integrity.timeline_digest
    ? `timeline digest · ${integrity.timeline_digest}`
    : "timeline digest unavailable";
  if (!payload.authoritative) {
    showIntegrity(
      "Agent profile is not authoritative",
      "The timeline remains visible for investigation, but its active profile is withheld.",
    );
  }
}

function formatValue(value) {
  if (value === null || value === undefined) return "null";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function renderProfiles(payload) {
  const nodes = (payload.profiles || []).map((profile, index) => {
    const node = document.createElement("article");
    node.className = `profile-card${profile.authoritative ? " current" : ""}`;
    const header = document.createElement("header");
    const heading = document.createElement("div");
    heading.append(
      text("p", profile.authoritative ? "Current authoritative" : "Historical snapshot", "eyebrow"),
      text("h3", profile.profile_id || `Profile v${profile.version}`),
    );
    header.append(heading, text("span", `v${profile.version}`, "version-pill"));
    const traits = document.createElement("ul");
    traits.className = "trait-list";
    Object.entries(profile.traits || {})
      .sort(([a], [b]) => a.localeCompare(b))
      .forEach(([key, value]) => {
        const item = document.createElement("li");
        item.append(text("strong", key), text("code", formatValue(value)));
        traits.append(item);
      });
    node.append(header, text("h3", "Traits"), traits);
    if (index > 0) {
      const changes = document.createElement("ul");
      changes.className = "change-list";
      (profile.trait_changes || []).forEach((change) => {
        const item = document.createElement("li");
        item.append(
          text("strong", change.key),
          text("code", `${formatValue(change.before)} → ${formatValue(change.after)}`),
        );
        changes.append(item);
      });
      node.append(text("h3", "Changes from previous version"), changes);
    }
    return node;
  });
  elements.profileVersions.replaceChildren(...nodes);
}

function renderTimeline(payload) {
  const events = payload.timeline?.events || [];
  const nodes = events.map((event) => {
    const item = document.createElement("li");
    item.className = "timeline-item";
    const dot = document.createElement("span");
    dot.className = "timeline-dot";
    dot.setAttribute("aria-hidden", "true");
    const content = document.createElement("article");
    content.className = "timeline-content";
    const header = document.createElement("header");
    const labels = document.createElement("div");
    labels.append(
      text("span", String(event.event_type || "UNKNOWN").replaceAll("IDENTITY_", "").replaceAll("_", " "), "event-type"),
      text("h3", `Event ${Number(event.sequence) + 1}`),
    );
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "View source record";
    button.addEventListener("click", () => openRecord(event.source_record_url));
    header.append(labels, button);
    const meta = document.createElement("div");
    meta.className = "event-meta";
    meta.append(
      text("span", `Actor: ${event.actor || "—"}`),
      text("span", `Time: ${event.created_at || "—"}`),
      text("span", `Ref: ${shortRef(event.event_ref)}`),
      text("span", `Parent: ${shortRef(event.parent_event_id)}`),
    );
    content.append(header, meta);
    item.append(dot, content);
    return item;
  });
  elements.timelineList.replaceChildren(...nodes);
  elements.eventCount.textContent = `${events.length} durable event${events.length === 1 ? "" : "s"}`;
}

function renderEvidence(payload) {
  const links = payload.links || {};
  const items = [
    ["Download identity-timeline.json", links.timeline_evidence],
    ["Download identity-events.jsonl", links.events_evidence],
  ];
  const manifest = elements.evidenceLinks.dataset.manifest;
  if (manifest) items.push(["Download acceptance manifest", manifest]);
  elements.evidenceLinks.replaceChildren(
    ...items.filter(([, href]) => href).map(([label, href]) => {
      const link = document.createElement("a");
      link.href = href;
      link.textContent = label;
      link.setAttribute("download", "");
      return link;
    }),
  );
}

async function openRecord(url) {
  try {
    const payload = await fetchJson(url);
    elements.recordJson.textContent = JSON.stringify(payload.event, null, 2);
    elements.recordPanel.hidden = false;
    elements.closeRecord.focus();
  } catch (error) {
    setStatus(`Unable to load source record: ${error.message}`);
  }
}

function closeRecord() {
  elements.recordPanel.hidden = true;
  elements.recordJson.textContent = "";
}

async function loadAgent(agentId) {
  if (!agentId) return;
  state.agentId = agentId;
  const [timeline, profiles] = await Promise.all([
    fetchJson(apiPath(agentId, "timeline")),
    fetchJson(apiPath(agentId, "profiles")),
  ]);
  renderTimelineOverview(timeline);
  renderProfiles(profiles);
  renderTimeline(timeline);
  renderEvidence(timeline);
}

async function loadAll() {
  setStatus("Verifying publication and replaying durable evidence…");
  elements.refreshButton.disabled = true;
  elements.integrityBanner.hidden = true;
  try {
    const [controlPlane, agentsPayload] = await Promise.all([
      fetchJson("/api/v1/control-plane/status"),
      fetchJson("/api/v1/agents"),
    ]);
    renderControlPlane(controlPlane);
    const agents = agentsPayload.agents || [];
    const options = agents.map((agent) => {
      const option = document.createElement("option");
      option.value = agent.agent_id;
      option.textContent = `${agent.agent_id} · ${agent.integrity_status}`;
      return option;
    });
    elements.agentSelect.replaceChildren(...options);
    const selected = agents.some((item) => item.agent_id === state.agentId)
      ? state.agentId
      : agents[0]?.agent_id;
    if (selected) {
      elements.agentSelect.value = selected;
      await loadAgent(selected);
    }
    setStatus(controlPlane.authoritative ? "All evidence verified." : "Evidence loaded with fail-closed findings.");
  } catch (error) {
    showIntegrity("Control Plane could not be loaded", error.message);
    setStatus(`Load failed: ${error.message}`);
  } finally {
    elements.refreshButton.disabled = false;
  }
}

elements.agentSelect.addEventListener("change", (event) => {
  loadAgent(event.target.value).catch((error) => setStatus(`Agent load failed: ${error.message}`));
});
elements.refreshButton.addEventListener("click", loadAll);
elements.closeRecord.addEventListener("click", closeRecord);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !elements.recordPanel.hidden) closeRecord();
});

loadAll();

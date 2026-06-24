"use strict";

const state = {
  agentId: "",
  timeline: null,
  profiles: null,
};

const elements = {
  agentSelect: document.querySelector("#agent-select"),
  refreshButton: document.querySelector("#refresh-button"),
  loadStatus: document.querySelector("#load-status"),
  integrityBanner: document.querySelector("#integrity-banner"),
  integrityTitle: document.querySelector("#integrity-title"),
  integrityMessage: document.querySelector("#integrity-message"),
  overviewCards: document.querySelector("#overview-cards"),
  timelineDigest: document.querySelector("#timeline-digest"),
  profileVersions: document.querySelector("#profile-versions"),
  timelineList: document.querySelector("#timeline-list"),
  eventCount: document.querySelector("#event-count"),
  findingsList: document.querySelector("#findings-list"),
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

function setStatus(message) {
  elements.loadStatus.textContent = message;
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

function formatValue(value) {
  if (value === null || value === undefined) return "null";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function shortRef(value) {
  const raw = String(value || "");
  if (raw.length <= 34) return raw || "—";
  return `${raw.slice(0, 17)}…${raw.slice(-12)}`;
}

function renderIntegrity(payload) {
  const valid = payload.integrity_status === "VALID" && payload.authoritative === true;
  elements.integrityBanner.hidden = valid;
  if (valid) return;
  elements.integrityTitle.textContent = "Timeline is not authoritative";
  elements.integrityMessage.textContent =
    "Evidence remains visible for investigation, but the active profile is withheld because integrity or replay checks failed.";
}

function renderOverview(payload) {
  const timeline = payload.timeline || {};
  const integrity = timeline.integrity || {};
  const profile = payload.active_profile || payload.observed_active_profile || {};
  const cards = [
    card("Agent", payload.agent_id),
    card("Lifecycle status", timeline.status || "unknown"),
    card("Integrity", payload.integrity_status),
    card("Authoritative profile", payload.authoritative ? `v${profile.version}` : "withheld"),
    card("Durable events", integrity.event_count ?? timeline.events?.length ?? 0),
    card("Findings", payload.findings?.length ?? 0),
  ];
  elements.overviewCards.replaceChildren(...cards);
  elements.timelineDigest.textContent = integrity.timeline_digest
    ? `timeline digest · ${integrity.timeline_digest}`
    : "timeline digest unavailable";
}

function renderProfiles(payload) {
  const profiles = payload.profiles || [];
  const nodes = profiles.map((profile, index) => {
    const node = document.createElement("article");
    node.className = `profile-card${profile.authoritative ? " current" : ""}`;

    const header = document.createElement("header");
    const heading = document.createElement("div");
    heading.append(
      text("p", profile.authoritative ? "Current authoritative" : "Historical snapshot", "eyebrow"),
      text("h3", profile.profile_id || `Profile v${profile.version}`),
    );
    header.append(heading, text("span", `v${profile.version}`, "version-pill"));

    const traitsHeading = text("h3", "Traits");
    const traits = document.createElement("ul");
    traits.className = "trait-list";
    Object.entries(profile.traits || {})
      .sort(([a], [b]) => a.localeCompare(b))
      .forEach(([key, value]) => {
        const item = document.createElement("li");
        item.append(text("strong", key), text("code", formatValue(value)));
        traits.append(item);
      });

    node.append(header, traitsHeading, traits);

    if (index > 0) {
      const changesHeading = text("h3", "Changes from previous version");
      const changes = document.createElement("ul");
      changes.className = "change-list";
      (profile.trait_changes || []).forEach((change) => {
        const item = document.createElement("li");
        item.className = "change";
        item.append(
          text("strong", change.key),
          text("code", `${formatValue(change.before)} → ${formatValue(change.after)}`),
        );
        changes.append(item);
      });
      if (!changes.childElementCount) {
        changes.append(text("li", "No trait changes recorded."));
      }
      node.append(changesHeading, changes);
    }
    return node;
  });
  elements.profileVersions.replaceChildren(...nodes);
}

function eventLabel(eventType) {
  return String(eventType || "UNKNOWN").replaceAll("IDENTITY_", "").replaceAll("_", " ");
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
      text("span", eventLabel(event.event_type), "event-type"),
      text("h3", `Event ${Number(event.sequence) + 1}`),
    );

    const viewButton = document.createElement("button");
    viewButton.type = "button";
    viewButton.textContent = "View source record";
    viewButton.addEventListener("click", () => openRecord(event.source_record_url, event.event_ref));
    header.append(labels, viewButton);

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

function renderFindings(payload) {
  const findings = payload.findings || [];
  if (!findings.length) {
    elements.findingsList.replaceChildren(
      text("p", "No integrity or semantic findings. The timeline replay is valid.", "no-findings"),
    );
    return;
  }
  const nodes = findings.map((finding) => {
    const node = document.createElement("article");
    node.className = "finding";
    node.append(
      text("span", finding.code || "UNKNOWN", "finding-code"),
      text("h3", finding.message || "Timeline finding"),
      text("p", finding.event_ref ? `Event: ${finding.event_ref}` : `Source: ${finding.source || "timeline"}`),
    );
    return node;
  });
  elements.findingsList.replaceChildren(...nodes);
}

function renderEvidence(payload) {
  const links = payload.links || {};
  const items = [
    ["Download identity-timeline.json", links.timeline_evidence],
    ["Download identity-events.jsonl", links.events_evidence],
  ];
  const nodes = items
    .filter(([, href]) => Boolean(href))
    .map(([label, href]) => {
      const link = document.createElement("a");
      link.href = href;
      link.textContent = label;
      link.setAttribute("download", "");
      return link;
    });
  elements.evidenceLinks.replaceChildren(...nodes);
}

async function openRecord(url, eventRef) {
  try {
    setStatus(`Loading ${shortRef(eventRef)}…`);
    const payload = await fetchJson(url);
    elements.recordJson.textContent = JSON.stringify(payload.event, null, 2);
    elements.recordPanel.hidden = false;
    elements.closeRecord.focus();
    setStatus("Source record loaded.");
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
  setStatus("Replaying append-only evidence…");
  elements.refreshButton.disabled = true;
  try {
    const [timeline, profiles] = await Promise.all([
      fetchJson(apiPath(agentId, "timeline")),
      fetchJson(apiPath(agentId, "profiles")),
    ]);
    state.timeline = timeline;
    state.profiles = profiles;
    renderIntegrity(timeline);
    renderOverview(timeline);
    renderProfiles(profiles);
    renderTimeline(timeline);
    renderFindings(timeline);
    renderEvidence(timeline);
    setStatus(
      timeline.authoritative
        ? "Evidence replayed. Profile is authoritative."
        : "Evidence replayed with findings. Profile is withheld.",
    );
  } catch (error) {
    elements.integrityBanner.hidden = false;
    elements.integrityTitle.textContent = "Timeline could not be loaded";
    elements.integrityMessage.textContent = error.message;
    setStatus(`Load failed: ${error.message}`);
  } finally {
    elements.refreshButton.disabled = false;
  }
}

async function loadAgents() {
  setStatus("Discovering agents…");
  try {
    const payload = await fetchJson("/api/v1/agents");
    const agents = payload.agents || [];
    const options = agents.map((agent) => {
      const option = document.createElement("option");
      option.value = agent.agent_id;
      option.textContent = `${agent.agent_id} · ${agent.integrity_status}`;
      return option;
    });
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No identity timelines found";
      elements.agentSelect.replaceChildren(option);
      setStatus("No timelines found.");
      return;
    }
    elements.agentSelect.replaceChildren(...options);
    const firstAgent = agents[0].agent_id;
    elements.agentSelect.value = firstAgent;
    await loadAgent(firstAgent);
  } catch (error) {
    setStatus(`Agent discovery failed: ${error.message}`);
  }
}

elements.agentSelect.addEventListener("change", (event) => loadAgent(event.target.value));
elements.refreshButton.addEventListener("click", () => loadAgent(state.agentId));
elements.closeRecord.addEventListener("click", closeRecord);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !elements.recordPanel.hidden) closeRecord();
});

loadAgents();

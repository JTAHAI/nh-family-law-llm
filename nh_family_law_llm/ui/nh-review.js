/* Local review desk: no third-party scripts, persistence, or external model calls. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "local-nh-review"};
  let report = null, epoch = 0, activeController = null, sourceEpoch = 0;
  const dateValue = () => $("as-of").value;
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  };
  const message = (text) => { $("status").textContent = text; };
  const error = (text) => { $("error").textContent = text; $("error").hidden = !text; };
  const safeOfficialURL = (value) => {
    try {
      const url = new URL(value);
      return url.protocol === "https:" && !url.username && !url.password &&
        ["gc.nh.gov", "www.gc.nh.gov", "courts.nh.gov", "www.courts.nh.gov", "dhhs.nh.gov", "www.dhhs.nh.gov"].includes(url.hostname) ? url.href : null;
    } catch (_) { return null; }
  };
  async function request(path, options = {}) {
    const response = await fetch(path, {cache: "no-store", credentials: "same-origin", ...options, headers: {...headers, ...(options.headers || {})}});
    let data;
    try { data = await response.json(); } catch (_) { throw new Error("The local service returned an unreadable response."); }
    if (!response.ok) {
      const detail = data.detail;
      const text = detail && typeof detail === "object" && !Array.isArray(detail) ? detail.message || detail.error : "Request could not be completed. Check the supplied values and local service.";
      throw new Error(String(text));
    }
    return data;
  }
  function invalidate() {
    epoch += 1; report = null; $("export").disabled = true;
    if (activeController) activeController.abort();
    activeController = null; $("analyze").disabled = false; $("results").setAttribute("aria-busy", "false");
    $("results").replaceChildren(el("p", "Inputs changed. Run a new review before using or exporting the results.", "hint"));
    error("");
  }
  function listSection(title, items, target) {
    if (!Array.isArray(items) || !items.length) return;
    const section = el("section", undefined, "result-section");section.append(el("h3", title));
    const list = el("ul");for (const item of items) list.append(el("li", item));section.append(list);target.append(section);
  }
  function sourceCard(item) {
    const card = el("article", undefined, "source");
    card.append(el("strong", item.citation), el("small", item.title), el("small", item.retrieval_eligible ? "Reviewed summary available for selected date" : "Not active · do not rely on this summary"));
    const actions = el("div", undefined, "source-actions");
    const button = el("button", "Inspect summary", "secondary");button.type = "button";button.disabled = item.retrieval_eligible !== true;
    button.addEventListener("click", () => showSource(item.authority_id));actions.append(button);
    const url = safeOfficialURL(item.source_url);
    if (url) {const link = el("a", "Official source ↗");link.href = url;link.target = "_blank";link.rel = "noopener noreferrer";actions.append(link);}
    card.append(actions);return card;
  }
  async function showSource(id) {
    const current = ++sourceEpoch;
    $("source-title").textContent = "Loading source summary…";$("source-text").textContent = "";$("source-notice").textContent = "";$("source-metadata").textContent = "";
    if (!$("source-dialog").open) $("source-dialog").showModal();
    try {
      const data = await request(`/api/nh-review/sources/${encodeURIComponent(id)}?as_of_date=${encodeURIComponent(dateValue())}`);
      if (current !== sourceEpoch) return;
      $("source-title").textContent = data.citation;
      $("source-notice").textContent = data.notice;
      $("source-metadata").textContent = `As of ${data.as_of_date} · Capsule SHA-256: ${data.sha256}`;
      $("source-text").textContent = data.text;
    } catch (err) { if (current === sourceEpoch) $("source-notice").textContent = err.message; }
  }
  function render(data) {
    const target = $("results");target.replaceChildren();
    target.append(el("p", `Review date: ${data.as_of_date}. ${data.status === "blocked" ? "Some conclusions are blocked; resolve the identified gaps." : "All output requires human review."}`, "notice"));
    for (const item of data.findings || []) {
      const finding = el("article", undefined, "finding");
      finding.append(el("span", String(item.status).replaceAll("_", " "), `badge ${item.severity === "blocker" ? "blocker" : ""}`),el("h3", item.title),el("p", item.explanation));
      listSection("Evidence to gather", item.evidence_needed, finding);listSection("Caveats", item.caveats, finding);target.append(finding);
    }
    listSection("Authority gaps — resolve before relying on the result", data.authority_gaps, target);
    listSection("Missing facts", data.missing_facts, target);
    listSection("Evidence checklist", data.evidence_checklist, target);
    for (const route of data.routes || []) {const box = el("section", undefined, "result-section");box.append(el("h3", route.label),el("p", route.explanation));listSection("Next documents", route.next_documents, box);target.append(box);}
    listSection("Drafting controls", data.drafting_controls, target);listSection("Important notices", data.notices, target);
    const sources = el("section", undefined, "result-section");sources.append(el("h3", "Sources used / sources still needed"));
    for (const source of data.authority_references || []) sources.append(sourceCard(source));target.append(sources);
  }
  async function refresh() {
    const selectedDate = dateValue();
    if (!selectedDate) return;
    try {
      const data = await request(`/api/nh-review/status?as_of_date=${encodeURIComponent(selectedDate)}`);
      if (selectedDate !== dateValue()) return;
      $("coverage").textContent = `${data.active_catalog_source_count} of ${data.catalog_source_count} catalog summaries available for ${data.as_of_date}. Snapshot review date: ${data.snapshot_as_of_date}. This is not exhaustive NH authority coverage.`;
      $("source-list").replaceChildren(...data.sources.map(sourceCard));
      message(data.known_amendment_blocks.length ? `Known effective amendments block: ${data.known_amendment_blocks.join(", ")}. Source review is required.` : "Local reviewed-summary snapshot available. Official law and current forms still need review.");
    } catch (err) {
      if (selectedDate !== dateValue()) return;
      $("source-list").replaceChildren();$("coverage").textContent = "Authority status unavailable. No source is approved by this error state.";message("Authority snapshot unavailable.");error(err.message);
    }
  }
  $("review-form").addEventListener("submit", async (event) => {
    event.preventDefault();invalidate();const current = epoch;
    let facts = {};
    try {
      if ($("facts").value.trim()) facts = JSON.parse($("facts").value);
      if (!facts || typeof facts !== "object" || Array.isArray(facts)) throw new Error("Facts must be a JSON object.");
    } catch (err) {error(`Check the optional facts: ${err.message}`);return;}
    const payload = {...facts, question: $("question").value, as_of_date: dateValue()};
    activeController = new AbortController();$("analyze").disabled = true;$("results").setAttribute("aria-busy", "true");message("Checking reported facts and required authorities…");
    try {
      const data = await request("/api/legal-behavior/analyze", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload),signal:activeController.signal});
      if (current !== epoch) return;
      if (data.review_required !== true || data.filing_ready !== false || data.legal_advice !== false) throw new Error("The response did not preserve the review-required safety flags.");
      report = data;render(data);$("export").disabled = false;message(data.status === "blocked" ? "Review complete with blockers. Resolve missing or unavailable authority before relying on any conclusion." : "Review complete. This output requires human review.");
    } catch (err) {if (current === epoch && err.name !== "AbortError") {error(err.message);message("Review not completed. No export is available.");}}
    finally {if (current === epoch) {activeController = null;$("analyze").disabled = false;$("results").setAttribute("aria-busy", "false");}}
  });
  $("export").addEventListener("click", async () => {
    const current = epoch, selected = report;if (!selected) return;
    try {
      const reportText = JSON.stringify(selected);
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(reportText));
      if (current !== epoch || selected !== report) return;
      const envelope = {schema:"nhfl.review-export.v1",metadata:{producer:"New Hampshire Family Law LLM",version:document.body.dataset.version,jurisdiction:"NH",exported_at:new Date().toISOString(),review_required:true,filing_ready:false,legal_advice:false},report_sha256:Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,"0")).join(""),report_serialization:"compact UTF-8 JSON.stringify(report)",report:selected};
      const url = URL.createObjectURL(new Blob([JSON.stringify(envelope,null,2)+"\n"],{type:"application/json"}));
      const link = el("a");link.href = url;link.download = `nh-review-${selected.as_of_date}.json`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    } catch (err) {error(`Export was not created: ${err.message}`);}
  });
  for (const id of ["question","facts","as-of"]) $(id).addEventListener("input", invalidate);
  $("as-of").addEventListener("change", () => {sourceEpoch += 1;$("source-dialog").close();refresh();});
  $("clear").addEventListener("click", () => {invalidate();$("question").value="";$("facts").value="";$("question").focus();message("Review cleared. No facts were saved by this workflow.");});
  $("refresh").addEventListener("click", refresh);
  $("close-source").addEventListener("click", () => {sourceEpoch += 1;$("source-dialog").close();});
  const now = new Date();$("as-of").value = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
  refresh();
})();

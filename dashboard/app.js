/* Calypso⁻¹ judge dashboard.
 *
 * Reads the backend's event bus (`GET /events/recent` to backfill, then `GET /stream` over SSE)
 * and renders it as a live architecture graph plus call, recall, health and day panels.
 * `?demo=1` (or `demo=idle` / `demo=offline`) replays a scripted day from demo.js instead.
 * `?token=…` is remembered and unlocks `/people` and `/days` (names and the day timeline).
 */
(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const DEMO = params.get("demo");
  const PULSE_MS = 2500;        // how long a node stays lit after its event
  const CARD_MIN_S = 6, CARD_MAX_S = 10;
  const PUCK_OFFLINE_S = 60;
  const TARGET_CARD_S = 2.5;    // sentence end → card on screen
  const FACE_HOLD_MS = 10000;   // a face identification outranks voice-only results for this long
  const CALLER = "caller";      // participant row for the 1:1 setup-call caller
  const MODE_LABEL = { setup: "Setup call", recognize: "Recognition call", group: "Group call" };
  const callLabel = (c) => (c && (MODE_LABEL[c.mode] || MODE_LABEL[c.kind])) || "FaceTime call";

  // ---- token ------------------------------------------------------------------
  let token = null;
  try {
    if (params.get("token")) {
      localStorage.setItem("calypso.token", params.get("token"));
      params.delete("token");
      history.replaceState(null, "", location.pathname + (params.toString() ? "?" + params : ""));
    }
    token = localStorage.getItem("calypso.token");
  } catch (_) { /* storage blocked: names and the timeline stay hidden */ }

  // ---- state ------------------------------------------------------------------
  const S = {
    events: [],                 // newest last, capped
    total: 0,
    people: {},                 // id → Person
    days: null,                 // DayEvent[] | null (null = not loaded / no token)
    pulses: {},                 // node key → last pulse ms
    counts: {},                 // stage → count
    health: null, healthAt: 0,
    segments: {},               // segment_uuid → {at, tags}
    sounds: [],                 // {start, end, label} from puck.segment
    segCount: 0, lastSegmentAt: 0, lastProcessedAt: 0, lastFailedAt: 0,
    call: null,                 // {id, kind, started}
    calls: [],                  // {start, end, kind}
    lastCallEnded: null,
    participants: new Map(),    // key → {status, personId, face, voice, th, at}
    lines: [],                  // {speaker, text, at, highlight}
    lastLineAt: 0,
    intent: null, recall: null, // last recall.detect / recall.search payloads
    recognizeCount: 0,
    card: null, cardAt: 0, cardsShown: 0, queued: 0,
    lat: { card: [], seg: [], ctrl: [], recall: [] },
    stream: "connecting",
  };

  // ---- tiny DOM helpers ---------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "style") el.style.cssText = v;
      else el.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
    return el;
  }
  const SVGNS = "http://www.w3.org/2000/svg";
  function s(tag, attrs) {
    const el = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
  }
  const feather = () => {
    const svg = s("svg", { width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" });
    svg.append(s("path", { d: "M20.2 4.8a5.5 5.5 0 0 0-7.8 0L6 11.2V18h6.8l6.4-6.4a5.5 5.5 0 0 0 0-7.8z" }), s("path", { d: "M16 8 2 22M17.5 15H9" }));
    return svg;
  };
  const photoGlyph = () => {
    const svg = s("svg", { width: 40, height: 40, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 1.6, "stroke-linecap": "round", "stroke-linejoin": "round" });
    svg.append(s("path", { d: "m3 17 5-5 4 4 3-3 6 6" }), s("circle", { cx: 16, cy: 8, r: 2 }));
    return svg;
  };
  const person = () => {
    const svg = s("svg", { width: 28, height: 28, viewBox: "0 0 24 24", fill: "currentColor", opacity: 0.45 });
    svg.append(s("circle", { cx: 12, cy: 8, r: 4 }), s("path", { d: "M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7z" }));
    return svg;
  };

  // ---- time helpers -------------------------------------------------------------
  const tsMs = (ev) => Date.parse(ev.ts) || Date.now();
  const nowMs = () => Date.now();
  function ago(ms) {
    if (!ms) return "never";
    const sec = Math.max(0, Math.round((nowMs() - ms) / 1000));
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
    return `${Math.round(sec / 3600)}h ago`;
  }
  const clock = (ms) => new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const clockSec = (ms) => new Date(ms).toLocaleTimeString([], { hour12: false });
  const secs = (ms) => `${(ms / 1000).toFixed(1)} s`;
  const fmt = (n) => (n == null ? "—" : Number(n).toFixed(2));
  const pushLat = (key, ms) => { if (ms >= 0 && ms < 60000) { S.lat[key].push(ms); if (S.lat[key].length > 24) S.lat[key].shift(); } };
  const lastLat = (key) => S.lat[key][S.lat[key].length - 1];

  const nameOf = (id) => (id && S.people[id] && S.people[id].name) || null;

  // ---- event reducer ---------------------------------------------------------------
  function pulse(...keys) { const t = nowMs(); for (const k of keys) S.pulses[k] = t; }

  function apply(ev, live) {
    const p = ev.payload || {};
    const at = live ? nowMs() : tsMs(ev);
    S.events.push(ev); if (S.events.length > 200) S.events.shift();
    S.total += 1;
    S.counts[ev.stage] = (S.counts[ev.stage] || 0) + 1;
    const lit = (...k) => live && pulse(...k);

    switch (ev.stage) {
      case "puck.health":
        S.health = p; S.healthAt = at; lit("puck"); break;
      case "puck.segment": {
        S.segCount += 1; S.lastSegmentAt = at;
        S.segments[p.segment_uuid] = { at };
        const top = (p.sound_tags || []).slice().sort((a, b) => b.score - a.score)[0];
        if (top && p.ts_start) S.sounds.push({ start: Date.parse(p.ts_start), end: Date.parse(p.ts_end || p.ts_start), label: top.label });
        if (S.sounds.length > 400) S.sounds.shift();
        lit("puck", "ingest"); break;
      }
      case "puck.processed": {
        const seg = S.segments[p.segment_uuid];
        if (seg) pushLat("seg", at - seg.at);
        S.lastProcessedAt = at; lit("worker"); break;
      }
      case "puck.failed": S.lastFailedAt = at; lit("worker"); break;
      case "day.built": lit("day"); loadDay(); break;
      case "person.created": case "person.updated": loadPeople(); break;
      case "person.enrolled": {
        // A setup call just saved (or updated) the caller: show who they are now.
        const row = S.participants.get(CALLER);
        if (S.call && p.call_id === S.call.id && row) {
          Object.assign(row, { status: "enrolled", personId: p.person_id, at, matched: !!p.matched_existing,
            prints: { face: p.face_prints_added ?? 0, voice: p.voice_prints_added ?? 0 } });
        }
        loadPeople(); lit("ctrl"); break;
      }

      case "call.started":
        S.call = { id: p.call_id, kind: p.kind || "call", mode: null, started: at };
        S.participants.clear(); S.lines = []; S.intent = null; S.recall = null;
        lit("agent"); break;
      case "agent.session":
        // The call log stores recognize calls as "group"; this carries the real mode.
        if (S.call && p.call_id === S.call.id) {
          S.call.mode = p.mode;
          if (p.mode === "setup") S.participants.set(CALLER, { key: CALLER, status: "setup", personId: null, face: null, voice: null, th: {}, at });
        }
        lit("agent", "ctrl"); break;
      case "call.ended":
        if (S.call) S.calls.push({ start: S.call.started, end: at, kind: S.call.kind, mode: S.call.mode });
        S.lastCallEnded = at; S.call = null; lit("agent"); break;
      case "call.line":
        S.lines.push({ speaker: p.speaker, text: p.text, at, highlight: false });
        if (S.lines.length > 4) S.lines.shift();
        S.lastLineAt = at; lit("agent", "ctrl"); break;

      case "recognize": {
        S.recognizeCount += 1;
        const th = p.thresholds || {};
        const voice = (p.voice_top3 || [])[0];
        const faces = p.faces || [];
        const pk = p.participant_key || "p";
        // One face = one row per caller (keyed by participant); a composite grid gets one row per face.
        const keyFor = (i) => (faces.length > 1 ? `${pk}:${i}` : pk);
        for (const [i, f] of faces.entries()) {
          if (f.person_id && S.people[f.person_id] && S.people[f.person_id].is_patient) continue;
          const prev = S.participants.get(keyFor(i)) || {};
          const identifiedAt = f.status === "identified" ? at : prev.identifiedAt;
          S.participants.set(keyFor(i), { ...prev, key: keyFor(i), status: f.status, personId: f.person_id,
            face: (f.face_top3 || [])[0], voice: voice || prev.voice, th, at, identifiedAt });
        }
        if (!faces.length && p.voice_only) {
          // Voice alone (no face in this clip) only adds a voice score to the caller's row. It may not
          // undo a face identification from the last few seconds: face is the main signal.
          const prev = S.participants.get(pk);
          const faceRecent = prev && prev.identifiedAt && at - prev.identifiedAt < FACE_HOLD_MS;
          const vo = p.voice_only;
          if (faceRecent) S.participants.set(pk, { ...prev, voice, th, at });
          else if (!(vo.person_id && S.people[vo.person_id] && S.people[vo.person_id].is_patient)) {
            S.participants.set(pk, { ...(prev || {}), key: pk, status: vo.status, personId: vo.person_id,
              face: prev ? prev.face : null, voice, th, at,
              identifiedAt: vo.status === "identified" ? at : prev && prev.identifiedAt });
          }
        }
        lit("recog", "ctrl"); break;
      }
      case "recall.detect":
        S.intent = p.intent || null;
        if (S.intent && S.intent.intent !== "none") {
          const line = S.lines[S.lines.length - 1]; if (line) line.highlight = true;
          if (S.lastLineAt) pushLat("recall", at - S.lastLineAt);
        }
        lit("recall", "ctrl"); break;
      case "recall.search": S.recall = p; lit("recall"); break;

      case "card.queued":
        S.queued += 1;
        if (S.lastLineAt) pushLat("ctrl", at - S.lastLineAt);
        if (!S.card || at - S.cardAt > CARD_MAX_S * 1000) { S.card = p.card || null; S.cardAt = at; }
        lit("ctrl", "sched"); break;
      case "card.shown":
        S.queued = Math.max(0, S.queued - 1);
        S.card = p.card || p; S.cardAt = at; S.cardsShown += 1;
        if (S.lastLineAt && at - S.lastLineAt < 15000) pushLat("card", at - S.lastLineAt);
        lit("sched", "agent"); break;
    }
  }

  // ---- architecture graph ------------------------------------------------------------
  // Coordinates follow the Figma frame "Dashboard — Live call" (graph is 1336×284).
  const NW = 184, NH = 74;
  const NODES = {
    puck:   { x: 0,   y: 22,  name: "Puck" },
    ingest: { x: 236, y: 22,  name: "Ingest" },
    worker: { x: 472, y: 22,  name: "Speech + voice" },
    day:    { x: 708, y: 22,  name: "Day builder" },
    agent:  { x: 0,   y: 170, name: "Call agent" },
    ctrl:   { x: 236, y: 170, name: "Claude" },
    recog:  { x: 472, y: 130, name: "Recognize" },
    recall: { x: 472, y: 208, name: "Recall" },
    sched:  { x: 708, y: 170, name: "Card scheduler" },
  };
  const EDGES = [
    ["puck", "ingest"], ["ingest", "worker"], ["worker", "day"],
    ["agent", "ctrl"], ["ctrl", "recog"], ["ctrl", "recall"], ["recog", "sched"], ["recall", "sched"],
  ];
  const nodeEls = {}, edgeEls = {};

  function buildGraph() {
    const graph = $("graph"), svg = $("edges");
    for (const [a, b] of EDGES) {
      const A = NODES[a], B = NODES[b];
      const x1 = A.x + NW, y1 = A.y + NH / 2, x2 = B.x, y2 = B.y + NH / 2, mx = (x1 + x2) / 2;
      const path = s("path", { class: "edge", d: `M ${x1} ${y1} C ${mx} ${y1} ${mx} ${y2} ${x2} ${y2}` });
      svg.append(path); edgeEls[`${a}-${b}`] = path;
    }
    const S0 = NODES.sched;
    const toScreen = s("path", { class: "edge", d: `M ${S0.x + NW} ${S0.y + NH / 2} C ${S0.x + NW + 60} ${S0.y + NH / 2} 920 110 974 110` });
    svg.append(toScreen); edgeEls["sched-screen"] = toScreen;
    for (const [key, n] of Object.entries(NODES)) {
      const detail = h("span", { class: "node-detail" });
      const el = h("div", { class: "node", style: `left:${n.x}px;top:${n.y}px` },
        h("div", { class: "node-head" }, h("span", { class: "node-dot" }), h("span", { class: "node-name" }, n.name)), detail);
      graph.append(el); nodeEls[key] = { el, detail };
    }
    const fit = () => {
      const w = $("graph-fit").clientWidth, k = Math.min(1, w / 1336);
      graph.style.transform = `scale(${k})`;
      $("graph-fit").style.height = `${284 * k}px`;
    };
    new ResizeObserver(fit).observe($("graph-fit")); fit();
  }

  const isLit = (key) => nowMs() - (S.pulses[key] || 0) < PULSE_MS;
  const puckOffline = () => !S.healthAt || nowMs() - S.healthAt > PUCK_OFFLINE_S * 1000;
  const cardOnScreen = () => S.card && nowMs() - S.cardAt < CARD_MAX_S * 1000;

  function nodeDetail(key) {
    const h0 = S.health || {};
    switch (key) {
      case "puck": return puckOffline() ? (S.healthAt ? `offline · ${ago(S.healthAt)}` : "no heartbeat yet") : `${S.segCount} seg · queue ${h0.queue_depth ?? 0}`;
      case "ingest": return S.lastSegmentAt ? `segment · ${ago(S.lastSegmentAt)}` : "no segments yet";
      case "worker": return S.lastFailedAt > S.lastProcessedAt ? `failed · ${ago(S.lastFailedAt)}` : lastLat("seg") != null ? `STT · ${secs(lastLat("seg"))}` : "waiting";
      case "day": return S.days ? `${S.days.length} moments today` : `${S.counts["day.built"] || 0} builds`;
      case "agent": return S.call ? `${callLabel(S.call)} · ${S.participants.size} seen` : S.lastCallEnded ? `last call ${clock(S.lastCallEnded)}` : "waiting for a call";
      case "ctrl": return lastLat("ctrl") != null ? `controller · ${Math.round(lastLat("ctrl"))} ms` : "waiting";
      case "recog": return S.recognizeCount ? `face + voice · ${S.recognizeCount}` : "waiting";
      case "recall": {
        const best = bestRecall();
        if (best) return `best ${fmt(best.score)} ${best.score >= recallMin() ? "≥" : "<"} ${fmt(recallMin())}`;
        return S.intent ? `intent · ${S.intent.intent}` : "waiting";
      }
      case "sched": return cardOnScreen() ? `1 showing · ${S.queued} queued` : `${S.cardsShown} card${S.cardsShown === 1 ? "" : "s"} so far`;
    }
    return "";
  }

  function renderGraph() {
    for (const key of Object.keys(NODES)) {
      const { el, detail } = nodeEls[key];
      const off = key === "puck" && puckOffline();
      const on = !off && (isLit(key) || (key === "sched" && cardOnScreen() && nowMs() - S.cardAt < PULSE_MS));
      el.classList.toggle("active", on);
      el.classList.toggle("offline", off);
      detail.textContent = nodeDetail(key);
    }
    for (const [id, path] of Object.entries(edgeEls)) {
      const [a, b] = id.split("-");
      const on = b === "screen" ? cardOnScreen() : isLit(b) && (isLit(a) || b !== "sched");
      path.classList.toggle("active", on);
      path.classList.toggle("off", a === "puck" && puckOffline());
    }
  }

  // ---- card on screen ----------------------------------------------------------------
  function renderCard() {
    const slot = $("card-slot");
    if (!cardOnScreen()) {
      if (!slot.querySelector(".screen-empty")) {
        slot.replaceChildren(h("div", { class: "screen-empty" },
          h("img", { src: "art/gull-resting.png", alt: "" }),
          h("div", {}, h("div", { class: "participant-name" }, "Nothing on screen"),
            h("div", { class: "small soft" }, "Cards show up here during a FaceTime call."))));
      }
      $("card-latency").textContent = "";
      return;
    }
    const c = S.card, el = (S.card.__el ||= buildCard(c));
    if (slot.firstChild !== el) slot.replaceChildren(el);
    const shown = (nowMs() - S.cardAt) / 1000;
    el.querySelector(".timer-fill").style.width = `${Math.min(100, (shown / CARD_MAX_S) * 100)}%`;
    el.querySelector(".timer-text").textContent = `${shown.toFixed(1)} s of ${CARD_MIN_S}–${CARD_MAX_S} s`;
    const lat = lastLat("card");
    $("card-latency").textContent = lat != null ? `sentence → card ${secs(lat)}  ·  target ≤ ${TARGET_CARD_S} s` : "";
  }

  // Identity cards are separate facts ("Mary's brother", a memory); caption cards ("Let's talk",
  // "Saved") arrive pre-wrapped into short lines for the phone, so rejoin them into one sentence.
  function cardText(c) {
    const lines = c.lines || [];
    if (c.kind === "identity" || c.kind === "today") return lines.slice(0, 2).join(" · ");
    return lines.join(" ").replace(/\s+/g, " ").trim();
  }

  function buildCard(c) {
    const neutral = c.kind === "learning";
    const photo = h("div", { class: "screen-photo" });
    const img = (c.image_urls || [])[0];
    if (img) photo.style.backgroundImage = `url("${encodeURI(img)}")`;
    else photo.append(neutral ? feather() : photoGlyph());
    return h("div", { class: `screen-card${neutral ? " neutral" : ""}` },
      h("div", { class: "screen-body" }, photo,
        h("div", { style: "min-width:0" },
          h("div", { class: "screen-title" }, c.title || ""),
          h("div", { class: "screen-lines" }, cardText(c)))),
      h("div", { class: "timer" },
        h("div", { class: "timer-track" }, h("div", { class: "timer-fill", style: "width:0" })),
        h("span", { class: "mono-small timer-text" })));
  }

  // ---- header -----------------------------------------------------------------------
  function renderStatus() {
    const pills = [];
    if (S.call) {
      const sec = Math.floor((nowMs() - S.call.started) / 1000);
      pills.push(["live", `${callLabel(S.call)} · ${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`]);
    } else pills.push(["waiting", "Waiting for a call"]);
    pills.push(puckOffline() ? ["offline", S.healthAt ? `Puck offline · ${ago(S.healthAt)}` : "Puck not seen yet"] : ["ok", `Puck online · ${ago(S.healthAt)}`]);
    pills.push(DEMO ? ["ok", "Demo replay"] : S.stream === "open" ? ["ok", "Stream connected"] : ["offline", "Reconnecting…"]);
    $("subtitle").textContent = `Live system view · ${new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}`;
    $("status").replaceChildren(...pills.map(([cls, text]) => h("span", { class: `pill ${cls}` }, text)));
    document.body.classList.toggle("mode-live", !!S.call);
    document.body.classList.toggle("mode-idle", !S.call);
  }

  // ---- live panels --------------------------------------------------------------------
  function scoreBar(label, score, threshold) {
    const v = score == null ? 0 : Math.max(0, Math.min(1, score));
    const pass = score != null && threshold != null && score >= threshold;
    return h("div", { class: `score${pass ? " pass" : ""}` },
      h("span", { class: "score-label" }, label),
      h("div", { class: "score-track" },
        h("div", { class: "score-fill", style: `width:${Math.max(3, v * 100)}%` }),
        threshold != null && h("div", { class: "score-tick", style: `left:calc(${threshold * 100}% - 1px)` })),
      h("span", { class: "score-value" }, fmt(score)));
  }

  function participantCard(p) {
    const known = p.status === "identified" || p.status === "enrolled";
    const pr = known ? S.people[p.personId] : null;
    let name, detail, tag, tagCls = "", dashed = !known;
    if (p.status === "setup") {
      name = "Caller"; detail = "Introducing themselves to Calypso⁻¹"; tag = "Setting up"; tagCls = "learning";
    } else if (p.status === "enrolled") {
      name = nameOf(p.personId) || "New relative";
      const prints = p.prints ? `${p.prints.face} face · ${p.prints.voice} voice prints` : "";
      detail = [pr && pr.relationship, prints].filter(Boolean).join(" · ") || "Saved";
      tag = p.matched ? "Updated" : "Saved";
    } else if (known) {
      name = nameOf(p.personId) || "Known person";
      detail = pr ? [pr.relationship, (pr.facts || [])[0]].filter(Boolean).join(" · ") || "Known" : "Open with ?token= to show names";
      tag = "Known";
    } else if (p.status === "learning") {
      name = "New visitor"; detail = "Will ask once to learn their name"; tag = "Learning"; tagCls = "learning";
    } else {
      name = "Getting to know someone new…"; detail = "Close scores, so not guessing"; tag = "Not sure yet"; tagCls = "unsure";
    }
    const avatar = h("div", { class: `avatar${known ? "" : " unknown"}` });
    if (pr && pr.face_photo_url) avatar.style.backgroundImage = `url("${encodeURI(pr.face_photo_url)}")`;
    else avatar.append(known ? person() : feather());
    const scored = p.status !== "setup" && p.status !== "enrolled";  // setup calls enroll; they don't score
    return h("div", { class: `participant${dashed ? " dashed" : ""}` },
      h("div", { class: "participant-top" }, avatar,
        h("div", { class: "participant-text" }, h("div", { class: "participant-name" }, name), h("div", { class: "small soft" }, detail)),
        h("span", { class: `tag ${tagCls}` }, tag)),
      scored && scoreBar("Face", p.face && p.face.score, p.th.face_match),
      scored && scoreBar("Voice", p.voice && p.voice.score, p.th.voice_match));
  }

  // Chert names the caller "chert-bridge-<call id>"; show who they are instead.
  function speakerLabel(raw) {
    if (!raw || !raw.startsWith("chert-bridge-")) return raw || "Caller";
    for (const p of S.participants.values()) {
      if ((p.status === "identified" || p.status === "enrolled") && nameOf(p.personId)) return nameOf(p.personId);
    }
    return "Caller";
  }

  function renderCall() {
    const ps = [...S.participants.values()].slice(0, 2);  // in the order they were first seen
    $("call-sub").textContent = S.call ? `${callLabel(S.call)} · ${S.participants.size} seen` : "";
    $("participants").replaceChildren(...(ps.length ? ps.map(participantCard) : [h("div", { class: "empty-note" },
      h("img", { src: "art/gull-wave.png", alt: "" }), h("span", { class: "small soft" }, "Waiting to see who joined…"))]));

    $("transcript").replaceChildren(...(S.lines.length ? S.lines.map((l) =>
      h("div", { class: `line${l.highlight ? " highlight" : ""}` }, h("b", {}, speakerLabel(l.speaker)), h("span", {}, l.text)))
      : [h("span", { class: "small soft" }, "Nobody has spoken yet.")]));

    const kids = [h("div", { class: "recall-head" }, h("span", { class: "label soft" }, "Recall"),
      S.intent ? h("span", { class: "tag" }, S.intent.intent + (S.intent.query ? ` · “${S.intent.query}”` : "")) : h("span", { class: "small soft" }, "listening for a memory question"))];
    const matches = recallMatches();
    const min = recallMin();
    for (const m of matches.slice(0, 3)) kids.push(recallBar(m, min));
    if (S.intent && S.intent.intent !== "none" && !matches.length) kids.push(h("span", { class: "small soft" }, "Waiting for recall search results…"));
    if (matches.length && matches[0].score < min) kids.push(h("span", { class: "small soft" }, `Nothing scored above ${fmt(min)}, so no memory card is shown.`));
    $("recall").replaceChildren(...kids);
  }

  // recall.search is not emitted yet; accept a few likely shapes.
  function recallMatches() {
    const r = S.recall; if (!r) return [];
    const list = r.top3 || r.matches || r.results || [];
    return list.map((m) => ({ label: m.label || m.title || m.place || m.photo_id || m.id || "match", score: Number(m.score) || 0 }));
  }
  const recallMin = () => (S.recall && (S.recall.threshold ?? S.recall.recall_min)) ?? 0.35;
  const bestRecall = () => recallMatches()[0];
  const recallBar = (m, min) => scoreBar(m.label, m.score, min);

  function renderHealth() {
    const h0 = S.health || {};
    const off = puckOffline();
    const rows = [
      ["Puck queue", String(h0.queue_depth ?? "—"), off && S.healthAt ? `at last check-in, ${ago(S.healthAt)}` : "segments waiting"],
      ["Per segment", h0.ms_per_segment != null ? `${Math.round(h0.ms_per_segment)} ms` : "—", h0.sound_backend ? `sound tags · ${h0.sound_backend}` : "sound tags on the Pi"],
      ["Events", S.total.toLocaleString(), "since this page opened"],
    ];
    $("stats").replaceChildren(...rows.map(([l, v, n]) => h("div", { class: "stat" },
      h("div", { class: "stat-text" }, h("span", { class: "label soft" }, l), h("span", { class: "small soft" }, n)),
      h("span", { class: "stat-value" }, v))));
    $("sparks").replaceChildren(
      spark("Sentence → card", S.lat.card, TARGET_CARD_S * 1000),
      spark("Segment → transcript", S.lat.seg, null, off ? "paused" : null));
  }

  function spark(label, samples, target, override) {
    const W = 300, H = 44, pad = 4;
    const max = Math.max(target ? target * 1.4 : 0, ...samples, 1);
    const y = (v) => H - pad - (v / max) * (H - pad * 2);
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none" });
    if (target) svg.append(s("line", { x1: 0, x2: W, y1: y(target), y2: y(target), stroke: "var(--apricot)", "stroke-width": 2, "stroke-dasharray": "6 5", "vector-effect": "non-scaling-stroke" }));
    if (samples.length > 1) {
      const pts = samples.map((v, i) => `${(i / (samples.length - 1)) * W},${y(v)}`).join(" ");
      svg.append(s("polyline", { points: pts, fill: "none", stroke: "var(--peri-deep)", "stroke-width": 2.5, "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" }));
    }
    const last = samples[samples.length - 1];
    return h("div", { class: "spark" },
      h("div", { class: "spark-head" }, h("span", { class: "small soft" }, label), h("span", { class: "mono" }, override || (last != null ? secs(last) : "—"))),
      svg);
  }

  // ---- idle panels: day timeline + event stream ------------------------------------------
  function renderDay() {
    const today = new Date();
    $("day-title").textContent = patientName() ? `${patientName()}’s day so far` : "Today so far";
    $("day-sub").textContent = today.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });

    const days = S.days || [];
    const evs = days.map((d) => ({ ...d, s: Date.parse(d.start), e: Date.parse(d.end) }));
    const sounds = mergeSounds(S.sounds.filter((x) => x.start >= nowMs() - 18 * 3600e3));
    const calls = S.calls.concat(S.call ? [{ start: S.call.started, end: nowMs(), kind: S.call.kind }] : []);
    const hr = 3600e3;
    const times = [...evs.flatMap((e) => [e.s, e.e]), ...sounds.flatMap((x) => [x.start, x.end]), ...calls.flatMap((c) => [c.start, c.end])];
    const last = times.length ? Math.max(...times) : nowMs();
    if (nowMs() - last < 3 * hr) times.push(nowMs());  // only stretch to "now" when the data is recent
    if (!times.length) times.push(nowMs());
    let t0 = Math.min(...times), t1 = Math.max(...times);
    t0 = Math.floor(t0 / hr) * hr; t1 = Math.max(t0 + 6 * hr, Math.ceil(t1 / hr) * hr);
    const step = (t1 - t0) / hr > 9 ? 2 * hr : hr;
    const X = (t) => ((t - t0) / (t1 - t0)) * 100;

    const blocks = (items) => items.map(([kind, label, a, b, op, title]) =>
      h("div", { class: `block ${kind}`, title: title || label, style: `left:${X(a)}%;width:max(24px, ${X(b) - X(a)}%);opacity:${op ?? 1}` }, label));
    const lane = (label, items) => h("div", { class: "lane-row" }, h("span", { class: "label soft" }, label),
      h("div", { class: "track" }, ...blocks(items), nowMs() <= t1 && h("div", { class: "now-line", style: `left:${X(nowMs())}%` })));

    const hours = [];
    for (let t = t0; t < t1; t += step) hours.push(h("span", { class: "mono-small soft", style: `left:${X(t)}%` }, new Date(t).toLocaleTimeString([], { hour: "numeric" })));
    const rows = [h("div", { class: "lane-row" }, h("span", {}), h("div", { class: "axis" }, ...hours))];

    if (S.days) {
      rows.push(lane("People", evs.flatMap((e) => e.people.map((pid, i) =>
        ["speaker", nameOf(pid) || "Someone new", e.s + i * (e.e - e.s) / e.people.length, e.s + (i + 1) * (e.e - e.s) / e.people.length]))));
      rows.push(lane("Where", evs.map((e) => [e.place_confidence >= 0.6 ? "place" : "sound", e.place, e.s, e.e,
        e.place_confidence >= 0.6 ? Math.max(0.45, e.place_confidence) : 1,
        `${e.place} · confidence ${fmt(e.place_confidence)}${e.evidence.length ? "\n" + e.evidence.join("\n") : ""}`])));
    } else {
      rows.push(h("div", { class: "lane-row" }, h("span", { class: "label soft" }, "Moments"),
        h("span", { class: "small soft" }, token ? "Loading the day…" : "Open with ?token=… to load people and places.")));
    }
    rows.push(lane("Sounds", sounds.map((x) => ["sound", x.label, x.start, x.end])));
    if (S.days) rows.push(lane("Photos", evs.filter((e) => e.photo_ids.length).map((e) => ["photo", `${e.photo_ids.length} photo${e.photo_ids.length > 1 ? "s" : ""}`, e.s, e.e])));
    rows.push(lane("Calls", calls.map((c) => ["call", callLabel(c), c.start, c.end])));
    $("lanes").replaceChildren(...rows);
  }

  // Collapse runs of the same sound label that are < 2 min apart into one block.
  function mergeSounds(list) {
    const out = [];
    for (const x of list.slice().sort((a, b) => a.start - b.start)) {
      const last = out[out.length - 1];
      if (last && last.label === x.label && x.start - last.end < 120e3) last.end = Math.max(last.end, x.end);
      else out.push({ ...x });
    }
    return out;
  }
  const patientName = () => (Object.values(S.people).find((p) => p.is_patient) || {}).name;

  function describe(ev) {
    const p = ev.payload || {};
    switch (ev.stage) {
      case "puck.segment": return `${p.seconds ?? "?"} s · ${(p.sound_tags || []).slice(0, 2).map((t) => t.label).join(", ") || "speech"}`;
      case "puck.processed": return `${(p.utterance_ids || []).length} utterance(s)`;
      case "puck.failed": return p.error || "failed";
      case "puck.health": return `queue ${p.queue_depth} · ${p.ms_per_segment != null ? Math.round(p.ms_per_segment) + " ms/seg" : p.sound_backend}`;
      case "recognize": return (p.faces || []).map((f) => `${f.status === "identified" ? nameOf(f.person_id) || "known" : f.status} · face ${fmt((f.face_top3 || [])[0]?.score)}`).join(", ") || "voice only";
      case "recall.detect": return p.intent ? `${p.intent.intent}${p.intent.query ? ` · “${p.intent.query}”` : ""}` : "";
      case "recall.search": return bestRecall() ? `best ${fmt(bestRecall().score)}` : "no matches";
      case "card.queued": case "card.shown": return (p.card && p.card.title) || p.title || "card";
      case "call.started": return `${p.kind || "call"} started`;
      case "agent.session": return `${MODE_LABEL[p.mode] || p.mode}${p.controlled ? " · test mode" : ""}`;
      case "call.ended": return "call ended";
      case "call.line": return `${speakerLabel(p.speaker)}: ${p.text}`;
      case "day.built": return `${p.events} moments`;
      case "person.enrolled":
        return `${p.name || "unnamed visitor"} · ${p.matched_existing ? "updated" : "new"} · ${p.face_prints_added ?? 0} face, ${p.voice_prints_added ?? 0} voice prints`;
      case "person.created": case "person.updated": return p.name || "unnamed visitor";
      case "app.visits": return `${p.count} visits`;
      case "app.photo": return "photo uploaded";
    }
    return Object.keys(p).slice(0, 3).join(", ");
  }

  function renderEvents() {
    const rows = S.events.slice(-9).reverse().map((ev) => h("div", { class: "event" },
      h("span", { class: "mono-small soft" }, clockSec(tsMs(ev))),
      h("span", { class: "stage" }, ev.stage),
      h("span", { class: "event-detail" }, describe(ev))));
    $("events").replaceChildren(...(rows.length ? rows : [h("span", { class: "small soft" }, "No events yet.")]));
  }

  // ---- render loop ---------------------------------------------------------------------
  let dirty = true;
  function render() {
    renderStatus(); renderGraph(); renderCard();
    if (dirty) {
      if (S.call) { renderCall(); renderHealth(); } else { renderDay(); renderEvents(); }
      dirty = false;
    }
  }
  setInterval(() => { dirty = true; render(); }, 1000);
  function onEvent(ev, live = true) { apply(ev, live); dirty = true; render(); }

  // ---- data sources ---------------------------------------------------------------------
  async function api(path) {
    const r = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) throw new Error(`${path} → ${r.status}`);
    return r.json();
  }
  async function loadPeople() {
    if (DEMO || !token) return;
    try { S.people = Object.fromEntries((await api("/people")).map((p) => [p.id, p])); dirty = true; } catch (e) { console.warn(e); }
  }
  async function loadDay() {
    if (DEMO || !token) return;
    const d = new Date(), iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    try { S.days = await api(`/days/${iso}/events`); dirty = true; } catch (e) { console.warn(e); }
  }

  async function connect() {
    await Promise.all([loadPeople(), loadDay()]);
    try {
      const recent = await (await fetch("/events/recent?limit=1000")).json();
      for (const ev of recent) apply(ev, false);
    } catch (e) { console.warn("backfill failed", e); }
    dirty = true; render();
    const es = new EventSource("/stream");
    es.onopen = () => { S.stream = "open"; render(); };
    es.onerror = () => { S.stream = "reconnecting"; render(); };
    es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch (e) { console.warn("bad event", e); } };
  }

  buildGraph();
  if (DEMO && window.CalypsoDemo) {
    window.CalypsoDemo.start(DEMO, { state: S, emit: onEvent, setPeople: (p) => { S.people = p; }, setDays: (d) => { S.days = d; } });
  } else {
    connect();
  }
  render();
})();

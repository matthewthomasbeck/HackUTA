/* Demo replay for the judge dashboard: `?demo=1` (full loop), `?demo=idle`, `?demo=offline`.
 * Emits the same `{stage, ts, payload}` events the backend puts on /stream, on a timer,
 * so the page can be built, screenshotted and shown without a live puck or call.
 */
window.CalypsoDemo = (() => {
  "use strict";

  const PEOPLE = [
    { id: "p-mary", name: "Mary", is_patient: true, facts: [] },
    { id: "p-sarah", name: "Sarah", relationship: "Daughter", facts: ["Lives in Austin"] },
    { id: "p-mom", name: "Mom", relationship: "Mother", facts: [] },
    { id: "p-tom", name: "Tom", relationship: "Neighbor", facts: [] },
    { id: "p-new", name: null, relationship: null, facts: [] },
  ];
  const TH = { face_match: 0.45, face_margin: 0.08, voice_match: 0.6, voice_margin: 0.08 };

  // The scripted day ends just before "now" (15:50 in demo-clock time), so it reads well at any hour.
  const SHIFT = Date.now() - (() => { const d = new Date(); d.setHours(16, 10, 0, 0); return +d; })();
  const at = (h, m = 0) => { const d = new Date(); d.setHours(h, m, 0, 0); return new Date(+d + SHIFT); };
  const iso = (d) => new Date(d).toISOString();

  function dayEvents() {
    return [
      { id: "d1", start: iso(at(9, 30)), end: iso(at(10, 30)), place: "Kroger", place_confidence: 0.92, people: ["p-mom"], summary: "Grocery shopping with Mom", evidence: ["Visit: Kroger 9:28–10:31", "shopping cart sounds"], photo_ids: [] },
      { id: "d2", start: iso(at(10, 55)), end: iso(at(12, 5)), place: "Blue Bean Café", place_confidence: 0.81, people: ["p-sarah", "p-new"], summary: "Coffee with Sarah", evidence: ["Visit: Blue Bean Café", "café sounds", "2 photos"], photo_ids: ["ph1", "ph2"] },
      { id: "d3", start: iso(at(12, 20)), end: iso(at(13, 25)), place: "Home", place_confidence: 0.95, people: [], summary: "Lunch at home", evidence: ["Visit: Home"], photo_ids: [] },
      { id: "d4", start: iso(at(14, 55)), end: iso(at(15, 50)), place: "somewhere with park sounds", place_confidence: 0.41, people: ["p-tom"], summary: "A walk in the garden", evidence: ["birdsong", "wind"], photo_ids: [] },
    ];
  }

  // Past events, replayed without pulses so the panels have history.
  function seed(mode) {
    const out = [];
    const ev = (d, stage, payload) => out.push({ stage, ts: iso(d), payload });
    const sounds = [[9, 32, "Shopping cart"], [9, 50, "Music"], [10, 10, "Shopping cart"], [11, 0, "Café"], [11, 25, "Café"], [11, 50, "Dishes"], [15, 0, "Bird"], [15, 20, "Bird"]];
    for (const [hh, mm, label] of sounds) {
      const d = at(hh, mm); if (d > Date.now()) continue;
      ev(d, "puck.segment", { segment_uuid: `seed-${hh}-${mm}`, ts_start: iso(d), ts_end: iso(+d + 8 * 60e3), seconds: 6.2, sound_tags: [{ label, score: 0.8 }], has_local_text: false });
    }
    if (at(10, 0) < Date.now()) { ev(at(10, 0), "call.started", { call_id: "c0", kind: "1:1" }); ev(at(10, 22), "call.ended", { call_id: "c0" }); }
    const healthAt = mode === "offline" ? Date.now() - 3 * 60e3 : Date.now() - 4e3;
    ev(healthAt, "puck.health", { ts: iso(healthAt), queue_depth: mode === "offline" ? 37 : 0, sound_backend: "yamnet-tflite", ms_per_segment: 212, time_synced: true });
    ev(Date.now() - 60e3, "day.built", { day: iso(new Date()).slice(0, 10), events: 4 });
    return out.sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
  }

  // One loop of a live call. Offsets in seconds.
  function script(mode) {
    const offline = mode === "offline";
    const seg = (id, tags) => ({ stage: "puck.segment", payload: { segment_uuid: id, ts_start: iso(Date.now()), ts_end: iso(Date.now() + 4e3), seconds: 4.2, sound_tags: tags, has_local_text: false } });
    const health = { stage: "puck.health", payload: { ts: iso(Date.now()), queue_depth: 0, sound_backend: "yamnet-tflite", ms_per_segment: 205 + Math.round(Math.random() * 20), time_synced: true } };
    const face = (key, status, pid, f, v) => ({ stage: "recognize", payload: {
      participant_key: key, call_id: "c1", faces: [{ bbox: { x: 0, y: 0, w: 100, h: 100 }, status, person_id: pid, face_top3: [{ person_id: pid, score: f }] }],
      voice_top3: v == null ? [] : [{ person_id: pid, score: v }], speech_s: 4, voice_only: null, thresholds: TH, notes: [] } });
    const line = (speaker, text) => ({ stage: "call.line", payload: { call_id: "c1", speaker, text } });

    const ambient = offline ? [] : [
      [0.5, health], [1, seg("s-a", [{ label: "Speech", score: 0.9 }, { label: "Kettle", score: 0.4 }])],
      [2.4, { stage: "puck.processed", payload: { segment_uuid: "s-a", utterance_ids: ["u1"] } }],
    ];
    if (mode === "idle") return { steps: ambient.concat([[6, seg("s-b", [{ label: "Speech", score: 0.8 }])], [7.3, { stage: "puck.processed", payload: { segment_uuid: "s-b", utterance_ids: ["u2"] } }]]), length: 10 };

    const call = offline ? [
      [3, { stage: "call.started", payload: { call_id: "c1", kind: "group" } }],
      [4, face("k1", "learning", null, 0.17, 0.24)],
      [5, line("Sarah", "This is my friend Priya from work.")],
      [6, face("k2", "uncertain", null, 0.48, 0.22)],
      [5.6, { stage: "card.queued", payload: { card: { kind: "learning", title: "Getting to know someone new…", lines: ["No name until Calypso⁻¹ is sure"] } } }],
      [6.4, { stage: "card.shown", payload: { card: { kind: "learning", title: "Getting to know someone new…", lines: ["No name until Calypso⁻¹ is sure"] } } }],
      [9, line("Mary", "Hello, dear.")],
      [19, line("Sarah", "Do you remember what we did on Tuesday?")],
      [19.4, { stage: "recall.detect", payload: { last_line: "Do you remember what we did on Tuesday?", intent: { intent: "memory", query: "Tuesday" } } }],
      [19.8, { stage: "recall.search", payload: { threshold: 0.35, top3: [{ label: "Garden", score: 0.21 }, { label: "Kroger", score: 0.14 }, { label: "Pier", score: 0.09 }] } }],
      [34, { stage: "call.ended", payload: { call_id: "c1" } }],
    ] : [
      [3, { stage: "call.started", payload: { call_id: "c1", kind: "group" } }],
      [4, face("k1", "identified", "p-sarah", 0.78, 0.71)],
      [4.6, { stage: "card.queued", payload: { card: { kind: "identity", title: "Sarah, your daughter", lines: ["Lives in Austin", "Her dog is Biscuit"] } } }],
      [5.2, { stage: "card.shown", payload: { card: { kind: "identity", title: "Sarah, your daughter", lines: ["Lives in Austin", "Her dog is Biscuit"] } } }],
      [7, line("Sarah", "Biscuit has been digging in the garden again.")],
      [8, face("k2", "uncertain", null, 0.48, 0.22)],
      [10, line("Mary", "Oh, that silly dog.")],
      [16, line("Sarah", "Mom, do you remember the beach last summer?")],
      [16.4, { stage: "recall.detect", payload: { last_line: "Mom, do you remember the beach last summer?", intent: { intent: "memory", query: "the beach" } } }],
      [16.8, { stage: "recall.search", payload: { threshold: 0.35, top3: [{ label: "Beach", score: 0.62 }, { label: "Pier", score: 0.31 }, { label: "Garden", score: 0.12 }] } }],
      [17.2, { stage: "card.queued", payload: { card: { kind: "memory", title: "The beach trip", lines: ["Last July in Galveston with Sarah and Biscuit"] } } }],
      [17.8, { stage: "card.shown", payload: { card: { kind: "memory", title: "The beach trip", lines: ["Last July in Galveston with Sarah and Biscuit"] } } }],
      [22, health],
      [23, seg("s-c", [{ label: "Speech", score: 0.9 }])],
      [24.3, { stage: "puck.processed", payload: { segment_uuid: "s-c", utterance_ids: ["u3"] } }],
      [28, line("Mary", "We had ice cream on the pier.")],
      [34, { stage: "call.ended", payload: { call_id: "c1" } }],
      [36, { stage: "day.built", payload: { day: iso(new Date()).slice(0, 10), events: 4 } }],
    ];
    return { steps: ambient.concat(call), length: 42 };
  }

  function start(mode, ctx) {
    mode = mode === "offline" || mode === "idle" ? mode : "live";
    ctx.setPeople(Object.fromEntries(PEOPLE.map((p) => [p.id, p])));
    ctx.setDays(dayEvents());
    for (const ev of seed(mode)) ctx.emit(ev, false);
    // Prior latency samples so the sparklines have a shape.
    const L = ctx.state.lat;
    L.card.push(...[1.9, 2.1, 1.7, 2.3, 1.8, 2.0, 1.6, 2.2, 1.9, 1.7, 2.0].map((x) => x * 1000));
    L.seg.push(...[1.5, 1.3, 1.6, 1.2, 1.4, 1.5, 1.3, 1.6, 1.4, 1.2, 1.4].map((x) => x * 1000));
    L.ctrl.push(640);

    const run = () => {
      const { steps, length } = script(mode);
      for (const [t, ev] of steps) setTimeout(() => ctx.emit({ ...ev, ts: iso(Date.now()) }), t * 1000);
      setTimeout(run, length * 1000);
    };
    run();
  }

  return { start };
})();

/*!
 * LeadOps tracking SDK v1. Add one tag to any page:
 *
 *   <script src="https://YOUR-API/sdk/leadops.js" data-site="my-site" async></script>
 *
 * Script tag options:
 *   data-api            API base URL (default: the address the script was loaded from)
 *   data-site           a name for this website (default: the page's hostname)
 *   data-exclude-paths  comma-separated path prefixes to skip, e.g. "/dashboard,/admin"
 *
 * In page code:
 *   LeadOps.track("emi_used", { emi: 52000 })  record a custom event
 *   LeadOps.ids()                                { visitor_id, session_id } for your own API calls
 *   LeadOps.flush()                              send queued events now
 *
 * Privacy: never reads what people type or fill in; it only counts actions and measures timings.
 * Event shapes are documented in docs/CONTRACTS.md.
 */
(function () {
  "use strict";
  if (window.LeadOps && window.LeadOps.version) return; // already loaded on this page

  var VERSION = "1.0.0";
  var SESSION_TIMEOUT_MS = 30 * 60 * 1000; // a new visit starts after 30 minutes without activity
  var FLUSH_INTERVAL_MS = 5000;
  var ACTIVITY_INTERVAL_MS = 10000;
  var MAX_QUEUE = 50;
  var SCROLL_MARKS = [25, 50, 75, 100];

  // ---------------------------------------------------------------- configuration from the script tag

  var script = document.currentScript || document.querySelector('script[src*="leadops.js"]');
  function attr(name) {
    return script ? script.getAttribute(name) : null;
  }
  var apiBase = (attr("data-api") || (script && script.src ? new URL(script.src, location.href).origin : "")).replace(/\/+$/, "");
  var endpoint = apiBase + "/events";
  var site = attr("data-site") || location.hostname || "local";
  var excludedPaths = (attr("data-exclude-paths") || "")
    .split(",")
    .map(function (path) { return path.trim(); })
    .filter(Boolean);

  function isExcluded(path) {
    return excludedPaths.some(function (prefix) { return path.indexOf(prefix) === 0; });
  }

  // ---------------------------------------------------------------- storage (falls back to memory when blocked)

  var memory = {};
  function load(key) {
    var value = null;
    try { value = window.localStorage.getItem(key); } catch (e) { /* storage blocked */ }
    if (value !== null) return value;
    return Object.prototype.hasOwnProperty.call(memory, key) ? memory[key] : null;
  }
  function save(key, value) {
    memory[key] = value;
    try { window.localStorage.setItem(key, value); } catch (e) { /* storage blocked: memory only */ }
  }

  function newId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    var bytes = new Uint8Array(16);
    if (window.crypto && window.crypto.getRandomValues) {
      window.crypto.getRandomValues(bytes);
    } else {
      for (var i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    return Array.prototype.map.call(bytes, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
  }

  // ---------------------------------------------------------------- visitor and session IDs

  var visitorId = load("leadops_vid");
  if (!visitorId) {
    visitorId = newId();
    save("leadops_vid", visitorId);
  }

  function touchSession() {
    var now = Date.now();
    var sessionId = load("leadops_sid");
    var lastActive = Number(load("leadops_sid_at") || 0);
    if (!sessionId || now - lastActive > SESSION_TIMEOUT_MS) sessionId = newId();
    save("leadops_sid", sessionId);
    save("leadops_sid_at", String(now));
    return sessionId;
  }

  // ---------------------------------------------------------------- browser context (sent with every batch)

  var utm = {};
  (function captureUtm() {
    try {
      new URLSearchParams(location.search).forEach(function (value, key) {
        if (key.indexOf("utm_") === 0) utm[key] = value.slice(0, 100);
      });
    } catch (e) { /* very old browser */ }
  })();

  function context() {
    var nav = window.navigator || {};
    var timezone = null;
    try { timezone = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { /* no Intl */ }
    return {
      user_agent: nav.userAgent,
      language: nav.language,
      languages: nav.languages ? nav.languages.length : null,
      timezone: timezone,
      screen: window.screen ? screen.width + "x" + screen.height : null,
      viewport: window.innerWidth + "x" + window.innerHeight,
      pixel_ratio: window.devicePixelRatio || 1,
      touch_points: nav.maxTouchPoints || 0,
      hardware_concurrency: nav.hardwareConcurrency || null,
      webdriver: nav.webdriver === true, // true when Selenium, Playwright or Puppeteer drives the browser
      referrer: document.referrer || null,
      utm: utm
    };
  }

  // ---------------------------------------------------------------- queue and sending

  var queue = [];
  var queueSession = null;
  var flushTimer = null;

  function push(type, props, path) {
    path = path || location.pathname;
    if (isExcluded(path)) return;
    var sessionId = touchSession();
    if (queueSession && sessionId !== queueSession) flush(false); // a new visit started: send the old one's events
    queueSession = sessionId;
    queue.push({
      type: type,
      ts: Date.now(),
      path: path,
      url: location.origin + path, // no query string: it can contain personal details
      title: document.title,
      props: props || {}
    });
    if (queue.length >= MAX_QUEUE) flush(false);
  }

  function scheduleFlush(delayMs) {
    if (flushTimer) return;
    flushTimer = setTimeout(function () {
      flushTimer = null;
      flush(false);
    }, delayMs);
  }

  function flush(pageClosing) {
    if (!queue.length) return;
    var body = JSON.stringify({
      visitor_id: visitorId,
      session_id: queueSession,
      site: site,
      sdk_version: VERSION,
      sent_at: Date.now(),
      context: context(),
      events: queue.splice(0, queue.length)
    });
    // text/plain keeps this a "simple" request: no CORS preflight, and sendBeacon accepts it.
    if (pageClosing && navigator.sendBeacon) {
      try {
        if (navigator.sendBeacon(endpoint, new Blob([body], { type: "text/plain" }))) return;
      } catch (e) { /* fall through to fetch */ }
    }
    try {
      fetch(endpoint, {
        method: "POST",
        body: body,
        headers: { "Content-Type": "text/plain" },
        credentials: "omit",
        keepalive: body.length < 60000
      }).catch(function () { /* offline or API down: drop the batch quietly */ });
    } catch (e) { /* no fetch */ }
  }

  // ---------------------------------------------------------------- page views, time on page, scroll depth

  var page = null;
  var previousPath = null;

  function startPage() {
    page = {
      path: location.pathname,
      visibleMs: 0,
      visibleSince: document.visibilityState === "hidden" ? null : Date.now(),
      maxScroll: 0,
      marks: {}
    };
    push("page_view", { referrer: previousPath || document.referrer || null });
    previousPath = page.path;
    setTimeout(measureScroll, 1000); // after the page has rendered
  }

  function endPage(reason) {
    if (!page) return;
    var visible = page.visibleMs + (page.visibleSince ? Date.now() - page.visibleSince : 0);
    push("page_leave", { duration_ms: visible, max_scroll_pct: page.maxScroll, reason: reason }, page.path);
    page = null;
  }

  function measureScroll() {
    if (!page) return;
    var doc = document.documentElement;
    var scrollable = Math.max(doc.scrollHeight, document.body ? document.body.scrollHeight : 0) - window.innerHeight;
    if (scrollable <= 0) {
      page.maxScroll = 100; // the whole page fits on screen
      return;
    }
    var percent = Math.min(100, Math.round(((window.scrollY || doc.scrollTop) / scrollable) * 100));
    if (percent > page.maxScroll) page.maxScroll = percent;
    SCROLL_MARKS.forEach(function (mark) {
      if (percent >= mark && !page.marks[mark]) {
        page.marks[mark] = true;
        push("scroll_depth", { percent: mark });
      }
    });
  }

  // Single-page apps (React Router and others) change pages through the History API.
  function onRouteChange() {
    if (page && location.pathname === page.path) return; // only path changes count as a new page
    flushActivity();
    endPage("navigate");
    startPage();
  }
  ["pushState", "replaceState"].forEach(function (method) {
    var original = history[method];
    if (typeof original !== "function") return;
    history[method] = function () {
      var result = original.apply(this, arguments);
      try { onRouteChange(); } catch (e) { /* never break the site's navigation */ }
      return result;
    };
  });
  window.addEventListener("popstate", onRouteChange);

  document.addEventListener("visibilitychange", function () {
    if (!page) return;
    if (document.visibilityState === "hidden") {
      if (page.visibleSince) {
        page.visibleMs += Date.now() - page.visibleSince;
        page.visibleSince = null;
      }
      flushActivity();
      flush(true); // the tab may never come back
    } else {
      page.visibleSince = Date.now();
    }
  });
  window.addEventListener("pagehide", function () {
    flushActivity();
    endPage("close");
    flush(true);
  });

  // ---------------------------------------------------------------- activity counts (human vs bot signals)

  var activity;
  var lastMouse = null;
  function resetActivity() {
    activity = { since: Date.now(), mouse_moves: 0, mouse_distance: 0, clicks: 0, touches: 0, keys: 0, scrolls: 0 };
  }
  resetActivity();

  function flushActivity() {
    var total = activity.mouse_moves + activity.clicks + activity.touches + activity.keys + activity.scrolls;
    if (total > 0) {
      push("activity", {
        interval_ms: Date.now() - activity.since,
        mouse_moves: activity.mouse_moves,
        mouse_distance: Math.round(activity.mouse_distance),
        clicks: activity.clicks,
        touches: activity.touches,
        keys: activity.keys, // how many keys were pressed, never which ones
        scrolls: activity.scrolls
      });
    }
    resetActivity();
  }

  document.addEventListener("mousemove", function (event) {
    activity.mouse_moves++;
    if (lastMouse) activity.mouse_distance += Math.abs(event.clientX - lastMouse[0]) + Math.abs(event.clientY - lastMouse[1]);
    lastMouse = [event.clientX, event.clientY];
  }, { passive: true });
  document.addEventListener("touchstart", function () { activity.touches++; }, { passive: true });
  document.addEventListener("keydown", function () { activity.keys++; }, true);

  var scrollQueued = false;
  window.addEventListener("scroll", function () {
    activity.scrolls++;
    if (scrollQueued) return;
    scrollQueued = true;
    setTimeout(function () {
      scrollQueued = false;
      measureScroll();
    }, 250);
  }, { passive: true });

  document.addEventListener("click", function (event) {
    activity.clicks++;
    var target = event.target && event.target.closest
      ? event.target.closest("a, button, [data-lo-track], [role=button], input[type=submit], input[type=button]")
      : null;
    if (!target) return; // every click is counted above; only clicks on controls become events
    var props = { tag: target.tagName.toLowerCase(), trusted: event.isTrusted }; // isTrusted is false for script clicks
    var label = target.getAttribute("data-lo-track");
    if (label) props.track = label;
    var text = (target.innerText || target.value || "").replace(/\s+/g, " ").trim().slice(0, 60);
    if (text) props.text = text;
    if (target.id) props.id = target.id.slice(0, 60);
    var href = target.getAttribute("href");
    if (href) props.href = href.slice(0, 200);
    push("click", props);
  }, true);

  // ---------------------------------------------------------------- public API

  function track(name, props) {
    if (typeof name !== "string" || !name) return;
    push(name, props && typeof props === "object" ? props : {});
    scheduleFlush(500); // custom events are rare and important: send them soon
  }

  window.LeadOps = {
    version: VERSION,
    track: track,
    ids: function () { return { visitor_id: visitorId, session_id: touchSession() }; },
    flush: function () { flushActivity(); flush(false); }
  };

  // Calls a site made before this script finished loading: window.__leadopsQueue.push(["track", name, props])
  var early = window.__leadopsQueue;
  window.__leadopsQueue = { push: function (call) { if (call && call[0] === "track") track(call[1], call[2]); } };
  if (early && early.length) early.forEach(window.__leadopsQueue.push);

  setInterval(flushActivity, ACTIVITY_INTERVAL_MS);
  setInterval(function () { flush(false); }, FLUSH_INTERVAL_MS);
  startPage();
  scheduleFlush(0); // the first page view goes out at once, so the visitor shows up live on the dashboard
})();

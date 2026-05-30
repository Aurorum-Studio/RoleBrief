// RoleBrief AI - live pipeline progress.
// Progressive enhancement: if anything here fails, the form/link still works
// as a normal request because we only preventDefault after a successful start.
(function () {
  "use strict";

  // Ordered pipeline stages used to drive the progress bar fill.
  var STAGE_ORDER = ["start", "collect_web", "collect_box", "briefs", "package", "box_sync", "complete"];

  function $(id) {
    return document.getElementById(id);
  }

  function setStepState(stage, state) {
    var step = document.querySelector('#progress-steps li[data-step="' + stage + '"]');
    if (!step) return;
    step.classList.remove("active", "done");
    if (state) step.classList.add(state);
  }

  function fillForStage(stage) {
    var idx = STAGE_ORDER.indexOf(stage);
    if (idx < 0) return null;
    return Math.round((idx / (STAGE_ORDER.length - 1)) * 100);
  }

  function logLine(text) {
    var log = $("progress-log");
    if (!log) return;
    var line = document.createElement("div");
    line.className = "log-line";
    line.textContent = text;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
  }

  function openOverlay() {
    var overlay = $("progress-overlay");
    if (!overlay) return;
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("progress-open");
  }

  function showError(message) {
    var err = $("progress-error");
    if (err) {
      err.textContent = message;
      err.hidden = false;
    }
    var spinner = document.querySelector(".progress-modal .spinner");
    if (spinner) spinner.classList.add("failed");
  }

  // Apply a single progress event to the UI.
  function applyEvent(evt) {
    if (!evt || !evt.stage) return;

    if (evt.message) {
      var current = $("progress-current");
      if (current && evt.status !== "role_done") current.textContent = evt.message;
      logLine(evt.message);
    }

    if (evt.stage === "briefs") {
      // Sub-counter like "(2/6)" while roles are generated one by one.
      if (evt.total) {
        var sub = $("briefs-sub");
        if (sub && evt.index) sub.textContent = "(" + evt.index + "/" + evt.total + ")";
      }
      if (evt.status === "active" || evt.status === "role_active") {
        setStepState("briefs", "active");
      } else if (evt.status === "done") {
        setStepState("briefs", "done");
      }
      var fillB = fillForStage("briefs");
      if (fillB !== null) growBar(fillB, evt.index, evt.total);
      return;
    }

    if (evt.status === "active") {
      setStepState(evt.stage, "active");
    } else if (evt.status === "done") {
      setStepState(evt.stage, "done");
    }

    var fill = fillForStage(evt.stage);
    if (fill !== null) growBar(fill);
  }

  var lastFill = 0;
  function growBar(target, index, total) {
    var bar = $("progress-bar-fill");
    if (!bar) return;
    var value = target;
    // Within the "briefs" stage, advance proportionally per role so the bar
    // moves smoothly while Gemini is queried for each audience.
    if (typeof index === "number" && typeof total === "number" && total > 0) {
      var briefsStart = fillForStage("briefs");
      var packageStart = fillForStage("package");
      value = briefsStart + ((packageStart - briefsStart) * (index / total));
    }
    if (value < lastFill) return;
    lastFill = value;
    bar.style.width = value + "%";
  }

  function finish(url) {
    var bar = $("progress-bar-fill");
    if (bar) bar.style.width = "100%";
    setStepState("box_sync", "done");
    window.setTimeout(function () {
      window.location.href = url;
    }, 550);
  }

  // Stream NDJSON progress from the server and drive the overlay.
  function startStream(url, formData) {
    openOverlay();
    var fetchOpts = { method: "POST", headers: { "Accept": "application/x-ndjson" } };
    if (formData) fetchOpts.body = formData;

    fetch(url, fetchOpts)
      .then(function (response) {
        if (!response.ok || !response.body) {
          throw new Error("Stream request failed (" + response.status + ")");
        }
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        function pump() {
          return reader.read().then(function (result) {
            if (result.done) {
              flush(buffer);
              return;
            }
            buffer += decoder.decode(result.value, { stream: true });
            var lines = buffer.split("\n");
            buffer = lines.pop();
            lines.forEach(handleLine);
            return pump();
          });
        }
        return pump();
      })
      .catch(function (err) {
        showError("Live progress unavailable: " + err.message + ". Falling back to a standard request...");
        window.setTimeout(function () { fallback(url, formData); }, 1200);
      });
  }

  function handleLine(line) {
    var text = (line || "").trim();
    if (!text) return;
    var evt;
    try {
      evt = JSON.parse(text);
    } catch (e) {
      return;
    }
    if (evt.stage === "complete" && (evt.result_url || evt.run_id)) {
      applyEvent({ stage: "complete", status: "done", message: evt.message });
      finish(evt.result_url || ("/run/" + evt.run_id));
      return;
    }
    if (evt.stage === "error" || evt.status === "error") {
      showError(evt.message || "The run failed. Please try again.");
      return;
    }
    applyEvent(evt);
  }

  function flush(buffer) {
    if (buffer && buffer.trim()) handleLine(buffer);
  }

  // No-stream fallback: submit the original form / navigate to the link target.
  function fallback(streamUrl, formData) {
    var form = document.querySelector("[data-analyze-form]");
    if (formData && form) {
      form.removeAttribute("data-analyze-form");
      form.submit();
      return;
    }
    // Demo link fallback navigates to the standard /demo route.
    window.location.href = "/demo";
  }

  function init() {
    var form = document.querySelector("[data-analyze-form]");
    if (form && window.fetch && window.ReadableStream) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var streamUrl = form.getAttribute("data-stream-url");
        startStream(streamUrl, new FormData(form));
      });
    }

    var script = document.querySelector('script[data-demo-stream-url]');
    var demoStreamUrl = script ? script.getAttribute("data-demo-stream-url") : null;
    var demoLink = document.querySelector("[data-demo-stream]");
    if (demoLink && demoStreamUrl && window.fetch && window.ReadableStream) {
      demoLink.addEventListener("click", function (e) {
        e.preventDefault();
        startStream(demoStreamUrl, null);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

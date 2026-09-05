function getActivePanel() {
  return document.querySelector(".fenix-tab-panel:not(.hidden)");
}

function getActiveTabName() {
  const tab = document.querySelector(".fenix-tab.active");
  return (tab && tab.dataset.tab) || "links";
}

function getActionLabels() {
  const tab = getActiveTabName();
  if (tab === "convert") {
    return {
      start: "Iniciar conversión",
      stop: "Detener conversión",
      starting: "Iniciando…",
      cancelling: "Cancelando…",
      emptyHint: "Indicá la ruta del archivo a convertir.",
      toastDone: "Conversión completada",
      toastFail: "Conversión fallida",
      toastCancel: "Conversión cancelada",
      toastPartial: "Conversión parcial",
    };
  }
  if (tab === "export") {
    return {
      start: "Exportar lista",
      stop: "Detener exportación",
      starting: "Exportando…",
      cancelling: "Cancelando…",
      emptyHint: "Pegá el link de la playlist.",
      toastDone: "Lista exportada",
      toastFail: "Exportación fallida",
      toastCancel: "Exportación cancelada",
      toastPartial: "Exportación parcial",
    };
  }
  return {
    start: "Iniciar descarga",
    stop: "Detener descarga",
    starting: "Iniciando…",
    cancelling: "Cancelando…",
    emptyHint: "Pegá un link, un nombre o una ruta antes de iniciar.",
    toastDone: "Descarga completada",
    toastFail: "Descarga fallida",
    toastCancel: "Descarga cancelada",
    toastPartial: "Descarga parcial",
  };
}

function getActiveLinksValue() {
  const panel = getActivePanel();
  if (!panel) return "";
  const source =
    panel.querySelector("[data-role='links-source']") ||
    panel.querySelector("textarea") ||
    panel.querySelector("#links-textarea-convert") ||
    panel.querySelector("input[type='text']");
  return source ? String(source.value || "").trim() : "";
}

function getActiveTipoValue() {
  const panel = getActivePanel();
  if (!panel) return "song";
  const tipo = panel.querySelector('input[name="tipo"]');
  return tipo ? String(tipo.value || "").trim() : "song";
}

function updateFormInputs() {
  document.querySelectorAll(".fenix-tab-panel").forEach((panel) => {
    const isHidden = panel.classList.contains("hidden");
    panel.querySelectorAll("input, textarea, select").forEach((el) => {
      el.disabled = isHidden;
    });
  });
  const hiddenLinks = document.getElementById("hidden-links");
  if (hiddenLinks) hiddenLinks.disabled = false;
}

function prepareForm() {
  updateFormInputs();
  const value = getActiveLinksValue();
  const hiddenLinks = document.getElementById("hidden-links");
  if (hiddenLinks) {
    hiddenLinks.disabled = false;
    hiddenLinks.value = value;
  }
  return value;
}

function switchTab(tab) {
  document.querySelectorAll(".fenix-tab-panel").forEach((p) => p.classList.add("hidden"));
  const panel = document.getElementById("panel-" + tab);
  if (panel) panel.classList.remove("hidden");

  document.querySelectorAll(".fenix-tab").forEach((t) => t.classList.remove("active"));
  const tabBtn = document.querySelector(`.fenix-tab[data-tab="${tab}"]`);
  if (tabBtn) tabBtn.classList.add("active");

  const hiddenLinks = document.getElementById("hidden-links");
  if (hiddenLinks) hiddenLinks.value = "";

  updateFormInputs();

  const btn = getSubmitBtn();
  const labels = getActionLabels();
  if (btn) {
    btn.dataset.labelStart = labels.start;
    if (!btn.dataset.mode || btn.dataset.mode === "start") {
      setBtnLabel(btn, labels.start, "start");
    }
  }
}

function setTipo(panel, tipo, btn) {
  const tipoEl = document.getElementById("tipo-" + panel);
  if (tipoEl) tipoEl.value = tipo;
  const container = btn.closest(".flex");
  if (!container) return;
  container.querySelectorAll(".tipo-btn").forEach((b) => {
    b.className = "tipo-btn fenix-btn-outline";
  });
  btn.className = "tipo-btn fenix-btn-primary";
}

function toggleConsole() {
  const content = document.getElementById("console-content");
  const btn = document.getElementById("console-toggle-btn");
  if (!content || !btn) return;
  if (content.classList.contains("hidden")) {
    content.classList.remove("hidden");
    btn.textContent = "Ocultar";
  } else {
    content.classList.add("hidden");
    btn.textContent = "Mostrar";
  }
}

window.restoreConsolePlaceholder = function () {
  const content = document.getElementById("console-content");
  const emptyMsg = document.getElementById("console-empty-msg");
  if (!content) return;
  const tab = getActiveTabName();
  let hint = "Los logs aparecerán aquí cuando inicies una descarga";
  if (tab === "convert") {
    hint = "Los logs aparecerán aquí cuando inicies una conversión";
  } else if (tab === "export") {
    hint = "Los logs aparecerán aquí cuando exportes una playlist";
  }
  content.innerHTML = `
    <div id="console-placeholder" class="fenix-console-log flex items-center justify-center text-center"
         style="min-height: 100px; color: var(--text-muted);">
      <span class="font-normal leading-relaxed">
        ${hint}
      </span>
    </div>`;
  if (emptyMsg) emptyMsg.textContent = "Esperando acción...";
  content.classList.remove("hidden");
  const btn = document.getElementById("console-toggle-btn");
  if (btn) btn.textContent = "Ocultar";
};

window.copyFailedLinks = function (btn) {
  const box = document.getElementById("failed-links-box");
  if (!box) return;
  const text = box.dataset.links || box.textContent;
  navigator.clipboard.writeText(text).then(() => {
    const original = btn.textContent;
    btn.textContent = "¡Copiado!";
    setTimeout(() => {
      btn.textContent = original;
    }, 1800);
  }).catch(() => {
    const range = document.createRange();
    range.selectNodeContents(box);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    try {
      document.execCommand("copy");
    } catch (e) {}
    sel.removeAllRanges();
    const original = btn.textContent;
    btn.textContent = "¡Copiado!";
    setTimeout(() => {
      btn.textContent = original;
    }, 1800);
  });
};

window.downloadTextFile = function (filename, text) {
  const name = (filename || "playlist.txt").trim() || "playlist.txt";
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name.toLowerCase().endsWith(".txt") ? name : name + ".txt";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(function () {
    URL.revokeObjectURL(url);
  }, 2000);
};

window.scrollToConsole = function () {
  const consoleSlot = document.getElementById("console-slot");
  if (consoleSlot) {
    setTimeout(() => {
      consoleSlot.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 300);
  }
};

function __applyIcon() {
  const theme = document.documentElement.getAttribute("data-theme");
  const sun = document.getElementById("theme-icon-sun");
  const moon = document.getElementById("theme-icon-moon");
  if (sun) sun.classList.toggle("hidden", theme === "dark");
  if (moon) moon.classList.toggle("hidden", theme !== "dark");
}

window.__toggleTheme = function () {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  __applyIcon();
};

window.__activeJobId = null;
window.__jobBusy = false;
window.__activeJobTab = null;

function getSubmitBtn() {
  return (
    document.getElementById("download-submit-btn") ||
    document.querySelector('#download-form button[type="submit"]')
  );
}

function setBtnLabel(btn, text, mode) {
  const label = btn.querySelector(".btn-label");
  if (label) {
    label.textContent = text;
  } else {
    btn.textContent = text;
    return;
  }
  const iconStart = btn.querySelector(".btn-icon-start");
  const iconStop = btn.querySelector(".btn-icon-stop");
  const isStop = mode === "stop" || mode === "cancelling";
  if (iconStart) iconStart.classList.toggle("hidden", isStop);
  if (iconStop) iconStop.classList.toggle("hidden", !isStop);
}

function labelsForJob() {
  if (window.__activeJobTab === "convert") {
    return {
      start: "Iniciar conversión",
      stop: "Detener conversión",
      starting: "Iniciando…",
      cancelling: "Cancelando…",
      toastDone: "Conversión completada",
      toastFail: "Conversión fallida",
      toastCancel: "Conversión cancelada",
      toastPartial: "Conversión parcial",
    };
  }
  if (window.__activeJobTab === "export") {
    return {
      start: "Exportar lista",
      stop: "Detener exportación",
      starting: "Exportando…",
      cancelling: "Cancelando…",
      toastDone: "Lista exportada",
      toastFail: "Exportación fallida",
      toastCancel: "Exportación cancelada",
      toastPartial: "Exportación parcial",
    };
  }
  if (window.__activeJobTab) {
    return {
      start: "Iniciar descarga",
      stop: "Detener descarga",
      starting: "Iniciando…",
      cancelling: "Cancelando…",
      toastDone: "Descarga completada",
      toastFail: "Descarga fallida",
      toastCancel: "Descarga cancelada",
      toastPartial: "Descarga parcial",
    };
  }
  return getActionLabels();
}

function setSubmitIdle() {
  const btn = getSubmitBtn();
  if (!btn) return;
  const labels = getActionLabels();
  btn.disabled = false;
  btn.dataset.mode = "start";
  btn.dataset.labelStart = labels.start;
  setBtnLabel(btn, labels.start, "start");
  btn.classList.remove("fenix-btn-danger");
  btn.classList.add("fenix-btn-primary");
}

function setSubmitBusy(jobId) {
  window.__activeJobId = jobId || window.__activeJobId;
  window.__jobBusy = true;
  const btn = getSubmitBtn();
  if (!btn) return;
  const labels = labelsForJob();
  btn.disabled = false;
  btn.dataset.mode = "stop";
  btn.dataset.labelStart = labels.start;
  setBtnLabel(btn, labels.stop, "stop");
  btn.classList.remove("fenix-btn-danger");
  btn.classList.add("fenix-btn-primary");
}

function setSubmitCancelling() {
  const btn = getSubmitBtn();
  if (!btn) return;
  const labels = labelsForJob();
  btn.disabled = true;
  btn.dataset.mode = "cancelling";
  setBtnLabel(btn, labels.cancelling, "cancelling");
  btn.classList.remove("fenix-btn-danger");
  btn.classList.add("fenix-btn-primary");
}

window.onJobStarted = function (jobId) {
  window.__activeJobId = jobId;
  window.__jobBusy = true;
  if (!window.__activeJobTab) {
    window.__activeJobTab = getActiveTabName();
  }
  setSubmitBusy(jobId);
};

window.onJobFinished = function (jobId) {
  if (jobId && window.__activeJobId && jobId !== window.__activeJobId) return;
  window.__activeJobId = null;
  window.__jobBusy = false;
  window.__activeJobTab = null;
  setSubmitIdle();
};

window.cancelActiveJob = function () {
  const jobId = window.__activeJobId;
  if (!jobId) {
    setSubmitIdle();
    return;
  }
  setSubmitCancelling();
  fetch("/cancel/" + encodeURIComponent(jobId), { method: "POST" })
    .then(function (r) {
      return r.json().catch(function () {
        return { ok: false };
      });
    })
    .then(function (data) {
      if (!data || !data.ok) {
        window.onJobFinished(jobId);
      }
    })
    .catch(function () {
      window.onJobFinished(jobId);
    });
};

function resolveDownloadForm(elt) {
  if (!elt) return null;
  if (elt.id === "download-form") return elt;
  return elt.closest ? elt.closest("form") : null;
}

document.addEventListener("DOMContentLoaded", function () {
  updateFormInputs();
  __applyIcon();
  setSubmitIdle();

  ["links", "playlist"].forEach((p) => {
    const container = document.querySelector(`#panel-${p} .flex.flex-wrap`);
    if (container) {
      const first = container.querySelector(".tipo-btn");
      if (first) {
        first.className = "tipo-btn fenix-btn-primary";
        const tipoEl = document.getElementById("tipo-" + p);
        if (tipoEl) tipoEl.value = first.dataset.tipo;
      }
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      ["about-modal", "help-modal"].forEach((id) => {
        const m = document.getElementById(id);
        if (m) m.classList.add("hidden");
      });
    }
  });

  ["about-modal", "help-modal"].forEach((id) => {
    const m = document.getElementById(id);
    if (m) {
      m.addEventListener("click", function (e) {
        if (e.target === this) this.classList.add("hidden");
      });
    }
  });

  const form = document.getElementById("download-form");
  if (form) {
    form.addEventListener(
      "click",
      function (e) {
        const btn = e.target.closest(
          "button[type='submit'], #download-submit-btn"
        );
        if (!btn || !form.contains(btn)) return;
        if (btn.dataset.mode === "stop" || btn.dataset.mode === "cancelling") {
          e.preventDefault();
          e.stopPropagation();
          window.cancelActiveJob();
        }
      },
      true
    );
  }
});

document.addEventListener("htmx:beforeRequest", function (evt) {
  const form = resolveDownloadForm(evt.detail.elt);
  if (!form || form.id !== "download-form") return;

  if (window.__jobBusy && window.__activeJobId) {
    evt.preventDefault();
    return;
  }

  const links = prepareForm();
  const labels = getActionLabels();
  if (!links) {
    evt.preventDefault();
    window.__jobBusy = false;
    setSubmitIdle();
    if (window.showToast) {
      window.showToast({
        variant: "error",
        message: "Falta el contenido",
        description: labels.emptyHint,
      });
    }
    return;
  }

  window.__activeJobTab = getActiveTabName();

  const btn = getSubmitBtn();
  if (btn) {
    btn.dataset.labelStart = labels.start;
    btn.disabled = true;
    btn.dataset.mode = "starting";
    setBtnLabel(btn, labels.starting, "start");
  }
});

document.addEventListener("htmx:configRequest", function (evt) {
  const form = resolveDownloadForm(evt.detail.elt);
  if (!form || form.id !== "download-form") return;

  updateFormInputs();

  const links = getActiveLinksValue();
  const tipo = getActiveTipoValue();

  if (!evt.detail.parameters) evt.detail.parameters = {};
  evt.detail.parameters["links"] = links;
  evt.detail.parameters["tipo"] = tipo;

  const hiddenLinks = document.getElementById("hidden-links");
  if (hiddenLinks) {
    hiddenLinks.disabled = false;
    hiddenLinks.value = links;
  }
});

document.addEventListener("htmx:afterSwap", function (evt) {
  const target = evt.detail && evt.detail.target;
  if (!target || target.id !== "console-content") return;
  setTimeout(function () {
    if (!window.__activeJobId) {
      window.__jobBusy = false;
      window.__activeJobTab = null;
      setSubmitIdle();
    }
  }, 0);
});

document.addEventListener("htmx:afterRequest", function (evt) {
  const form = resolveDownloadForm(evt.detail.elt);
  if (!form || form.id !== "download-form") return;
  setTimeout(function () {
    if (!window.__activeJobId) {
      window.__jobBusy = false;
      window.__activeJobTab = null;
      setSubmitIdle();
    }
  }, 50);
});

document.addEventListener("htmx:responseError", function () {
  if (!window.__activeJobId) {
    window.__jobBusy = false;
    window.__activeJobTab = null;
    setSubmitIdle();
  }
});

function playCompletionSound() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    const playTone = (freq, start, duration) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      osc.connect(gain);
      gain.connect(ctx.destination);
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(0.2, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
      osc.start(start);
      osc.stop(start + duration);
    };
    const now = ctx.currentTime;
    playTone(880, now, 0.18);
    playTone(1318.5, now + 0.16, 0.28);
  } catch (err) {
    console.warn("No se pudo reproducir el sonido:", err);
  }
}

function dismissToast(id) {
  const el = document.getElementById("toast-" + id);
  if (el) el.remove();
}

window.showToast = function (opts) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const variant = opts.variant || "info";
  const id = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
  const duration = opts.duration != null ? opts.duration : 6000;
  const icons = {
    success: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
    error: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    info: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  };
  const toast = document.createElement("div");
  toast.id = "toast-" + id;
  toast.className = "toast toast-" + variant;
  toast.setAttribute("role", "status");
  toast.innerHTML = `
${icons[variant] || icons.info}
    <div class="toast-body">
      <p class="toast-title"></p>
${opts.description ? `<p class="toast-desc"></p>` : ""}
    </div>
    <button type="button" class="toast-close" aria-label="Cerrar">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
`;
  toast.querySelector(".toast-title").textContent = opts.message || "";
  const descEl = toast.querySelector(".toast-desc");
  if (descEl && opts.description) descEl.textContent = opts.description;
  toast.addEventListener("click", () => dismissToast(id));
  toast.querySelector(".toast-close").addEventListener("click", (e) => {
    e.stopPropagation();
    dismissToast(id);
  });
  container.appendChild(toast);
  if (duration > 0) setTimeout(() => dismissToast(id), duration);
  try {
    if (document.hidden && "Notification" in window) {
      if (Notification.permission === "granted") {
        new Notification(opts.message || "Video Downloader", {
          body: opts.description || "",
          silent: true,
        });
      } else if (Notification.permission === "default") {
        Notification.requestPermission();
      }
    }
  } catch (_) {}
};

window.notifyJobFinished = function (data) {
  const success = Number(data.success || 0);
  const total = Number(data.total || 0);
  const failed = Number(
    data.failed != null ? data.failed : Math.max(0, total - success)
  );
  const cancelled = !!data.cancelled;
  const labels = labelsForJob();
  playCompletionSound();

  if (cancelled) {
    window.showToast({
      variant: "info",
      message: labels.toastCancel,
      description:
        success > 0
          ? `${success} archivo(s) ya estaban listos.`
          : "Se detuvo el job actual.",
    });
    return;
  }
  if (total === 0) {
    window.showToast({
      variant: "info",
      message: "Sin elementos",
      description: "No había nada para procesar.",
    });
    return;
  }
  if (success === total) {
    const isExport = window.__activeJobTab === "export";
    window.showToast({
      variant: "success",
      message: labels.toastDone,
      description: isExport
        ? total === 1
          ? "1 link en el .txt."
          : `${success} links en el .txt.`
        : total === 1
          ? "1 archivo listo."
          : `${success}/${total} archivos listos.`,
    });
  } else if (success === 0) {
    window.showToast({
      variant: "error",
      message: labels.toastFail,
      description:
        total === 1
          ? "No se pudo completar."
          : `0/${total} — revisá los errores.`,
    });
  } else {
    window.showToast({
      variant: "info",
      message: labels.toastPartial,
      description: `${success}/${total} OK · ${failed} fallaron.`,
    });
  }
};
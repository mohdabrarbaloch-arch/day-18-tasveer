/* ==========================================================================
   Tasveer — frontend
   Vanilla JS, no build step. Talks to the FastAPI backend over /api.
   ========================================================================== */

(() => {
  "use strict";

  // ── state ───────────────────────────────────────────────────────────────
  const state = {
    token: localStorage.getItem("tasveer_token") || null,
    user: null,
    styles: [],
    ratios: [],
    style: "cinematic",
    ratio: "1:1",
    authMode: "login",
    galleryPage: 1,
    galleryStyle: null,
    lastGeneration: null,
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // ── tiny helpers ────────────────────────────────────────────────────────
  function toast(message, isError = false) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.toggle("is-error", isError);
    el.hidden = false;
    requestAnimationFrame(() => el.classList.add("is-visible"));
    clearTimeout(toast._t);
    toast._t = setTimeout(() => {
      el.classList.remove("is-visible");
      setTimeout(() => { el.hidden = true; }, 300);
    }, 3200);
  }

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    if (state.token) headers["Authorization"] = `Bearer ${state.token}`;

    const res = await fetch(path, { ...options, headers });

    if (res.status === 204) return null;

    let data = null;
    const text = await res.text();
    if (text) {
      try { data = JSON.parse(text); } catch { data = { detail: text }; }
    }

    if (!res.ok) {
      const detail = data && data.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail) && detail[0] && detail[0].msg
            ? detail[0].msg
            : `Request failed (${res.status})`;
      const err = new Error(message);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  // ── auth ────────────────────────────────────────────────────────────────
  function setSession(token, user) {
    state.token = token;
    state.user = user;
    localStorage.setItem("tasveer_token", token);
    renderAuth();
  }

  function clearSession() {
    state.token = null;
    state.user = null;
    localStorage.removeItem("tasveer_token");
    renderAuth();
    $("#historySection").hidden = true;
  }

  function renderAuth() {
    const signedIn = Boolean(state.user);
    $("#authBtn").hidden = signedIn;
    $("#signupBtn").hidden = signedIn;
    $("#avatar").hidden = !signedIn;
    $("#creditsPill").hidden = !signedIn;

    if (signedIn) {
      $("#avatarInitial").textContent =
        (state.user.display_name || "A").trim().charAt(0).toUpperCase();
      $("#creditsValue").textContent = state.user.credits;
    }
  }

  async function restoreSession() {
    if (!state.token) return;
    try {
      const user = await api("/api/auth/me");
      state.user = user;
      renderAuth();
      loadHistory();
    } catch {
      clearSession();
    }
  }

  function openAuth(mode) {
    state.authMode = mode;
    const isLogin = mode === "login";
    $("#authTitle").textContent = isLogin ? "Sign in" : "Create an account";
    $("#authSub").textContent = isLogin
      ? "Welcome back."
      : "60 free credits, no card needed.";
    $("#nameField").hidden = isLogin;
    $("#authSubmit").textContent = isLogin ? "Sign in" : "Create account";
    $("#authSwitchText").textContent = isLogin ? "New here?" : "Already have an account?";
    $("#authSwitch").textContent = isLogin ? "Create an account" : "Sign in";
    $("#authError").hidden = true;
    $("#authForm").reset();
    $("#authModal").hidden = false;
    setTimeout(() => $("#authEmail").focus(), 60);
  }

  function closeAuth() { $("#authModal").hidden = true; }

  async function submitAuth(event) {
    event.preventDefault();
    const errEl = $("#authError");
    errEl.hidden = true;

    const email = $("#authEmail").value.trim();
    const password = $("#authPassword").value;
    const name = $("#authName").value.trim();

    const btn = $("#authSubmit");
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "Please wait…";

    try {
      const path = state.authMode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body =
        state.authMode === "login"
          ? { email, password }
          : { email, password, display_name: name || email.split("@")[0] };

      const data = await api(path, { method: "POST", body: JSON.stringify(body) });
      setSession(data.access_token, data.user);
      closeAuth();
      toast(`Welcome, ${data.user.display_name}`);
      loadHistory();
    } catch (err) {
      errEl.textContent = err.message;
      errEl.hidden = false;
    } finally {
      btn.disabled = false;
      btn.textContent = original;
    }
  }

  // ── styles & ratios ─────────────────────────────────────────────────────
  async function loadMeta() {
    try {
      const [styles, ratios] = await Promise.all([
        api("/api/styles"),
        api("/api/aspect-ratios"),
      ]);
      state.styles = styles;
      state.ratios = ratios.ratios;
      renderStyleChips();
      renderRatioChips();
      renderGalleryFilters();
    } catch {
      toast("Could not load styles", true);
    }
  }

  function renderStyleChips() {
    const wrap = $("#styleChips");
    wrap.innerHTML = "";
    state.styles.forEach((s) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip" + (s.key === state.style ? " is-active" : "");
      btn.dataset.style = s.key;

      const dot = document.createElement("span");
      dot.className = "chip__dot";
      dot.style.background = s.palette[2] || s.palette[0];

      btn.appendChild(dot);
      btn.appendChild(document.createTextNode(s.label));
      btn.addEventListener("click", () => {
        state.style = s.key;
        renderStyleChips();
      });
      wrap.appendChild(btn);
    });
  }

  function renderRatioChips() {
    const wrap = $("#ratioChips");
    wrap.innerHTML = "";
    state.ratios.forEach((r) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip" + (r.key === state.ratio ? " is-active" : "");
      btn.textContent = r.key;
      btn.title = `${r.width} × ${r.height}`;
      btn.addEventListener("click", () => {
        state.ratio = r.key;
        renderRatioChips();
      });
      wrap.appendChild(btn);
    });
  }

  function renderGalleryFilters() {
    const wrap = $("#galleryFilters");
    wrap.innerHTML = "";

    const all = document.createElement("button");
    all.type = "button";
    all.className = "chip" + (state.galleryStyle === null ? " is-active" : "");
    all.textContent = "All";
    all.addEventListener("click", () => {
      state.galleryStyle = null;
      state.galleryPage = 1;
      renderGalleryFilters();
      loadGallery(true);
    });
    wrap.appendChild(all);

    state.styles.forEach((s) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip" + (state.galleryStyle === s.key ? " is-active" : "");
      btn.textContent = s.label;
      btn.addEventListener("click", () => {
        state.galleryStyle = s.key;
        state.galleryPage = 1;
        renderGalleryFilters();
        loadGallery(true);
      });
      wrap.appendChild(btn);
    });
  }

  // ── generation ──────────────────────────────────────────────────────────
  function showSkeletons(count) {
    const grid = $("#imageGrid");
    grid.innerHTML = "";
    for (let i = 0; i < count; i++) {
      const sk = document.createElement("div");
      sk.className = "skeleton";
      grid.appendChild(sk);
    }
    $("#emptyState").hidden = true;
    $("#result").hidden = false;
  }

  async function generate(event) {
    event.preventDefault();

    if (!state.user) {
      openAuth("login");
      toast("Sign in to generate");
      return;
    }

    const prompt = $("#prompt").value.trim();
    if (prompt.length < 3) {
      toast("Write a slightly longer prompt", true);
      return;
    }

    const seedRaw = $("#seed").value.trim();
    const payload = {
      prompt,
      negative_prompt: $("#negative").value.trim(),
      style: state.style,
      aspect_ratio: state.ratio,
      count: 4,
      is_public: $("#publicToggle").checked,
    };
    if (seedRaw !== "") payload.seed = Number(seedRaw);

    const btn = $("#generateBtn");
    const label = btn.querySelector(".btn__label");
    const spinner = btn.querySelector(".btn__spinner");
    btn.disabled = true;
    label.textContent = "Rendering…";
    spinner.hidden = false;

    showSkeletons(4);

    try {
      const gen = await api("/api/generations", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      state.lastGeneration = gen;
      renderResult(gen);

      if (state.user) {
        state.user.credits = Math.max(0, state.user.credits - 1);
        $("#creditsValue").textContent = state.user.credits;
      }
      loadHistory();
    } catch (err) {
      $("#result").hidden = true;
      $("#emptyState").hidden = false;
      if (err.status === 401) {
        clearSession();
        openAuth("login");
      } else if (err.status === 402) {
        toast("Out of credits — that's the demo limit", true);
      } else {
        toast(err.message, true);
      }
    } finally {
      btn.disabled = false;
      label.textContent = "Generate";
      spinner.hidden = true;
    }
  }

  function renderResult(gen) {
    $("#resultStyle").textContent = gen.style;
    $("#resultRatio").textContent = gen.aspect_ratio;
    $("#resultSeed").textContent = `seed ${gen.seed}`;
    $("#resultPrompt").textContent = gen.prompt;

    const grid = $("#imageGrid");
    grid.innerHTML = "";

    gen.images.forEach((img) => {
      const tile = document.createElement("div");
      tile.className = "tile";

      const el = document.createElement("img");
      el.src = img.url;
      el.alt = gen.prompt;
      el.loading = "lazy";
      el.width = img.width;
      el.height = img.height;

      const bar = document.createElement("div");
      bar.className = "tile__bar";

      const seed = document.createElement("span");
      seed.className = "tile__seed";
      seed.textContent = `#${img.seed}`;

      const dl = document.createElement("button");
      dl.className = "tile__act";
      dl.textContent = "Save";
      dl.addEventListener("click", (e) => {
        e.stopPropagation();
        downloadImage(img.url, gen.prompt, img.seed);
      });

      bar.appendChild(seed);
      bar.appendChild(dl);
      tile.appendChild(el);
      tile.appendChild(bar);

      tile.addEventListener("click", () => openLightbox(img.url, gen.prompt, img.seed));
      grid.appendChild(tile);
    });

    $("#emptyState").hidden = true;
    $("#result").hidden = false;
  }

  function downloadImage(url, prompt, seed) {
    const a = document.createElement("a");
    a.href = url;
    a.download = `tasveer-${seed}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast("Saved to your downloads");
  }

  // ── history ─────────────────────────────────────────────────────────────
  async function loadHistory() {
    if (!state.user) return;
    try {
      const items = await api("/api/generations?limit=12");
      const section = $("#historySection");
      const strip = $("#historyStrip");

      if (!items.length) {
        section.hidden = true;
        return;
      }

      section.hidden = false;
      $("#historyCount").textContent = `${items.length} recent`;
      strip.innerHTML = "";

      items.forEach((gen) => {
        if (!gen.images.length) return;
        const item = document.createElement("div");
        item.className = "history__item";

        const img = document.createElement("img");
        img.src = gen.images[0].url;
        img.alt = gen.prompt;
        img.loading = "lazy";

        const cap = document.createElement("span");
        cap.textContent = gen.prompt;

        item.appendChild(img);
        item.appendChild(cap);
        item.addEventListener("click", () => {
          renderResult(gen);
          window.scrollTo({ top: 0, behavior: "smooth" });
        });
        strip.appendChild(item);
      });
    } catch {
      /* history is a nicety — never break the page over it */
    }
  }

  // ── gallery ─────────────────────────────────────────────────────────────
  async function loadGallery(reset = false) {
    if (reset) {
      state.galleryPage = 1;
      $("#galleryGrid").innerHTML = "";
    }

    const params = new URLSearchParams({
      page: String(state.galleryPage),
      page_size: "12",
    });
    if (state.galleryStyle) params.set("style", state.galleryStyle);

    try {
      const data = await api(`/api/gallery?${params}`);
      const grid = $("#galleryGrid");

      if (reset && !data.items.length) {
        $("#galleryEmpty").hidden = false;
        $("#galleryMoreWrap").hidden = true;
        return;
      }
      $("#galleryEmpty").hidden = true;

      data.items.forEach((gen) => {
        if (!gen.images.length) return;
        const img = gen.images[0];

        const tile = document.createElement("div");
        tile.className = "tile";

        const el = document.createElement("img");
        el.src = img.url;
        el.alt = gen.prompt;
        el.loading = "lazy";

        const cap = document.createElement("div");
        cap.className = "tile__caption";
        cap.textContent = gen.prompt;

        tile.appendChild(el);
        tile.appendChild(cap);
        tile.addEventListener("click", () => openLightbox(img.url, gen.prompt, img.seed));
        grid.appendChild(tile);
      });

      $("#galleryMoreWrap").hidden = !data.has_more;
    } catch (err) {
      toast(err.message, true);
    }
  }

  // ── lightbox ────────────────────────────────────────────────────────────
  function openLightbox(url, prompt, seed) {
    $("#lightboxImg").src = url;
    $("#lightboxImg").alt = prompt;
    $("#lightboxCaption").textContent = `${prompt} · seed ${seed}`;
    const dl = $("#lightboxDownload");
    dl.href = url;
    dl.download = `tasveer-${seed}.png`;
    $("#lightbox").hidden = false;
  }

  function closeLightbox() {
    $("#lightbox").hidden = true;
    $("#lightboxImg").src = "";
  }

  // ── view switching ──────────────────────────────────────────────────────
  function switchView(view) {
    $$(".tab").forEach((t) => {
      const active = t.dataset.view === view;
      t.classList.toggle("is-active", active);
      t.setAttribute("aria-selected", String(active));
    });
    $$(".view").forEach((v) => {
      v.classList.toggle("is-active", v.id === `view-${view}`);
    });
    if (view === "gallery") loadGallery(true);
  }

  // ── seed prompts ────────────────────────────────────────────────────────
  const SEED_PROMPTS = [
    "a lone lighthouse on a stormy coast at night, cinematic",
    "neon city street in the rain, cyberpunk",
    "soft watercolor mountains at sunrise, pastel",
    "minimal white studio product shot of a ceramic vase",
    "oil painting of a desert caravan at golden hour",
    "anime girl on a rooftop under a bright blue sky",
  ];

  function renderSeedPrompts() {
    const wrap = $("#seedPrompts");
    wrap.innerHTML = "";
    SEED_PROMPTS.forEach((p) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "seed-chip";
      btn.textContent = p.length > 42 ? p.slice(0, 40) + "…" : p;
      btn.title = p;
      btn.addEventListener("click", () => {
        $("#prompt").value = p;
        updatePromptCount();
        $("#prompt").focus();
      });
      wrap.appendChild(btn);
    });
  }

  function updatePromptCount() {
    $("#promptCount").textContent = $("#prompt").value.length;
  }

  // ── wiring ──────────────────────────────────────────────────────────────
  function wire() {
    $("#genForm").addEventListener("submit", generate);
    $("#prompt").addEventListener("input", updatePromptCount);

    $("#authBtn").addEventListener("click", () => openAuth("login"));
    $("#signupBtn").addEventListener("click", () => openAuth("register"));
    $("#authForm").addEventListener("submit", submitAuth);
    $("#authSwitch").addEventListener("click", () =>
      openAuth(state.authMode === "login" ? "register" : "login")
    );
    $("#logoutBtn").addEventListener("click", (e) => {
      e.stopPropagation();
      clearSession();
      toast("Signed out");
    });

    $$("[data-close]").forEach((el) => el.addEventListener("click", closeAuth));

    $$(".tab").forEach((t) =>
      t.addEventListener("click", () => switchView(t.dataset.view))
    );

    $("#lightboxClose").addEventListener("click", closeLightbox);
    $("#lightbox").addEventListener("click", (e) => {
      if (e.target.id === "lightbox") closeLightbox();
    });

    $("#galleryMore").addEventListener("click", () => {
      state.galleryPage += 1;
      loadGallery(false);
    });

    $("#reuseSeed").addEventListener("click", () => {
      if (!state.lastGeneration) return;
      $("#seed").value = state.lastGeneration.seed;
      $("#prompt").value = state.lastGeneration.prompt;
      updatePromptCount();
      toast("Seed and prompt restored");
    });

    $("#copyPrompt").addEventListener("click", async () => {
      if (!state.lastGeneration) return;
      try {
        await navigator.clipboard.writeText(state.lastGeneration.prompt);
        toast("Prompt copied");
      } catch {
        toast("Could not copy", true);
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!$("#lightbox").hidden) closeLightbox();
        else if (!$("#authModal").hidden) closeAuth();
      }
    });
  }

  // ── boot ────────────────────────────────────────────────────────────────
  async function boot() {
    wire();
    renderSeedPrompts();
    updatePromptCount();
    await loadMeta();
    await restoreSession();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();

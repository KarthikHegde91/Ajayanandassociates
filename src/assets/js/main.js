/*!
 * main.js — Ajay Anand & Associates
 * No dependencies, ES2017. Every enhancement here is optional:
 * the site must remain usable if this file fails to load or run.
 */
(function () {
  "use strict";

  /* ---------------------------------------------------- always open pages at the top -- */
  (function () {
    if (location.hash) return;
    try { if ("scrollRestoration" in history) history.scrollRestoration = "manual"; } catch (e) {}
    var toTop = function () { window.scrollTo(0, 0); };
    toTop();
    window.addEventListener("pageshow", toTop);
    window.addEventListener("load", toTop);
  })();

  /* ---------------------------------------------------- tel:/mailto: links break inside sandboxed preview frames: open at top level -- */
  (function () {
    var framed = false;
    try { framed = window.top !== window.self; } catch (e) { framed = true; }
    if (!framed) return;
    document.querySelectorAll('a[href^="tel:"], a[href^="mailto:"]').forEach(function (a) { a.setAttribute("target", "_top"); });
  })();

  /* ---------------------------------------------------- header: scroll -- */
  var header = document.querySelector("[data-header], .site-header");
  if (header) {
    var onScroll = function () {
      header.classList.toggle("is-scrolled", window.scrollY > 4);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* ---------------------------------------------------- header: nav -- */
  (function () {
    if (!header) return;
    var toggle = document.querySelector("[data-nav-toggle]");
    var nav = document.getElementById("site-nav");

    function closeDrawer() {
      header.classList.remove("is-open");
      if (toggle) toggle.setAttribute("aria-expanded", "false");
      closeAllGroups();
    }
    function openDrawer() {
      header.classList.add("is-open");
      if (toggle) toggle.setAttribute("aria-expanded", "true");
    }
    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        if (header.classList.contains("is-open")) closeDrawer();
        else openDrawer();
      });
    }

    var groups = Array.prototype.slice.call(document.querySelectorAll("[data-nav-menu]"));

    function closeAllGroups(except) {
      groups.forEach(function (g) {
        if (g === except) return;
        g.classList.remove("is-open");
        var btn = g.querySelector(".nav__group-btn");
        if (btn) btn.setAttribute("aria-expanded", "false");
      });
    }

    groups.forEach(function (g) {
      var btn = g.querySelector(".nav__group-btn");
      if (!btn) return;
      btn.addEventListener("click", function () {
        var willOpen = !g.classList.contains("is-open");
        closeAllGroups(g);
        g.classList.toggle("is-open", willOpen);
        btn.setAttribute("aria-expanded", String(willOpen));
      });
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" || e.key === "Esc") {
        closeDrawer();
      }
    });

    document.addEventListener("click", function (e) {
      if (!header.contains(e.target)) {
        closeAllGroups();
      } else if (nav && !nav.contains(e.target) && e.target !== toggle && !(toggle && toggle.contains(e.target))) {
        closeAllGroups();
      }
    });
  })();

  /* ---------------------------------------------------- theme toggle -- */
  (function () {
    var toggle = document.querySelector("[data-theme-toggle]");
    if (!toggle) return;
    var root = document.documentElement;
    var metaThemeColor = document.querySelector('meta[name="theme-color"]');

    function resolvedTheme() {
      var attr = root.getAttribute("data-theme");
      if (attr === "dark" || attr === "light") return attr;
      return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function applyMetaThemeColor(theme) {
      if (metaThemeColor) metaThemeColor.setAttribute("content", theme === "dark" ? "#161826" : "#232552");
    }

    function syncToggle(theme) {
      var isDark = theme === "dark";
      toggle.setAttribute("aria-pressed", String(isDark));
      toggle.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
    }

    syncToggle(resolvedTheme());

    toggle.addEventListener("click", function () {
      var next = resolvedTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
      syncToggle(next);
      applyMetaThemeColor(next);
    });
  })();

  /* ---------------------------------------------------- current-page nav -- */
  (function () {
    var here = location.pathname.replace(/\/index\.html$/, "/");
    var hereNorm = here.length > 1 ? here.replace(/\/$/, "") : here;
    document.querySelectorAll(".nav__link[href]").forEach(function (a) {
      var href = a.getAttribute("href");
      if (!href || href.charAt(0) !== "/") return;
      var path = href.split("#")[0].split("?")[0];
      var pathNorm = path.length > 1 ? path.replace(/\/$/, "") : path;
      if (pathNorm === hereNorm) a.classList.add("is-current");
    });
  })();

  /* ---------------------------------------------------- accordion: single-open -- */
  document.querySelectorAll("[data-accordion]").forEach(function (group) {
    var items = Array.prototype.slice.call(group.querySelectorAll(".accordion__item"));
    items.forEach(function (item) {
      item.addEventListener("toggle", function () {
        if (item.open) {
          items.forEach(function (other) {
            if (other !== item) other.open = false;
          });
        }
      });
    });
  });

  /* ---------------------------------------------------- optional blocks -- */
  document.querySelectorAll("[data-optional]").forEach(function (block) {
    var body = block.querySelector(".optional__body") || block;
    if (!body.innerHTML || !body.innerHTML.replace(/\s|&nbsp;/g, "")) {
      block.remove();
    }
  });

  /* ---------------------------------------------------- reveal on scroll -- */
  (function () {
    var els = Array.prototype.slice.call(document.querySelectorAll("[data-reveal]"));
    if (!els.length) return;
    if (!("IntersectionObserver" in window)) {
      els.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.05, rootMargin: "0px 0px -8% 0px" }
    );
    els.forEach(function (el) { io.observe(el); });
    /* safety net: never leave content hidden (e.g. print, odd scroll restores) */
    window.setTimeout(function () {
      els.forEach(function (el) { el.classList.add("is-visible"); });
    }, 2500);
  })();

  /* ---------------------------------------------------- forms -- */
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  var MOBILE_RE = /^(\+91[\s-]?)?[6-9]\d{9}$/;

  document.querySelectorAll("[data-form]").forEach(function (form) {
    var submitBtn = form.querySelector('button[type="submit"], button:not([type])');
    if (form.hasAttribute("data-form-disabled")) {
      form.addEventListener("submit", function (e) { e.preventDefault(); });
      if (submitBtn) { submitBtn.disabled = true; submitBtn.setAttribute("aria-disabled", "true"); }
      return;
    }
    var statusEl = form.querySelector(".form__status");

    function setError(field, message) {
      var row = field.closest(".form__row");
      if (!row) return;
      var errorEl = row.querySelector(".form__error");
      row.classList.toggle("has-error", !!message);
      field.setAttribute("aria-invalid", message ? "true" : "false");
      if (errorEl && message) errorEl.textContent = message;
    }

    function validate() {
      var ok = true;
      Array.prototype.forEach.call(form.elements, function (field) {
        if (!field.name || field.name === "botcheck" || field.type === "hidden") return;
        var value = (field.value || "").trim();
        if (field.hasAttribute("required") && !value) {
          setError(field, "This field is required.");
          ok = false;
          return;
        }
        if (value && field.type === "email" && !EMAIL_RE.test(value)) {
          setError(field, "Enter a valid email address.");
          ok = false;
          return;
        }
        if (value && field.type === "tel" && !MOBILE_RE.test(value)) {
          setError(field, "Enter a valid 10-digit Indian mobile number.");
          ok = false;
          return;
        }
        setError(field, "");
      });
      return ok;
    }

    Array.prototype.forEach.call(form.elements, function (field) {
      if (!field.name) return;
      field.addEventListener("blur", function () {
        if (field.closest(".form__row.has-error")) validate();
      });
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();

      var hp = form.querySelector('[name="botcheck"]');
      if (hp && hp.checked) return; // silent abort: likely a bot

      if (!validate()) return;

      var data = new FormData(form);
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.dataset.label = submitBtn.dataset.label || submitBtn.textContent;
        submitBtn.textContent = "Sending…";
      }
      if (statusEl) {
        statusEl.className = "form__status";
        statusEl.textContent = "";
      }

      fetch(form.action, {
        method: form.method || "POST",
        body: data,
        headers: { Accept: "application/json" },
      })
        .then(function (res) {
          return res.json().catch(function () { return {}; }).then(function (json) {
            return { ok: res.ok && json.success !== false, json: json };
          });
        })
        .then(function (result) {
          if (result.ok) {
            var wrap = document.createElement("p");
            wrap.className = "form__status form__status--ok";
            wrap.setAttribute("role", "status");
            wrap.textContent = "Thank you. Your enquiry has been received - we will get back to you shortly.";
            form.replaceWith(wrap);
          } else {
            throw new Error((result.json && result.json.message) || "Submission failed");
          }
        })
        .catch(function () {
          if (statusEl) {
            statusEl.className = "form__status form__status--error";
            statusEl.textContent = "We could not send this automatically. Submitting the form directly instead...";
          }
          if (submitBtn) submitBtn.disabled = false;
          HTMLFormElement.prototype.submit.call(form);
        });
    });
  });
})();

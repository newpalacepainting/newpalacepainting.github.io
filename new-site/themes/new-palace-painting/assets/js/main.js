// New Palace Painting — progressive enhancements. Content is fully usable without JS.

const root = document.documentElement;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const header = document.querySelector("[data-header]");
const hero = document.querySelector(".hero");

/* ---------- Mobile navigation ---------- */
const toggle = document.querySelector("[data-nav-toggle]");
const menu = document.querySelector("[data-nav-menu]");

function setNav(open) {
  document.body.classList.toggle("nav-open", open);
  toggle.setAttribute("aria-expanded", String(open));
  toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
}

if (toggle && menu) {
  toggle.addEventListener("click", () => setNav(!document.body.classList.contains("nav-open")));
  menu.addEventListener("click", (e) => {
    if (e.target.closest("a")) setNav(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setNav(false);
  });
}

/* ---------- Scroll-driven UI (header, progress, parallax, process line, mobile CTA) ---------- */
const parallax = document.querySelector("[data-parallax]");
const process = document.querySelector("[data-process]");
const processPin = document.querySelector("[data-process-pin]");
const processSteps = process ? [...process.querySelectorAll(".process-step")] : [];
const processFill = process?.querySelector(".process-line span");
const mobileCta = document.querySelector("[data-mobile-cta]");
const vertical = window.matchMedia("(max-width: 991.98px)");
// Must match the pinned-process media query in main.css.
const pinned = window.matchMedia(
  "(min-width: 992px) and (min-height: 680px) and (prefers-reduced-motion: no-preference)"
);
const clamp01 = (v) => Math.min(1, Math.max(0, v));

// Service-area map: municipalities and logo pieces carry data-o (0..1) = progress at which they get painted.
const mapPin = document.querySelector("[data-map-pin]");
const mapFrame = document.querySelector("[data-map]");
const mapParts = mapFrame ? [...mapFrame.querySelectorAll("[data-o]")].map((el) => ({ el, o: +el.dataset.o, muni: el.classList.contains("map-muni") })) : [];
const mapAreas = [...document.querySelectorAll("[data-map-area]")].map((el) => ({ el, at: +el.dataset.at }));
const mapCount = document.querySelector("[data-map-count]");
let mapLast = -1;

function paintMap(vh) {
  let p;
  if (reduceMotion) {
    p = 1;
  } else if (pinned.matches && mapPin) {
    // Start painting a little before the pin engages; hold the finished map for the last 15% of the track.
    const r = mapPin.getBoundingClientRect();
    const lead = vh * 0.1;
    p = clamp01((lead - r.top) / ((r.height - vh) * 0.85 + lead));
  } else {
    const r = mapFrame.getBoundingClientRect();
    p = clamp01((vh * 0.85 - r.top) / (r.height + vh * 0.1));
  }
  if (Math.abs(p - mapLast) < 0.002) return;
  mapLast = p;
  let painted = 0;
  for (const part of mapParts) {
    const on = p > 0 && p >= part.o;
    part.el.classList.toggle("is-painted", on);
    if (on && part.muni) painted++;
  }
  mapAreas.forEach((a) => a.el.classList.toggle("is-on", p > 0 && p >= a.at));
  if (mapCount) mapCount.textContent = painted;
}

// Tagline reveal: words switch from muted to full colour one at a time, in reading order, while the
// rainbow brush stroke underneath is painted across, as the section rises through the viewport.
const tagline = document.querySelector("[data-tagline]");
const taglinePin = document.querySelector("[data-tagline-pin]");
const taglineWords = tagline ? [...tagline.querySelectorAll(".tw")] : [];
let taglineLit = -1;
function revealTagline(vh) {
  let p;
  if (reduceMotion) {
    p = 1;
  } else if (pinned.matches && taglinePin) {
    // Pinned like the process steps: scroll through the track drives the effect; last 20% holds the finished line.
    const r = taglinePin.getBoundingClientRect();
    p = clamp01(-r.top / (r.height - vh) / 0.8);
  } else {
    const r = tagline.getBoundingClientRect();
    p = clamp01((vh * 0.85 - r.top) / (vh * 0.3 + r.height * 0.6));
  }
  tagline.style.setProperty("--paint", clamp01((p - 0.15) / 0.85).toFixed(3));
  const lit = Math.round(p * taglineWords.length);
  if (lit === taglineLit) return;
  taglineLit = lit;
  taglineWords.forEach((w, i) => w.classList.toggle("is-on", i < lit));
}

let ticking = false;
function onScroll() {
  const y = window.scrollY;
  const vh = window.innerHeight;
  const max = root.scrollHeight - vh;

  header?.classList.toggle("is-scrolled", y > 40);
  if (tagline) revealTagline(vh);
  root.style.setProperty("--progress", max > 0 ? (y / max).toFixed(4) : 0);
  mobileCta?.classList.toggle("is-visible", y > (hero ? hero.offsetHeight * 0.6 : 200));

  if (parallax && !reduceMotion && y < vh * 1.2) {
    parallax.style.transform = `translate3d(0, ${y * 0.25}px, 0)`;
  }

  if (process && processPin && pinned.matches) {
    // Steps are stuck to the viewport; scroll distance through the pin track drives the fill.
    // The last 15% of the track is a hold so the finished line stays on screen before unpinning.
    const r = processPin.getBoundingClientRect();
    const fill = clamp01(-r.top / (r.height - vh) / 0.85);
    const last = processSteps.length - 1;
    processFill.style.setProperty("--fill", fill.toFixed(4));
    processSteps.forEach((step, i) => step.classList.toggle("is-lit", r.top <= 1 && fill >= i / last - 0.01));
  } else if (process) {
    // Fill the line as the section crosses the middle of the viewport; light up steps behind it.
    const r = process.getBoundingClientRect();
    const fill = clamp01((vh * 0.6 - r.top) / r.height);
    processFill.style.setProperty("--fill", fill.toFixed(3));
    processSteps.forEach((step, i) => {
      const at = vertical.matches
        ? (step.offsetTop + 36) / r.height
        : (i + 0.5) / processSteps.length;
      step.classList.toggle("is-lit", fill >= at - 0.02);
    });
  }
  if (mapFrame) paintMap(vh);
  ticking = false;
}

window.addEventListener(
  "scroll",
  () => {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(onScroll);
    }
  },
  { passive: true }
);
window.addEventListener("resize", onScroll, { passive: true });
onScroll();

/* ---------- Reveal on scroll + animated counters ---------- */
function countUp(el) {
  const target = parseFloat(el.dataset.count);
  const decimals = parseInt(el.dataset.decimals || "0", 10);
  if (reduceMotion) return;
  const start = performance.now();
  const duration = 1400;
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = (target * eased).toFixed(decimals);
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

const revealEls = document.querySelectorAll(".reveal");
if ("IntersectionObserver" in window) {
  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-in");
        entry.target.querySelectorAll("[data-count]").forEach(countUp);
        io.unobserve(entry.target);
      }
    },
    { rootMargin: "0px 0px -4% 0px", threshold: 0.05 }
  );
  revealEls.forEach((el) => io.observe(el));
} else {
  revealEls.forEach((el) => el.classList.add("is-in"));
}

/* ---------- Active section highlight in nav ---------- */
const navLinks = [...document.querySelectorAll(".nav-link-item")].filter((a) => a.hash);
const sections = navLinks.map((a) => document.getElementById(a.hash.slice(1))).filter(Boolean);
if (sections.length && "IntersectionObserver" in window) {
  const spy = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        navLinks.forEach((a) => a.classList.toggle("is-active", a.hash === `#${entry.target.id}`));
      }
    },
    { rootMargin: "-45% 0px -50% 0px" }
  );
  // Observe the hero too (it has no id), so returning to the top clears the highlight.
  [hero, ...sections].filter(Boolean).forEach((s) => spy.observe(s));
}

/* ---------- Lightbox ---------- */
window.addEventListener("load", () => {
  if (typeof window.baguetteBox !== "undefined") {
    window.baguetteBox.run(".baguette-gallery", { animation: "fadeIn", noScrollbars: true });
  }
});

/* ---------- Hero video: pause when off-screen or when reduced motion is requested ---------- */
const video = hero?.querySelector("video");
if (video) {
  if (reduceMotion) {
    video.removeAttribute("autoplay");
    video.pause();
  } else if ("IntersectionObserver" in window) {
    new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) video.play().catch(() => {});
      else video.pause();
    }).observe(hero);
  }
}

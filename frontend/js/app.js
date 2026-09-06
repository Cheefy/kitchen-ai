import { renderHome } from "./pages/home.js";
import { renderCalendar } from "./pages/calendar.js";
import { renderRecipe } from "./pages/recipe.js";
import { renderSettings } from "./pages/settings.js";

const view = document.getElementById("view");
const navTabs = document.getElementById("nav-tabs");

function setActiveTab(name) {
  navTabs.querySelectorAll("a[data-tab]").forEach((a) => {
    a.classList.toggle("active", a.dataset.tab === name);
  });
}

function navigate(hash) {
  window.location.hash = hash;
}

async function route() {
  const hash = window.location.hash || "#/home";
  const [, path, param] = hash.split("/");

  view.innerHTML = "";

  if (!path || path === "home") {
    setActiveTab("home");
    await renderHome(view, navigate);
    return;
  }

  if (path === "calendar") {
    setActiveTab("calendar");
    await renderCalendar(view);
    return;
  }

  if (path === "recipe" && param) {
    setActiveTab("home");
    await renderRecipe(view, param);
    return;
  }

  if (path === "settings") {
    setActiveTab("settings");
    await renderSettings(view);
    return;
  }

  setActiveTab("home");
  await renderHome(view, navigate);
}

// route() mutates #view incrementally (appendChild calls interleaved with
// awaited fetches), not as one atomic swap. If two route() calls ever run
// concurrently -- observed in practice on a fresh page load/refresh, where
// something fires the router twice in close succession -- their appends
// interleave and both survive, leaving duplicated content in the DOM.
// Serializing every call through one chain guarantees only one is ever
// running at a time; a second call queued for the same hash is also just
// dropped, since it would render identical content anyway.
let routeChain = Promise.resolve();
let lastQueuedHash = null;

function scheduleRoute() {
  const hash = window.location.hash || "#/home";
  if (hash === lastQueuedHash) return routeChain;
  lastQueuedHash = hash;
  routeChain = routeChain.then(route).catch((err) => console.error("routing failed", err));
  return routeChain;
}

window.addEventListener("hashchange", scheduleRoute);

// Module scripts execute after the document has finished parsing, so
// readyState is already past "loading" by the time this runs -- meaning
// DOMContentLoaded either already fired or is about to fire regardless.
// Registering a listener AND doing an immediate call both fired route()
// on every hard refresh. Pick exactly one path (the scheduleRoute guard
// above is the real fix for the duplicate-render bug; this just avoids
// scheduling it twice for no reason).
if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", scheduleRoute, { once: true });
} else {
  scheduleRoute();
}

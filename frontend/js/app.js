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

window.addEventListener("hashchange", route);

// Module scripts execute after the document has finished parsing, so
// readyState is already past "loading" by the time this runs -- meaning
// DOMContentLoaded either already fired or is about to fire regardless.
// Registering a listener AND doing an immediate call both fired route()
// on every hard refresh, doubling every render. Pick exactly one path.
if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", route, { once: true });
} else {
  route();
}

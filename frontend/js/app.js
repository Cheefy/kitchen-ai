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
window.addEventListener("DOMContentLoaded", route);

// In case the module loads after DOMContentLoaded already fired.
if (document.readyState !== "loading") {
  route();
}

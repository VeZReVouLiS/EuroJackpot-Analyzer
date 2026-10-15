/* Starts the in-browser API before the UI boots (the UI waits for window.EJ_WEBAPI_PROMISE) and registers the
 * service worker (offline use + automatic updates of the web app). */
import { createApi } from "./webapi.js";

window.EJ_WEBAPI_PROMISE = createApi().then((api) => { window.EJ_WEBAPI = api; return api; });

if ("serviceWorker" in navigator && location.protocol.startsWith("http") && !(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform())) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").then((reg) => {
      reg.addEventListener("updatefound", () => {
        const w = reg.installing;
        if (w) w.addEventListener("statechange", () => { if (w.state === "installed" && navigator.serviceWorker.controller) window.__ejUpdateReady = true; });
      });
    }).catch(() => {});
    let reloaded = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => { if (!reloaded && window.__ejUpdateReady) { reloaded = true; location.reload(); } });
  });
}

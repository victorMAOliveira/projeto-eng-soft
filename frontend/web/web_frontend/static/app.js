// EstágioHub — small progressive enhancements (HTMX does the heavy lifting).
(function () {
  "use strict";

  // Toggle "Mostrar microsserviços": highlights every panel with its service colour.
  // The choice is kept in a cookie so server-rendered pages start in the right state.
  function applyServicesToggle(enabled) {
    document.body.classList.toggle("show-services", enabled);
    document.cookie = "eh_show_services=" + (enabled ? "1" : "0") + "; path=/; max-age=31536000; samesite=lax";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.getElementById("toggle-services");
    if (toggle) {
      toggle.addEventListener("change", function () { applyServicesToggle(toggle.checked); });
    }
  });

  // Propagate a correlation id generated per page load, so a whole user
  // interaction can be traced across gateway and service logs.
  var pageCorrelation = "web-" + Math.random().toString(16).slice(2, 10);
  document.addEventListener("htmx:configRequest", function (evt) {
    evt.detail.headers["X-Correlation-ID"] = pageCorrelation + "-" + Date.now().toString(16);
  });
})();

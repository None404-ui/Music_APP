/**
 * Показ полей админки MusicItem в зависимости от вида (track / album / playlist).
 */
(function () {
  "use strict";

  function kindValue() {
    var el = document.querySelector("#id_kind");
    return el ? String(el.value || "").trim() : "";
  }

  function setVisible(selector, show) {
    document.querySelectorAll(selector).forEach(function (node) {
      node.style.display = show ? "" : "none";
    });
  }

  function sync() {
    var k = kindValue();
    setVisible(".musicitem-fs-track", k === "track");
    setVisible(".musicitem-fs-album", k === "album" || k === "playlist");
  }

  document.addEventListener("DOMContentLoaded", function () {
    var kind = document.querySelector("#id_kind");
    if (!kind) {
      return;
    }
    kind.addEventListener("change", sync);
    sync();
  });
})();

(function () {
    "use strict";

    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

    function qsa(sel, root) {
        return Array.from((root || document).querySelectorAll(sel));
    }

    function setActiveItem(items, activeKey) {
        items.forEach(function (el) {
            var key = el.getAttribute("data-section");
            if (!key) {
                return;
            }

            if (key === activeKey) {
                el.classList.add("active");
            } else {
                el.classList.remove("active");
            }
        });
    }

    function showPanel(activeKey) {
        var panels = qsa(".settings-panel");
        panels.forEach(function (panel) {
            var id = panel.id || "";
            var isMatch = id === ("settings-" + activeKey);
            if (isMatch) {
                panel.classList.remove("hidden");
            } else {
                panel.classList.add("hidden");
            }
        });
    }

    function normalizeKey(key) {
        if (!key) {
            return "general";
        }
        if (key === "appearance") {
            return "appearance";
        }
        return "general";
    }

    function readKeyFromHash() {
        var hash = window.location.hash || "";
        if (!hash) {
            return "general";
        }
        return normalizeKey(hash.replace("#", "").trim());
    }

    function writeHash(key) {
        var next = "#" + key;
        if (window.location.hash === next) {
            return;
        }
        history.replaceState({}, "", window.location.pathname + window.location.search + next);
    }

    function init() {
        var container = qs(".settings-layout");
        if (!container) {
            return;
        }

        var items = qsa(".settings-item[data-section]", container);
        if (items.length === 0) {
            return;
        }

        function apply(key) {
            var k = normalizeKey(key);
            setActiveItem(items, k);
            showPanel(k);
            writeHash(k);
        }

        container.addEventListener("click", function (evt) {
            var item = evt.target.closest(".settings-item[data-section]");
            if (!item) {
                return;
            }

            if (item.classList.contains("disabled")) {
                return;
            }

            var key = item.getAttribute("data-section");
            apply(key);
        });

        window.addEventListener("hashchange", function () {
            apply(readKeyFromHash());
        });

        apply(readKeyFromHash());
    }

    document.addEventListener("DOMContentLoaded", init);

    // If settings content is injected via fragment navigation, DOMContentLoaded will not fire.
    // This listens for swaps by polling a lightweight condition once per animation frame until found.
    (function initAfterSwap() {
        if (document.querySelector(".settings-layout")) {
            init();
            return;
        }
        requestAnimationFrame(initAfterSwap);
    })();
})();
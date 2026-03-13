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

    function setThemeUI(container, pref) {
        var segmented = qs(".segmented", container);
        var buttons = qsa(".segmented-btn[data-theme-choice]", container);

        if (!segmented || buttons.length === 0) {
            return;
        }

        var order = ["light", "dark", "system"];
        var idx = order.indexOf(pref);
        if (idx === -1) {
            idx = 2;
        }

        segmented.style.setProperty("--seg-index", String(idx));

        buttons.forEach(function (btn) {
            var choice = btn.getAttribute("data-theme-choice");
            var active = choice === pref;
            btn.classList.toggle("is-active", active);
            btn.setAttribute("aria-pressed", active ? "true" : "false");
        });
    }

    function bindThemeSelector(container) {
        var segmented = qs(".segmented", container);
        if (!segmented) {
            return;
        }

        if (!window.CapstoneTheme || typeof window.CapstoneTheme.setPreference !== "function") {
            return;
        }

        if (segmented.getAttribute("data-bound") === "1") {
            setThemeUI(container, window.CapstoneTheme.getPreference());
            return;
        }
        segmented.setAttribute("data-bound", "1");

        setThemeUI(container, window.CapstoneTheme.getPreference());

        segmented.addEventListener("click", function (evt) {
            var btn = evt.target.closest(".segmented-btn[data-theme-choice]");
            if (!btn) {
                return;
            }

            var choice = btn.getAttribute("data-theme-choice") || "system";
            window.CapstoneTheme.setPreference(choice);
            setThemeUI(container, window.CapstoneTheme.getPreference());
        });

        if (window.matchMedia) {
            var mq = window.matchMedia("(prefers-color-scheme: dark)");
            var onChange = function () {
                setThemeUI(container, window.CapstoneTheme.getPreference());
            };

            if (mq && typeof mq.addEventListener === "function") {
                mq.addEventListener("change", onChange);
            } else if (mq && typeof mq.addListener === "function") {
                mq.addListener(onChange);
            }
        }
    }

    function initSettingsLayout(container) {
        if (container.getAttribute("data-settings-init") === "1") {
            bindThemeSelector(container);
            return;
        }
        container.setAttribute("data-settings-init", "1");

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

            apply(item.getAttribute("data-section"));
        });

        window.addEventListener("hashchange", function () {
            apply(readKeyFromHash());
        });

        bindThemeSelector(container);
        apply(readKeyFromHash());
    }

    function init() {
        var container = qs(".settings-layout");
        if (!container) {
            return;
        }
        initSettingsLayout(container);
    }

    document.addEventListener("DOMContentLoaded", init);

    window.pageInit = function () {
        init();
    };
})();
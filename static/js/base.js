(function () {
    "use strict";

    var navInProgress = false;

    var lastAppliedTheme = null;   // "light" | "dark" | null
    var lastAppliedPref = null;    // "light" | "dark" | "system" | null

    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

    function qsa(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function getCookie(name) {
        var prefix = name + "=";
        var parts = document.cookie ? document.cookie.split(";") : [];
        for (var i = 0; i < parts.length; i++) {
            var part = parts[i].trim();
            if (part.indexOf(prefix) === 0) {
                return decodeURIComponent(part.slice(prefix.length));
            }
        }
        return null;
    }

    function setCookie(name, value, days) {
        var maxAge = "";
        if (typeof days === "number") {
            maxAge = "; Max-Age=" + String(days * 24 * 60 * 60);
        }
        document.cookie = name + "=" + encodeURIComponent(value) + maxAge + "; Path=/; SameSite=Lax";
    }

    function normalizeThemePreference(pref) {
        if (pref === "light" || pref === "dark" || pref === "system") {
            return pref;
        }
        return "system";
    }

    function getThemePreference() {
        return normalizeThemePreference(getCookie("themePreference"));
    }

    function systemPrefersDark() {
        return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    }

    function effectiveThemeFromPreference(pref) {
        if (pref === "light" || pref === "dark") {
            return pref;
        }
        return systemPrefersDark() ? "dark" : "light";
    }

    function applyEffectiveTheme(theme) {
        if (theme !== "light" && theme !== "dark") {
            return false;
        }
        if (lastAppliedTheme === theme) {
            return false;
        }

        var light = qs("#theme-light");
        var dark = qs("#theme-dark");
        if (!light || !dark) {
            return false;
        }

        light.disabled = (theme === "dark");
        dark.disabled = (theme === "light");

        document.documentElement.setAttribute("data-theme", theme);
        lastAppliedTheme = theme;

        if (window.CapstoneVanta && typeof window.CapstoneVanta.onThemeChange === "function") {
            window.CapstoneVanta.onThemeChange(theme);
        }

        return true;
    }

    function applyPreference(pref) {
        var p = normalizeThemePreference(pref);
        var effective = effectiveThemeFromPreference(p);

        applyEffectiveTheme(effective);
        lastAppliedPref = p;
    }

    function setThemePreference(pref) {
        var currentPref = getThemePreference();
        var p = normalizeThemePreference(pref);

        // If the preference itself is the same, nothing changes.
        if (p === currentPref) {
            return;
        }

        var beforeEffective = effectiveThemeFromPreference(currentPref);
        var afterEffective = effectiveThemeFromPreference(p);

        setCookie("themePreference", p, 365);

        // Requirement: switching between system and explicit theme should do nothing
        // if the *effective* theme is the same.
        if (afterEffective === beforeEffective) {
            lastAppliedPref = p;
            return;
        }

        applyPreference(p);
    }

    function initTheme() {
        applyPreference(getThemePreference());

        if (!window.matchMedia) {
            return;
        }

        var mq = window.matchMedia("(prefers-color-scheme: dark)");
        var onChange = function () {
            // Only respond to OS changes when preference is system.
            if (getThemePreference() !== "system") {
                return;
            }

            var nextEffective = effectiveThemeFromPreference("system");
            if (nextEffective === lastAppliedTheme) {
                return;
            }

            applyPreference("system");
        };

        if (mq && typeof mq.addEventListener === "function") {
            mq.addEventListener("change", onChange);
        } else if (mq && typeof mq.addListener === "function") {
            mq.addListener(onChange);
        }
    }

    function afterStylesApplied(cb) {
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                cb();
            });
        });
    }

    window.CapstoneTheme = {
        getPreference: getThemePreference,
        setPreference: setThemePreference,
        getEffectiveTheme: function () {
            return effectiveThemeFromPreference(getThemePreference());
        }
    };

    function sameOrigin(url) {
        return url.origin === window.location.origin;
    }

    function shouldHandleLink(link, evt) {
        if (!link) {
            return false;
        }
        if (link.target && link.target !== "") {
            return false;
        }
        if (evt.defaultPrevented) {
            return false;
        }
        if (evt.metaKey || evt.ctrlKey || evt.shiftKey || evt.altKey) {
            return false;
        }
        if (link.hasAttribute("download")) {
            return false;
        }

        var href = link.getAttribute("href");
        if (!href || href.charAt(0) === "#") {
            return false;
        }

        var url = new URL(link.href, window.location.href);
        return sameOrigin(url);
    }

    function focusMain() {
        var main = qs("#app-content");
        if (!main) {
            return;
        }
        try {
            main.focus();
        } catch (e) {
            /* ignore */
        }
    }

    function setMainInnerHtml(html) {
        var main = qs("#app-content");
        if (!main) {
            return false;
        }
        main.innerHTML = html;
        return true;
    }

    function setExtraHead(html) {
        qsa("head [data-dynamic-head]").forEach(function (el) {
            el.remove();
        });

        if (!html) {
            return;
        }

        var temp = document.createElement("template");
        temp.innerHTML = html;

        qsa("*", temp.content).forEach(function (node) {
            var clone = node.cloneNode(true);
            clone.setAttribute("data-dynamic-head", "true");
            document.head.appendChild(clone);
        });
    }

    function copyAttrs(fromEl, toEl) {
        Array.prototype.slice.call(fromEl.attributes).forEach(function (attr) {
            toEl.setAttribute(attr.name, attr.value);
        });
    }

    function loadScriptNode(scriptNode) {
        return new Promise(function (resolve, reject) {
            var s = document.createElement("script");
            copyAttrs(scriptNode, s);

            s.async = false;

            if (scriptNode.src) {
                s.onload = function () {
                    resolve();
                };
                s.onerror = function () {
                    reject(new Error("Failed to load script: " + scriptNode.src));
                };
                document.body.appendChild(s);
                return;
            }

            s.text = scriptNode.text || scriptNode.textContent || "";
            document.body.appendChild(s);
            resolve();
        });
    }

    function setExtraScripts(html) {
        qsa("script[data-dynamic-script]").forEach(function (el) {
            el.remove();
        });

        if (!html) {
            return Promise.resolve();
        }

        var temp = document.createElement("template");
        temp.innerHTML = html;

        var scripts = qsa("script", temp.content);
        scripts.forEach(function (node) {
            node.setAttribute("data-dynamic-script", "true");
        });

        var chain = Promise.resolve();
        scripts.forEach(function (node) {
            chain = chain.then(function () {
                return loadScriptNode(node);
            });
        });

        return chain;
    }

    function fetchFragment(path, intent) {
        return fetch(path, {
            headers: { "X-Requested-With": intent },
            credentials: "same-origin"
        }).then(function (res) {
            if (!res.ok) {
                throw new Error("HTTP " + res.status);
            }
            return res.json();
        });
    }

    function fetchAndSwap(path, push) {
        if (navInProgress) {
            return;
        }
        navInProgress = true;

        fetchFragment(path, "fetch")
            .then(function (data) {
                if (!data || typeof data.html !== "string") {
                    window.location.href = path;
                    return;
                }

                if (typeof data.title === "string" && data.title.length > 0) {
                    document.title = data.title;
                }

                if (typeof data.head === "string") {
                    setExtraHead(data.head);
                }

                if (!setMainInnerHtml(data.html)) {
                    window.location.href = path;
                    return;
                }

                var scriptsHtml = (typeof data.scripts === "string") ? data.scripts : "";
                return setExtraScripts(scriptsHtml).then(function () {
                    if (push) {
                        history.pushState({}, "", path);
                    }
                    focusMain();

                    if (typeof window.pageInit === "function") {
                        try {
                            window.pageInit();
                        } catch (e) {
                            /* ignore */
                        }
                    }
                });
            })
            .catch(function () {
                window.location.href = path;
            })
            .finally(function () {
                navInProgress = false;
            });
    }

    function onDocumentClick(evt) {
        var link = evt.target.closest("a");
        if (!shouldHandleLink(link, evt)) {
            return;
        }
        evt.preventDefault();

        var url = new URL(link.href, window.location.href);
        fetchAndSwap(url.pathname + url.search, true);
    }

    function onPopState() {
        fetchAndSwap(window.location.pathname + window.location.search, false);
    }

    function onMouseOver(evt) {
        var link = evt.target.closest("a[data-nav]");
        if (!link || !link.href) {
            return;
        }

        var url = new URL(link.href, window.location.href);
        if (!sameOrigin(url)) {
            return;
        }

        fetchFragment(url.pathname + url.search, "prefetch")
            .then(function () {
                /* ignore */
            })
            .catch(function () {
                /* ignore */
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.addEventListener("click", onDocumentClick);
        window.addEventListener("popstate", onPopState);
        document.addEventListener("mouseover", onMouseOver);

        initTheme();

        if (window.CapstoneVanta) {
            if (typeof window.CapstoneVanta.bindResize === "function") {
                window.CapstoneVanta.bindResize();
            }
            if (typeof window.CapstoneVanta.init === "function") {
                window.CapstoneVanta.init();
            }
        }
    });
})();
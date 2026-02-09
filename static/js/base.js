(function () {
    "use strict";

    var vantaEffect = null;
    var resizeTimer = null;
    var navInProgress = false;

    function cssVar(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    function colorToInt(hex) {
        if (!hex) {
            return 0;
        }
        return parseInt(hex.replace("#", ""), 16);
    }

    function canInitVanta() {
        return window.VANTA && window.VANTA.TOPOLOGY && window.p5;
    }

    function getVantaEl() {
        return document.getElementById("vanta-bg");
    }

    function createVantaEffect() {
        var el = getVantaEl();
        if (!el) {
            return null;
        }

        return window.VANTA.TOPOLOGY({
            el: el,
            mouseControls: false,
            touchControls: false,
            gyroControls: false,
            color: colorToInt(cssVar("--vanta-color")),
            backgroundColor: colorToInt(cssVar("--vanta-bg")),
            speed: 50
        });
    }

    function destroyVanta() {
        if (vantaEffect && typeof vantaEffect.destroy === "function") {
            try {
                vantaEffect.destroy();
            } catch (e) {
                /* ignore */
            }
        }
        vantaEffect = null;
    }

    function initVantaOnce() {
        if (vantaEffect) {
            return;
        }
        if (!canInitVanta()) {
            return;
        }

        var el = getVantaEl();
        if (!el) {
            return;
        }

        if (el.clientWidth === 0 || el.clientHeight === 0) {
            return;
        }

        vantaEffect = createVantaEffect();
    }

    function reinitVantaAfterResize() {
        if (!canInitVanta()) {
            return;
        }

        var el = getVantaEl();
        if (!el) {
            return;
        }

        if (el.clientWidth === 0 || el.clientHeight === 0) {
            return;
        }

        destroyVanta();
        vantaEffect = createVantaEffect();
    }

    function onWindowResize() {
        if (resizeTimer) {
            clearTimeout(resizeTimer);
        }

        resizeTimer = setTimeout(function () {
            requestAnimationFrame(function () {
                reinitVantaAfterResize();
            });
        }, 300);
    }

    function isSameOrigin(url) {
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
        if (!isSameOrigin(url)) {
            return false;
        }

        return true;
    }

    function focusMain() {
        var main = document.getElementById("app-content");
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
        var currentMain = document.getElementById("app-content");
        if (!currentMain) {
            return false;
        }

        currentMain.innerHTML = html;
        return true;
    }

    function setExtraHead(html) {
        if (!html) {
            return;
        }

        // Remove old dynamic head nodes
        document
            .querySelectorAll("head [data-dynamic-head]")
            .forEach(function (el) {
                el.remove();
            });

        // Parse fragment properly
        var temp = document.createElement("template");
        temp.innerHTML = html;

        temp.content.querySelectorAll("*").forEach(function (node) {
            var clone = node.cloneNode(true);
            clone.setAttribute("data-dynamic-head", "true");
            document.head.appendChild(clone);
        });
    }

    function copyScriptAttributes(fromEl, toEl) {
        Array.prototype.slice.call(fromEl.attributes).forEach(function (attr) {
            toEl.setAttribute(attr.name, attr.value);
        });
    }

    function loadScriptNode(scriptNode) {
        return new Promise(function (resolve, reject) {
            var s = document.createElement("script");
            copyScriptAttributes(scriptNode, s);

            // Force deterministic execution order for dynamic scripts
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

            // Inline script
            s.text = scriptNode.text || scriptNode.textContent || "";
            document.body.appendChild(s);
            resolve();
        });
    }

    function setExtraScripts(html) {
        // Remove old dynamic scripts
        document.querySelectorAll("script[data-dynamic-script]").forEach(function (el) {
            el.remove();
        });

        if (!html) {
            return Promise.resolve();
        }

        var temp = document.createElement("template");
        temp.innerHTML = html;

        var scripts = Array.prototype.slice.call(temp.content.querySelectorAll("script"));

        // Mark them so we can clean up on the next navigation
        scripts.forEach(function (node) {
            node.setAttribute("data-dynamic-script", "true");
        });

        // Load sequentially to preserve dependencies
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
            headers: {
                "X-Requested-With": intent
            },
            credentials: "same-origin"
        })
        .then(function (res) {
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

            var ok = setMainInnerHtml(data.html);
            if (!ok) {
                window.location.href = path;
                return;
            }

            var scriptsHtml = "";
            if (typeof data.scripts === "string") {
                scriptsHtml = data.scripts;
            }

            return setExtraScripts(scriptsHtml).then(function () {
                if (push) {
                    history.pushState({}, "", path);
                }

                focusMain();

                // Optional: give pages a hook after swap
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

    function prefetchLink(link) {
        if (!link || !link.href) {
            return;
        }

        var url = new URL(link.href, window.location.href);
        if (!isSameOrigin(url)) {
            return;
        }

        fetchFragment(url.pathname + url.search, "prefetch")
        .then(function () {
            /* intentionally ignore result */
        })
        .catch(function () {
            /* ignore */
        });
    }

    function onMouseOver(evt) {
        var link = evt.target.closest("a[data-nav]");
        if (!link) {
            return;
        }

        prefetchLink(link);
    }

    document.addEventListener("DOMContentLoaded", function () {
        window.addEventListener("resize", onWindowResize);

        document.addEventListener("click", onDocumentClick);
        window.addEventListener("popstate", onPopState);

        document.addEventListener("mouseover", onMouseOver);

        initVantaOnce();
    });

    window.addEventListener("beforeunload", function () {
        destroyVanta();
    });
})();

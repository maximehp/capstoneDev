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
            mouseControls: true,
            touchControls: true,
            gyroControls: false,
            color: colorToInt(cssVar("--vanta-color")),
            backgroundColor: colorToInt(cssVar("--vanta-bg")),
            scale: 1.0,
            scaleMobile: 1.0
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

    function setMainHtml(newMain) {
        var currentMain = document.getElementById("app-content");
        if (!currentMain) {
            return false;
        }

        currentMain.innerHTML = newMain.innerHTML;
        return true;
    }

    function updateTitleFromDoc(doc) {
        if (!doc) {
            return;
        }

        var titleEl = doc.querySelector("title");
        if (titleEl && titleEl.textContent) {
            document.title = titleEl.textContent;
        }
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

    function fetchAndSwap(path, push) {
        if (navInProgress) {
            return;
        }
        navInProgress = true;

        fetch(path, {
            headers: {
                "X-Requested-With": "fetch"
            },
            credentials: "same-origin"
        })
        .then(function (res) {
            if (!res.ok) {
                throw new Error("HTTP " + res.status);
            }
            return res.text();
        })
        .then(function (html) {
            var parser = new DOMParser();
            var doc = parser.parseFromString(html, "text/html");

            var newMain = doc.querySelector("#app-content");
            if (!newMain) {
                window.location.href = path;
                return;
            }

            updateTitleFromDoc(doc);

            var ok = setMainHtml(newMain);
            if (!ok) {
                window.location.href = path;
                return;
            }

            if (push) {
                history.pushState({}, "", path);
            }

            focusMain();
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

    window.addEventListener("load", function () {
        initVantaOnce();
        window.addEventListener("resize", onWindowResize);

        document.addEventListener("click", onDocumentClick);
        window.addEventListener("popstate", onPopState);
    });

    window.addEventListener("beforeunload", function () {
        destroyVanta();
    });
})();

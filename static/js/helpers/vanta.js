(function () {
    "use strict";

    var vantaEffect = null;
    var resizeTimer = null;

    var lastTheme = null;               // "light" | "dark" | null
    var lastColors = null;              // { color: number, backgroundColor: number } | null
    var themeChangeToken = 0;

    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

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
        return !!(window.VANTA && window.VANTA.TOPOLOGY && window.p5);
    }

    function getVantaEl() {
        return qs("#vanta-bg");
    }

    function isUsableEl(el) {
        if (!el) {
            return false;
        }
        return !(el.clientWidth === 0 || el.clientHeight === 0);
    }

    function readColorsFromCss() {
        return {
            color: colorToInt(cssVar("--vanta-color")),
            backgroundColor: colorToInt(cssVar("--vanta-bg"))
        };
    }

    function colorsEqual(a, b) {
        if (!a || !b) {
            return false;
        }
        return a.color === b.color && a.backgroundColor === b.backgroundColor;
    }

    function create() {
        var el = getVantaEl();
        if (!el) {
            return null;
        }

        // Force the browser to apply the stylesheet toggles before reading CSS vars.
        // This is cheap compared to a full reinit and avoids the “old colors” tick.
        void document.documentElement.offsetHeight;

        var colors = readColorsFromCss();
        lastColors = colors;

        return window.VANTA.TOPOLOGY({
            el: el,
            mouseControls: false,
            touchControls: false,
            gyroControls: false,
            color: colors.color,
            backgroundColor: colors.backgroundColor,
            speed: 50
        }) || null;
    }

    function destroy() {
        if (vantaEffect && typeof vantaEffect.destroy === "function") {
            try {
                vantaEffect.destroy();
            } catch (e) {
                /* ignore */
            }
        }
        vantaEffect = null;
    }

    function init() {
        if (vantaEffect) {
            return;
        }
        if (!canInitVanta()) {
            return;
        }

        var el = getVantaEl();
        if (!isUsableEl(el)) {
            return;
        }

        vantaEffect = create();
    }

    function reinit() {
        if (!canInitVanta()) {
            return false;
        }

        var el = getVantaEl();
        if (!isUsableEl(el)) {
            return false;
        }

        destroy();
        vantaEffect = create();
        return !!vantaEffect;
    }

    function tryReinitWithRetries(token, attemptsLeft) {
        if (token !== themeChangeToken) {
            return;
        }

        var ok = reinit();
        if (ok) {
            return;
        }

        if (attemptsLeft <= 0) {
            return;
        }

        requestAnimationFrame(function () {
            tryReinitWithRetries(token, attemptsLeft - 1);
        });
    }

    function onThemeChange(effectiveTheme) {
        if (effectiveTheme !== "light" && effectiveTheme !== "dark") {
            return;
        }
        if (lastTheme === effectiveTheme) {
            return;
        }

        lastTheme = effectiveTheme;
        themeChangeToken += 1;
        var token = themeChangeToken;

        // Fast path: do it immediately.
        var before = lastColors;
        var ok = reinit();

        // If we couldn’t reinit because the element was 0x0, retry a few frames.
        if (!ok) {
            tryReinitWithRetries(token, 6);
            return;
        }

        // If the reinit happened but colors did not change (race), retry once next frame.
        // This keeps the “instant” feel most of the time, and only delays on the rare miss.
        var after = lastColors;
        if (colorsEqual(before, after)) {
            requestAnimationFrame(function () {
                if (token !== themeChangeToken) {
                    return;
                }

                // Force one more style pass and rebuild again.
                void document.documentElement.offsetHeight;
                reinit();
            });
        }
    }

    function onWindowResize() {
        if (resizeTimer) {
            clearTimeout(resizeTimer);
        }

        resizeTimer = setTimeout(function () {
            reinit();
        }, 300);
    }

    function bindResize() {
        window.addEventListener("resize", onWindowResize);
    }

    window.CapstoneVanta = {
        init: init,
        destroy: destroy,
        reinit: reinit,
        onThemeChange: onThemeChange,
        bindResize: bindResize
    };

    window.addEventListener("beforeunload", function () {
        destroy();
    });
})();
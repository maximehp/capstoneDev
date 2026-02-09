function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return parts.pop().split(";").shift();
    }
    return null;
}

function showError(message) {
    const box = document.getElementById("login-error");
    if (!box) {
        alert(message);
        return;
    }
    box.textContent = message;
    box.style.display = "block";
}

function clearError() {
    const box = document.getElementById("login-error");
    if (!box) {
        return;
    }
    box.textContent = "";
    box.style.display = "none";
}

async function parseJsonOrThrow(resp) {
    const contentType = resp.headers.get("content-type") || "";
    const text = await resp.text();

    if (!contentType.includes("application/json")) {
        throw new Error(`Expected JSON, got:\n${text.slice(0, 200)}`);
    }

    return JSON.parse(text);
}

function setMainInnerHtml(html) {
    const main = document.getElementById("app-content");
    if (!main) {
        return false;
    }
    main.innerHTML = html;
    return true;
}

async function fetchFragment(path) {
    const resp = await fetch(path, {
        method: "GET",
        credentials: "same-origin",
        headers: {
            "X-Requested-With": "fetch",
        },
    });

    const data = await parseJsonOrThrow(resp);

    if (!resp.ok) {
        throw new Error(data.error || `HTTP ${resp.status}`);
    }

    return data;
}

async function navigateWithoutReload(path) {
    const data = await fetchFragment(path);

    if (typeof data.title === "string" && data.title.length > 0) {
        document.title = data.title;
    }

    const ok = setMainInnerHtml(data.html);
    if (!ok) {
        throw new Error("Missing #app-content");
    }

    history.pushState({}, "", path);
}

document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("login-form");
    const submitBtn = document.getElementById("login-submit");

    if (!form) {
        return;
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        clearError();

        const formData = new FormData(form);
        const payload = {
            username: formData.get("username"),
            password: formData.get("password"),
        };

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Logging in...";
        }

        try {
            const resp = await fetch("/login/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "fetch",
                },
                body: JSON.stringify(payload),
            });

            const data = await parseJsonOrThrow(resp);

            if (!resp.ok || !data.ok) {
                throw new Error(data.error || `HTTP ${resp.status}`);
            }

            const target = data.redirect || "/";

            try {
                await navigateWithoutReload(target);
            } catch (e) {
                // window.location.href = target;
            }
        } catch (e) {
            showError(e.message);
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = "Log in";
            }
        }
    });
});
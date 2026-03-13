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
            window.location.assign(target);
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

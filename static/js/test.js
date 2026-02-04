function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return parts.pop().split(";").shift();
    }
    return null;
}

function getStartVmUrl() {
    const meta = document.querySelector('meta[name="start-vm-url"]');
    if (!meta) {
        throw new Error("Missing <meta name=\"start-vm-url\"> in template");
    }
    return meta.getAttribute("content");
}

document.addEventListener("click", async function (event) {
    const btn = event.target.closest("#start-vm-btn");
    if (!btn) {
        return;
    }

    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = "Starting...";

    try {
        const url = getStartVmUrl();

        const resp = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
                "X-Requested-With": "fetch"
            },
            body: JSON.stringify({ vm_id: "900", node: "Kif" })
        });

        const contentType = resp.headers.get("content-type") || "";
        const text = await resp.text();

        if (!contentType.includes("application/json")) {
            throw new Error(`HTTP ${resp.status} returned HTML:\n${text.slice(0, 200)}`);
        }

        const data = JSON.parse(text);

        if (!resp.ok || !data.ok) {
            throw new Error(data.error || `HTTP ${resp.status}`);
        }

        btn.textContent = "VM start requested";
    } catch (e) {
        btn.disabled = false;
        btn.textContent = originalText;
        alert(`Failed: ${e.message}`);
    }
});

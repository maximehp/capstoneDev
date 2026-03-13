(function () {
    "use strict";

    function qs(sel, root) {
        return (root || document).querySelector(sel);
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

    function escapeHtml(str) {
        return String(str || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function setText(id, value) {
        var el = qs("#" + id);
        if (!el) {
            return;
        }
        el.textContent = value;
    }

    function show(id) {
        var el = qs("#" + id);
        if (el) {
            el.classList.remove("hidden");
        }
    }

    function hide(id) {
        var el = qs("#" + id);
        if (el) {
            el.classList.add("hidden");
        }
    }

    function bytesToHuman(bytes) {
        if (typeof bytes !== "number" || !isFinite(bytes) || bytes < 0) {
            return "-";
        }

        var units = ["B", "KB", "MB", "GB", "TB"];
        var i = 0;
        var n = bytes;

        while (n >= 1024 && i < units.length - 1) {
            n = n / 1024;
            i += 1;
        }

        var rounded = (i === 0) ? String(Math.round(n)) : String(Math.round(n * 10) / 10);
        return rounded + " " + units[i];
    }

    function looksLikeHttpUrl(url) {
        return /^https?:\/\//i.test(url || "");
    }

    function normalizeUrl(url) {
        return String(url || "").trim().toLowerCase();
    }

    var PACKAGE_RE = /^[a-z0-9][a-z0-9+.-]{0,63}$/;

    var modal = qs("#vm-modal");
    var openBtn = qs("#new-vm-btn");

    var sceneTrack = qs("#scene-track");
    var toTcBtn = qs("#to-tc");
    var tcBackBtn = qs("#tc-back");

    var vmTrack = qs("#vm-track");
    var tcTrack = qs("#tc-track");

    var vmNextBtn = qs("#vm-next");
    var tcNextBtn = qs("#tc-next");

    var templateNameInput = qs("#tc-template-name");
    var isoSavedSelect = qs("#tc-iso-saved");
    var isoUrlInput = qs("#tc-os-iso-url");
    var isoCheckBtn = qs("#tc-iso-check");
    var isoStatus = qs("#tc-iso-status");

    var swInput = qs("#tc-sw-url");
    var swCheckBtn = qs("#tc-sw-check");
    var swStatus = qs("#tc-sw-status");
    var swSavedBox = qs("#tc-sw-saved-box");
    var buildProfileSelect = qs("#tc-build-profile");
    var hwCpuInput = qs("#tc-hw-cpu");
    var hwRamInput = qs("#tc-hw-ram");
    var hwDiskInput = qs("#tc-hw-disk");
    var netBridgeSelect = qs("#tc-net-bridge");
    var netVlanInput = qs("#tc-net-vlan");
    var netIpv4Select = qs("#tc-net-ipv4");
    var windowsOptionsBox = qs("#tc-windows-options");
    var winVirtioUrlInput = qs("#tc-win-virtio-url");
    var winAdminUsernameInput = qs("#tc-win-admin-username");
    var winAdminPasswordInput = qs("#tc-win-admin-password");
    var winImageSelectorTypeInput = qs("#tc-win-image-selector-type");
    var winImageSelectorValueInput = qs("#tc-win-image-selector-value");
    var winFirmwareProfileInput = qs("#tc-win-firmware-profile");
    var customSelectEntries = [];
    var customSelectSeed = 0;

    var validateStatus = qs("#tc-validate-status");
    var createStatus = qs("#tc-create-status");
    var buildStatusCard = qs("#tc-build-status");
    var buildStatusText = qs("#tc-build-status-text");
    var buildStageText = qs("#tc-build-stage-text");
    var buildErrorText = qs("#tc-build-error-text");
    var buildResultsBox = qs("#tc-build-results");

    var tcIndex = 0;
    var tcCount = 0;
    var isCreatingTemplate = false;
    var activeBuildJobId = null;
    var buildPollTimer = null;

    var lastIsoCheckedUrl = null;
    var lastIsoOk = false;
    var lastIsoData = null;

    var softwareItems = [];

    function setScene(scene) {
        if (sceneTrack) {
            sceneTrack.setAttribute("data-scene", scene);
        }
    }

    function setVmPage(i) {
        if (vmTrack) {
            vmTrack.style.setProperty("--content-index", String(i));
        }
    }

    function setTcPage(i) {
        if (!tcTrack) {
            return;
        }

        tcIndex = i;
        tcTrack.style.setProperty("--content-index", String(i));

        if (tcCount > 0 && i === (tcCount - 1)) {
            renderOverview(null);
        }

        updateTcNextEnabled();
    }

    function setIsoStatus(text, kind) {
        if (!isoStatus) {
            return;
        }
        isoStatus.textContent = text || "";
        isoStatus.classList.remove("is-error", "is-ok", "is-warn");
        if (kind === "error") {
            isoStatus.classList.add("is-error");
        } else if (kind === "ok") {
            isoStatus.classList.add("is-ok");
        } else if (kind === "warn") {
            isoStatus.classList.add("is-warn");
        }
    }

    function setSwStatus(text, kind) {
        if (!swStatus) {
            return;
        }
        swStatus.textContent = text || "";
        swStatus.classList.remove("is-error", "is-ok", "is-warn");
        if (kind === "error") {
            swStatus.classList.add("is-error");
        } else if (kind === "ok") {
            swStatus.classList.add("is-ok");
        } else if (kind === "warn") {
            swStatus.classList.add("is-warn");
        }
    }

    function setValidateStatus(text, kind) {
        if (!validateStatus) {
            return;
        }
        validateStatus.textContent = text || "";
        validateStatus.classList.remove("is-error", "is-ok", "is-warn");
        if (kind === "error") {
            validateStatus.classList.add("is-error");
        } else if (kind === "ok") {
            validateStatus.classList.add("is-ok");
        } else if (kind === "warn") {
            validateStatus.classList.add("is-warn");
        }
    }

    function setCreateStatus(text, kind) {
        if (!createStatus) {
            return;
        }
        createStatus.textContent = text || "";
        createStatus.classList.remove("is-error", "is-ok", "is-warn");
        if (kind === "error") {
            createStatus.classList.add("is-error");
        } else if (kind === "ok") {
            createStatus.classList.add("is-ok");
        } else if (kind === "warn") {
            createStatus.classList.add("is-warn");
        }
    }

    function setBuildStatus(payload) {
        if (!buildStatusCard) {
            return;
        }

        if (!payload) {
            buildStatusCard.classList.add("hidden");
            if (buildResultsBox) {
                buildResultsBox.innerHTML = "";
            }
            return;
        }

        buildStatusCard.classList.remove("hidden");
        if (buildStatusText) {
            buildStatusText.textContent = payload.status || "-";
        }
        if (buildStageText) {
            buildStageText.textContent = payload.stage || "-";
        }
        if (buildErrorText) {
            buildErrorText.textContent = payload.error || "-";
        }
        renderBuildResults(payload.result && payload.result.software_results ? payload.result.software_results : []);
    }

    function renderBuildResults(items) {
        if (!buildResultsBox) {
            return;
        }

        if (!items || items.length === 0) {
            buildResultsBox.innerHTML = '<div class="saved-item"><div class="saved-item-main"><div class="saved-item-title">No install results yet</div><div class="saved-item-sub">Results appear while the job runs.</div></div></div>';
            return;
        }

        buildResultsBox.innerHTML = items.map(function (item) {
            var status = String(item.status || "unknown");
            var css = status === "installed" ? " is-selected" : "";
            var message = item.message || "";
            var code = (typeof item.exit_code === "number") ? String(item.exit_code) : "-";
            return '' +
                '<div class="saved-item' + css + '">' +
                    '<div class="saved-item-main">' +
                        '<div class="saved-item-title">' + escapeHtml(item.item_id || "item") + ' - ' + escapeHtml(status) + '</div>' +
                        '<div class="saved-item-sub">exit=' + escapeHtml(code) + ' ' + escapeHtml(message) + '</div>' +
                    '</div>' +
                '</div>';
        }).join("");
    }

    function stopBuildPolling() {
        if (buildPollTimer) {
            clearTimeout(buildPollTimer);
            buildPollTimer = null;
        }
    }

    function toggleWindowsOptions() {
        if (!windowsOptionsBox) {
            return;
        }
        if (getTargetOs() === "windows") {
            windowsOptionsBox.classList.remove("hidden");
        } else {
            windowsOptionsBox.classList.add("hidden");
        }
    }

    function clearIsoDetails() {
        setText("tc-iso-filename", "-");
        setText("tc-iso-size", "-");
        setText("tc-iso-type", "-");
        setText("tc-iso-modified", "-");
        hide("tc-iso-details");
    }

    function applyIsoDetails(data) {
        setText("tc-iso-filename", data && data.filename ? data.filename : "-");
        setText(
            "tc-iso-size",
            bytesToHuman(data && typeof data.size_bytes === "number" ? data.size_bytes : NaN)
        );
        setText("tc-iso-type", data && data.content_type ? data.content_type : "-");
        setText("tc-iso-modified", data && data.last_modified ? data.last_modified : "-");
        show("tc-iso-details");
    }

    function keyForUrl(url) {
        return "url:" + normalizeUrl(url);
    }

    function keyForPackage(pkg) {
        return "pkg:" + String(pkg || "").trim().toLowerCase();
    }

    function getBuildProfile() {
        return buildProfileSelect ? String(buildProfileSelect.value || "").toLowerCase() : "";
    }

    function getTargetOs() {
        var value = getBuildProfile();
        if (value === "windows_unattend") {
            return "windows";
        }
        if (value === "ubuntu_autoinstall" || value === "debian_preseed") {
            return "linux";
        }
        return "";
    }

    function getBuildProfileLabel() {
        if (!buildProfileSelect || buildProfileSelect.selectedIndex < 0) {
            return "";
        }
        return String(buildProfileSelect.options[buildProfileSelect.selectedIndex].textContent || "").trim();
    }

    function resetSelectToPlaceholder(selectEl) {
        if (!selectEl) {
            return;
        }
        selectEl.value = "";
        if (String(selectEl.value) !== "" && selectEl.options.length > 0) {
            selectEl.selectedIndex = 0;
        }
    }

    function findCustomSelectEntry(selectEl) {
        for (var i = 0; i < customSelectEntries.length; i++) {
            if (customSelectEntries[i].select === selectEl) {
                return customSelectEntries[i];
            }
        }
        return null;
    }

    function renderCustomSelectOptions(entry) {
        if (!entry || !entry.select || !entry.menu) {
            return;
        }

        entry.menu.innerHTML = "";

        for (var i = 0; i < entry.select.options.length; i++) {
            var opt = entry.select.options[i];
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "custom-select-option";
            btn.setAttribute("role", "option");
            btn.setAttribute("data-index", String(i));
            btn.textContent = opt.textContent || opt.label || "";

            if (opt.disabled) {
                btn.disabled = true;
                btn.classList.add("is-disabled");
            }

            if (opt.hidden) {
                btn.hidden = true;
            }

            entry.menu.appendChild(btn);
        }
    }

    function syncCustomSelect(entry) {
        if (!entry || !entry.select || !entry.trigger || !entry.value || !entry.menu) {
            return;
        }

        renderCustomSelectOptions(entry);

        var selectedIndex = entry.select.selectedIndex;
        var selectedText = "";
        var selectedValue = "";

        if (selectedIndex >= 0 && selectedIndex < entry.select.options.length) {
            selectedText = entry.select.options[selectedIndex].textContent || "";
            selectedValue = entry.select.options[selectedIndex].value || "";
        } else if (entry.select.options.length > 0) {
            selectedText = entry.select.options[0].textContent || "";
            selectedValue = entry.select.options[0].value || "";
        }

        var optionButtons = entry.menu.querySelectorAll(".custom-select-option");
        Array.prototype.forEach.call(optionButtons, function (btn) {
            var idx = Number(btn.getAttribute("data-index"));
            var isSelected = idx === selectedIndex;
            btn.classList.toggle("is-selected", isSelected);
            btn.setAttribute("aria-selected", isSelected ? "true" : "false");
        });

        entry.value.textContent = selectedText || "";
        entry.value.classList.toggle("is-placeholder", selectedValue === "");
        entry.trigger.disabled = !!entry.select.disabled;
    }

    function syncCustomSelectForElement(selectEl) {
        var entry = findCustomSelectEntry(selectEl);
        if (entry) {
            syncCustomSelect(entry);
        }
    }

    function syncAllCustomSelects() {
        customSelectEntries.forEach(function (entry) {
            syncCustomSelect(entry);
        });
    }

    function setCustomSelectOpen(entry, open) {
        if (!entry || !entry.trigger || !entry.menu) {
            return;
        }

        var shouldOpen = !!open && !entry.trigger.disabled;
        entry.trigger.classList.toggle("is-open", shouldOpen);
        entry.trigger.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
        entry.menu.classList.toggle("is-open", shouldOpen);
    }

    function closeAllCustomSelects(exceptEntry) {
        customSelectEntries.forEach(function (entry) {
            if (entry !== exceptEntry) {
                setCustomSelectOpen(entry, false);
            }
        });
    }

    function ensureCustomSelect(selectEl) {
        if (!selectEl) {
            return null;
        }

        var existing = findCustomSelectEntry(selectEl);
        if (existing) {
            return existing;
        }

        var wrapper = document.createElement("div");
        wrapper.className = "custom-select";

        var trigger = document.createElement("button");
        trigger.type = "button";
        trigger.className = "field-control custom-select-trigger";
        trigger.setAttribute("aria-haspopup", "listbox");
        trigger.setAttribute("aria-expanded", "false");

        customSelectSeed += 1;
        var baseId = selectEl.id ? selectEl.id : ("custom-select-" + customSelectSeed);
        var menuId = baseId + "-menu";
        trigger.setAttribute("aria-controls", menuId);
        trigger.id = baseId + "-trigger";

        var valueSpan = document.createElement("span");
        valueSpan.className = "custom-select-value";
        trigger.appendChild(valueSpan);

        var caret = document.createElement("span");
        caret.className = "custom-select-caret";
        caret.setAttribute("aria-hidden", "true");
        trigger.appendChild(caret);

        var menu = document.createElement("div");
        menu.className = "custom-select-menu";
        menu.id = menuId;
        menu.setAttribute("role", "listbox");
        menu.setAttribute("aria-label", selectEl.getAttribute("aria-label") || selectEl.id || "Select");

        var parent = selectEl.parentNode;
        if (!parent) {
            return null;
        }

        parent.insertBefore(wrapper, selectEl);
        wrapper.appendChild(trigger);
        wrapper.appendChild(menu);
        wrapper.appendChild(selectEl);

        selectEl.classList.add("native-select-hidden");

        var entry = {
            select: selectEl,
            wrapper: wrapper,
            trigger: trigger,
            value: valueSpan,
            menu: menu
        };

        trigger.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            var expanded = trigger.getAttribute("aria-expanded") === "true";
            if (expanded) {
                setCustomSelectOpen(entry, false);
                return;
            }
            closeAllCustomSelects(entry);
            syncCustomSelect(entry);
            setCustomSelectOpen(entry, true);
        });

        trigger.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
                e.preventDefault();
                closeAllCustomSelects(entry);
                syncCustomSelect(entry);
                setCustomSelectOpen(entry, true);
                return;
            }
            if (e.key === "Escape") {
                setCustomSelectOpen(entry, false);
            }
        });

        menu.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            var optionBtn = e.target.closest(".custom-select-option");
            if (!optionBtn || optionBtn.disabled) {
                return;
            }

            var idx = Number(optionBtn.getAttribute("data-index"));
            if (!isFinite(idx) || idx < 0 || idx >= selectEl.options.length) {
                return;
            }

            selectEl.selectedIndex = idx;
            selectEl.dispatchEvent(new Event("change", { bubbles: true }));
            closeAllCustomSelects(null);
            trigger.focus();
        });

        selectEl.addEventListener("change", function () {
            syncCustomSelect(entry);
        });

        customSelectEntries.push(entry);
        syncCustomSelect(entry);
        return entry;
    }

    function initCustomSelects() {
        if (!modal) {
            return;
        }
        var selects = modal.querySelectorAll("select.select-control");
        Array.prototype.forEach.call(selects, function (selectEl) {
            ensureCustomSelect(selectEl);
        });
        syncAllCustomSelects();
    }

    function inferArtifactTypeFromName(name) {
        var n = String(name || "").toLowerCase();
        if (n.endsWith(".msix")) {
            return "msix";
        }
        if (n.endsWith(".msi")) {
            return "msi";
        }
        if (n.endsWith(".exe")) {
            return "exe";
        }
        if (n.endsWith(".deb")) {
            return "deb";
        }
        if (n.endsWith(".rpm")) {
            return "rpm";
        }
        if (n.endsWith(".apk")) {
            return "apk";
        }
        if (n.endsWith(".tar.gz") || n.endsWith(".tgz") || n.endsWith(".tar.xz") || n.endsWith(".tar.bz2") || n.endsWith(".tar")) {
            return "tar";
        }
        if (n.endsWith(".zip")) {
            return "zip";
        }
        if (n.endsWith(".ps1")) {
            return "ps1";
        }
        if (n.endsWith(".bat")) {
            return "bat";
        }
        if (n.endsWith(".cmd")) {
            return "cmd";
        }
        if (n.endsWith(".sh")) {
            return "sh";
        }
        if (n.endsWith(".run")) {
            return "run";
        }
        if (n.endsWith(".bin")) {
            return "bin";
        }
        return "unknown";
    }

    function inferInstallStrategy(item, targetOs) {
        if (!item) {
            return "unknown";
        }
        if (item.kind === "package") {
            return (targetOs === "linux") ? "package_manager" : "custom_command";
        }

        var artifact = item.artifact_type || "unknown";
        if (targetOs === "windows") {
            if (artifact === "exe" || artifact === "msi" || artifact === "msix") {
                return "native_installer";
            }
            if (artifact === "zip") {
                return "archive";
            }
            if (artifact === "ps1" || artifact === "bat" || artifact === "cmd") {
                return "script";
            }
            return "custom_command";
        }

        if (artifact === "deb" || artifact === "rpm" || artifact === "apk") {
            return "package_manager";
        }
        if (artifact === "tar" || artifact === "zip") {
            return "archive";
        }
        if (artifact === "sh" || artifact === "run") {
            return "script";
        }
        return "custom_command";
    }

    function getSoftwareCompatibilityError(item, targetOs) {
        if (!targetOs) {
            return "Select build profile first.";
        }
        if (!item) {
            return "Invalid software selection.";
        }

        if (item.kind === "package") {
            if (targetOs === "windows") {
                return "Package names are only supported for Linux targets.";
            }
            return "";
        }

        var artifact = String(
            item.artifact_type ||
            inferArtifactTypeFromName(item.filename || item.url || item.label || "")
        ).toLowerCase();

        if (targetOs === "linux" && (artifact === "exe" || artifact === "msi" || artifact === "msix")) {
            return "Windows installers (.exe/.msi/.msix) are not allowed for Linux targets.";
        }
        if (
            targetOs === "windows" &&
            (artifact === "deb" || artifact === "rpm" || artifact === "apk" || artifact === "sh" || artifact === "run")
        ) {
            return "Linux package/script artifacts are not allowed for Windows targets.";
        }

        return "";
    }

    function clearIncompatibleSelectionsForTarget() {
        var targetOs = getTargetOs();
        if (!targetOs) {
            return 0;
        }

        var cleared = 0;
        softwareItems.forEach(function (item) {
            if (!item.selected) {
                return;
            }
            var compatibilityError = getSoftwareCompatibilityError(item, targetOs);
            if (compatibilityError) {
                item.selected = false;
                cleared += 1;
            }
        });

        return cleared;
    }

    function findSoftwareItemByKey(key) {
        for (var i = 0; i < softwareItems.length; i++) {
            if (softwareItems[i].key === key) {
                return softwareItems[i];
            }
        }
        return null;
    }

    function upsertSoftwareItem(nextItem) {
        var existing = findSoftwareItemByKey(nextItem.key);
        if (existing) {
            existing.label = nextItem.label || existing.label;
            existing.url = nextItem.url || existing.url;
            existing.filename = nextItem.filename || existing.filename;
            existing.isSaved = !!(existing.isSaved || nextItem.isSaved);
            existing.kind = nextItem.kind || existing.kind;
            existing.artifact_type = nextItem.artifact_type || existing.artifact_type || "unknown";
            existing.install_strategy = nextItem.install_strategy || existing.install_strategy || "custom_command";
            existing.silent_args = nextItem.silent_args || existing.silent_args || "";
            existing.selected = true;
            return existing;
        }

        nextItem.artifact_type = nextItem.artifact_type || "unknown";
        nextItem.install_strategy = nextItem.install_strategy || "custom_command";
        nextItem.silent_args = nextItem.silent_args || "";
        nextItem.selected = true;
        softwareItems.push(nextItem);
        return nextItem;
    }

    function renderSoftwareList() {
        if (!swSavedBox) {
            return;
        }

        if (softwareItems.length === 0) {
            swSavedBox.innerHTML = "";
            return;
        }

        var targetOs = getTargetOs();

        swSavedBox.innerHTML = softwareItems.map(function (item) {
            var selectedClass = item.selected ? " is-selected" : "";
            var typeLabel = item.kind === "package" ? "package" : "url";
            var subtitle = item.kind === "package" ? item.label : (item.url || "");
            var strategy = item.install_strategy || inferInstallStrategy(item, getTargetOs());
            var compatibilityError = getSoftwareCompatibilityError(item, targetOs);
            var disabledAttr = compatibilityError ? " disabled" : "";
            var statusHint = compatibilityError
                ? (" | " + (targetOs ? ("blocked for " + targetOs) : "choose build profile"))
                : "";

            return '<div class="saved-item' + selectedClass + '" data-software-key="' + escapeHtml(item.key) + '">' +
                '<button type="button" class="saved-item-main" data-software-select="' + escapeHtml(item.key) + '"' + disabledAttr + '>' +
                    '<span class="saved-item-title">' + escapeHtml(item.label) + '</span>' +
                    '<span class="saved-item-sub">' + escapeHtml(typeLabel + ': ' + subtitle + ' | ' + strategy + statusHint) + '</span>' +
                '</button>' +
                (item.selected ? '<button type="button" class="saved-item-remove" data-software-remove="' + escapeHtml(item.key) + '" aria-label="Remove">&times;</button>' : '') +
            '</div>';
        }).join("");
    }

    function getSelectedSoftwareUrls() {
        return softwareItems
            .filter(function (item) { return item.selected && item.kind === "url" && item.url; })
            .map(function (item) { return item.url; });
    }

    function getSelectedPackages() {
        return softwareItems
            .filter(function (item) { return item.selected && item.kind === "package"; })
            .map(function (item) { return item.label; });
    }

    function getServiceFlags() {
        return {
            qemu_guest: false,
            docker: false,
            devtools: false
        };
    }

    function clampInt(rawValue, fallback, minValue, maxValue) {
        var n = parseInt(String(rawValue || ""), 10);
        if (!isFinite(n)) {
            return fallback;
        }
        if (typeof minValue === "number" && n < minValue) {
            return minValue;
        }
        if (typeof maxValue === "number" && n > maxValue) {
            return maxValue;
        }
        return n;
    }

    function splitDnsList(raw) {
        var value = String(raw || "").trim();
        if (!value) {
            return [];
        }
        return value.split(",").map(function (part) {
            return part.trim();
        }).filter(function (part) {
            return part.length > 0;
        });
    }

    function buildHardwarePayload() {
        return {
            cpu: clampInt(hwCpuInput ? hwCpuInput.value : "", 2, 1, 64),
            ram_gb: clampInt(hwRamInput ? hwRamInput.value : "", 4, 1, 512),
            disk_gb: clampInt(hwDiskInput ? hwDiskInput.value : "", 32, 8, 4096)
        };
    }

    function buildNetworkPayload() {
        var ipv4Mode = netIpv4Select ? String(netIpv4Select.value || "dhcp") : "dhcp";
        if (ipv4Mode !== "dhcp") {
            ipv4Mode = "dhcp";
        }
        var vlanValue = netVlanInput ? String(netVlanInput.value || "").trim() : "";
        var vlan = vlanValue ? clampInt(vlanValue, 0, 1, 4094) : null;
        return {
            bridge: netBridgeSelect ? String(netBridgeSelect.value || "") : "",
            vlan: vlan,
            ipv4_mode: ipv4Mode,
            static_ip: "",
            static_gateway: "",
            static_dns: []
        };
    }

    function buildWindowsPayload() {
        return {
            virtio_iso_url: winVirtioUrlInput ? String(winVirtioUrlInput.value || "").trim() : "",
            admin_username: winAdminUsernameInput ? String(winAdminUsernameInput.value || "").trim() : "",
            admin_password: winAdminPasswordInput ? String(winAdminPasswordInput.value || "").trim() : "",
            image_selector_type: winImageSelectorTypeInput ? String(winImageSelectorTypeInput.value || "image_name").trim() : "image_name",
            image_selector_value: winImageSelectorValueInput ? String(winImageSelectorValueInput.value || "").trim() : "",
            firmware_profile: winFirmwareProfileInput ? String(winFirmwareProfileInput.value || "bios_legacy").trim() : "bios_legacy",
            winrm_port: 5985,
            winrm_use_ssl: false,
            winrm_timeout: "2h"
        };
    }

    function windowsFieldsAreReady() {
        if (getTargetOs() !== "windows") {
            return true;
        }
        var windowsPayload = buildWindowsPayload();
        return !!(
            looksLikeHttpUrl(windowsPayload.virtio_iso_url) &&
            windowsPayload.admin_username &&
            windowsPayload.admin_password &&
            windowsPayload.image_selector_value &&
            windowsPayload.firmware_profile
        );
    }

    function buildValidationPayload() {
        var targetOs = getTargetOs();
        var selectedItems = softwareItems.filter(function (item) { return !!item.selected; }).map(function (item) {
            var artifact = item.artifact_type || inferArtifactTypeFromName(item.filename || item.url || item.label || "");
            var strategy = item.install_strategy || inferInstallStrategy(
                { kind: item.kind, artifact_type: artifact },
                targetOs
            );
            return {
                kind: item.kind,
                label: item.label || "",
                url: item.url || "",
                artifact_type: artifact,
                install_strategy: strategy,
                silent_args: item.silent_args || ""
            };
        });

        return {
            build_profile: getBuildProfile(),
            target_os: targetOs,
            software_items: selectedItems,
            software_urls: getSelectedSoftwareUrls(),
            custom_packages: getSelectedPackages(),
            services: getServiceFlags()
        };
    }

    function buildTemplateCreatePayload() {
        var payload = buildValidationPayload();
        payload.template_name = templateNameInput ? templateNameInput.value.trim() : "";
        payload.iso_url = isoUrlInput ? isoUrlInput.value.trim() : "";
        payload.hardware = buildHardwarePayload();
        payload.network = buildNetworkPayload();
        payload.windows = buildWindowsPayload();
        payload.ansible = {};
        return payload;
    }

    function renderOverview(normalizedPayload) {
        var overview = qs("#tc-overview");
        if (!overview) {
            return;
        }

        var templateName = templateNameInput ? templateNameInput.value.trim() : "";
        var isoUrl = isoUrlInput ? isoUrlInput.value.trim() : "";
        var targetOs = getTargetOs();
        var buildProfileLabel = getBuildProfileLabel();

        var softwareCount = getSelectedSoftwareUrls().length;
        var packageCount = getSelectedPackages().length;

        var rows = [
            { k: "Template", v: templateName || "-" },
            { k: "Build profile", v: buildProfileLabel || "-" },
            { k: "Target OS", v: targetOs },
            { k: "ISO URL", v: isoUrl || "-" },
            { k: "Selected software", v: String(softwareCount) },
            { k: "Selected packages", v: String(packageCount) },
            { k: "Guest networking", v: "DHCP-ready template" }
        ];

        if (targetOs === "windows") {
            var windowsPayload = buildWindowsPayload();
            rows.push({ k: "Windows admin", v: windowsPayload.admin_username || "-" });
            rows.push({ k: "Image selector", v: (windowsPayload.image_selector_type || "image_name") + ": " + (windowsPayload.image_selector_value || "-") });
            rows.push({ k: "Firmware", v: windowsPayload.firmware_profile || "-" });
            rows.push({ k: "VirtIO ISO", v: windowsPayload.virtio_iso_url || "-" });
        }

        overview.innerHTML = rows.map(function (row) {
            return '<div class="overview-item"><strong>' + escapeHtml(row.k) + ':</strong> ' + escapeHtml(row.v) + '</div>';
        }).join("");
    }

    function setTcNextEnabledIfReady() {
        if (!tcNextBtn) {
            return;
        }

        var nameOk = !!(templateNameInput && templateNameInput.value.trim().length > 0);
        var urlOk = !!(isoUrlInput && looksLikeHttpUrl(isoUrlInput.value.trim()));
        var checkedOk = lastIsoOk && (lastIsoCheckedUrl === (isoUrlInput ? isoUrlInput.value.trim() : ""));
        var osOk = !!getTargetOs();
        var windowsOk = windowsFieldsAreReady();

        tcNextBtn.disabled = !(nameOk && urlOk && checkedOk && osOk && windowsOk);
    }

    function updateTcNextEnabled() {
        if (!tcNextBtn) {
            return;
        }

        if (tcCount === 0) {
            tcCount = tcTrack ? tcTrack.querySelectorAll(".content-page").length : 0;
        }

        if (tcIndex >= (tcCount - 1)) {
            tcNextBtn.textContent = isCreatingTemplate ? "Creating..." : "Create template";
            tcNextBtn.disabled = isCreatingTemplate;
            return;
        }

        tcNextBtn.textContent = "Next";

        if (tcIndex === 0) {
            setTcNextEnabledIfReady();
            return;
        }

        tcNextBtn.disabled = false;
    }

    function populateSaved(selectEl, items, emptyLabel) {
        if (!selectEl) {
            return;
        }

        while (selectEl.options.length > 0) {
            selectEl.remove(0);
        }

        var empty = document.createElement("option");
        empty.value = "";
        empty.textContent = emptyLabel;
        empty.selected = true;
        selectEl.appendChild(empty);

        (items || []).forEach(function (item) {
            var opt = document.createElement("option");
            opt.value = item.url || "";
            opt.textContent = item.label || item.filename || item.url || "Saved item";
            selectEl.appendChild(opt);
        });

        syncCustomSelectForElement(selectEl);
    }

    function addSavedOption(selectEl, item) {
        if (!selectEl || !item || !item.url) {
            return;
        }

        var normalized = normalizeUrl(item.url);
        var existing = Array.prototype.slice.call(selectEl.options).some(function (opt) {
            return normalizeUrl(opt.value) === normalized;
        });

        if (!existing) {
            var opt = document.createElement("option");
            opt.value = item.url;
            opt.textContent = item.label || item.filename || item.url;
            selectEl.appendChild(opt);
        }

        selectEl.value = item.url;
        syncCustomSelectForElement(selectEl);
    }

    function resetSoftwareState() {
        softwareItems = [];
        renderSoftwareList();
        setSwStatus("", "");
        setValidateStatus("", "");
    }

    function refreshInferredStrategies() {
        var targetOs = getTargetOs();
        softwareItems.forEach(function (item) {
            item.install_strategy = inferInstallStrategy(item, targetOs);
            if (targetOs !== "windows" || item.install_strategy !== "native_installer") {
                item.silent_args = "";
            }
        });
        renderSoftwareList();
    }

    function createTemplateDefinition() {
        if (isCreatingTemplate) {
            return;
        }

        var payload = buildTemplateCreatePayload();
        var csrftoken = getCookie("csrftoken");

        if (!payload.template_name) {
            setCreateStatus("Template name is required.", "error");
            return;
        }
        if (!payload.build_profile || !payload.target_os) {
            setCreateStatus("Build profile is required.", "error");
            return;
        }
        if (!looksLikeHttpUrl(payload.iso_url)) {
            setCreateStatus("A valid ISO URL is required.", "error");
            return;
        }
        if (!lastIsoOk || lastIsoCheckedUrl !== payload.iso_url) {
            setCreateStatus("Re-check ISO URL before creating the template build job.", "error");
            return;
        }
        if (!windowsFieldsAreReady()) {
            setCreateStatus("Windows fields are required for a Windows template.", "error");
            return;
        }

        isCreatingTemplate = true;
        stopBuildPolling();
        activeBuildJobId = null;
        setBuildStatus(null);
        if (tcNextBtn) {
            tcNextBtn.disabled = true;
            tcNextBtn.textContent = "Creating...";
        }
        if (tcBackBtn) {
            tcBackBtn.disabled = true;
        }
        setCreateStatus("Queueing template build...", "");
        setValidateStatus("", "");

        fetch("/api/template/create/", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-CSRFToken": csrftoken || ""
            },
            body: JSON.stringify(payload)
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, status: res.status, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok || !result.data || result.data.ok !== true) {
                    throw new Error((result.data && result.data.error) ? result.data.error : ("Create request failed (HTTP " + result.status + ")"));
                }

                var data = result.data;
                renderOverview(data.normalized || null);
                activeBuildJobId = data.job && data.job.id ? data.job.id : null;
                setCreateStatus("Build job queued.", "ok");
                if (activeBuildJobId) {
                    fetchBuildStatus();
                }
                if (data.warnings && data.warnings.length > 0) {
                    setValidateStatus(data.warnings.join(" "), "warn");
                }
            })
            .catch(function (err) {
                setCreateStatus("Create failed: " + String(err && err.message ? err.message : err), "error");
            })
            .finally(function () {
                isCreatingTemplate = false;
                if (tcBackBtn) {
                    tcBackBtn.disabled = false;
                }
                updateTcNextEnabled();
            });
    }

    function fetchBuildStatus() {
        if (!activeBuildJobId) {
            return;
        }

        fetch("/api/template/builds/" + encodeURIComponent(activeBuildJobId) + "/status/", {
            method: "GET",
            credentials: "same-origin",
            headers: { "Accept": "application/json" }
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, status: res.status, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok || !result.data || result.data.ok !== true) {
                    throw new Error((result.data && result.data.error) ? result.data.error : ("Status request failed (HTTP " + result.status + ")"));
                }

                var job = result.data.job || null;
                setBuildStatus(job);
                if (!job) {
                    return;
                }
                if (job.status === "succeeded") {
                    setCreateStatus("Build completed successfully.", "ok");
                    stopBuildPolling();
                    return;
                }
                if (job.status === "failed" || job.status === "canceled") {
                    setCreateStatus("Build finished with status: " + job.status + ".", "error");
                    stopBuildPolling();
                    return;
                }

                stopBuildPolling();
                buildPollTimer = setTimeout(fetchBuildStatus, 3000);
            })
            .catch(function (err) {
                setCreateStatus("Build status check failed: " + String(err && err.message ? err.message : err), "error");
                stopBuildPolling();
            });
    }

    function checkIsoUrl() {
        if (!isoUrlInput || !isoCheckBtn) {
            return;
        }

        var url = isoUrlInput.value.trim();
        lastIsoCheckedUrl = null;
        lastIsoOk = false;
        lastIsoData = null;
        clearIsoDetails();

        if (!looksLikeHttpUrl(url)) {
            setIsoStatus("Enter a valid http(s) ISO URL.", "error");
            setTcNextEnabledIfReady();
            return;
        }

        setIsoStatus("Checking ISO...", "");
        isoCheckBtn.disabled = true;

        fetch("/api/iso/inspect/?url=" + encodeURIComponent(url), {
            method: "GET",
            credentials: "same-origin",
            headers: { "Accept": "application/json" }
        })
            .then(function (res) {
                if (!res.ok) {
                    throw new Error("HTTP " + res.status);
                }
                return res.json();
            })
            .then(function (data) {
                if (!data || data.ok !== true) {
                    throw new Error((data && data.error) ? data.error : "Invalid ISO URL");
                }

                lastIsoCheckedUrl = data.final_url || url;
                lastIsoOk = true;
                lastIsoData = data;
                applyIsoDetails(data);

                var item = {
                    url: data.final_url || url,
                    filename: data.filename || "",
                    label: data.filename || (data.final_url || url)
                };

                addSavedOption(isoSavedSelect, item);
                isoUrlInput.value = item.url;
                setIsoStatus("", "");
                setTcNextEnabledIfReady();
                renderOverview(null);
            })
            .catch(function (err) {
                clearIsoDetails();
                setIsoStatus("Check failed: " + String(err && err.message ? err.message : err), "error");
                setTcNextEnabledIfReady();
            })
            .finally(function () {
                isoCheckBtn.disabled = false;
            });
    }

    function handleSoftwareInputCheck() {
        if (!swInput || !swCheckBtn) {
            return;
        }

        var raw = swInput.value.trim();
        var targetOs = getTargetOs();
        if (!raw) {
            setSwStatus("Enter a software URL or package name.", "error");
            return;
        }
        if (!targetOs) {
            setSwStatus("Select build profile before adding software.", "error");
            return;
        }

        setSwStatus("Checking...", "");
        swCheckBtn.disabled = true;

        if (looksLikeHttpUrl(raw)) {
            fetch("/api/software/inspect/?url=" + encodeURIComponent(raw), {
                method: "GET",
                credentials: "same-origin",
                headers: { "Accept": "application/json" }
            })
                .then(function (res) {
                    if (!res.ok) {
                        throw new Error("HTTP " + res.status);
                    }
                    return res.json();
                })
                .then(function (data) {
                    if (!data || data.ok !== true) {
                        throw new Error((data && data.error) ? data.error : "Invalid software URL");
                    }

                    var finalUrl = data.final_url || raw;
                    var shortName = data.filename || finalUrl;
                    var artifactType = inferArtifactTypeFromName(shortName || finalUrl);
                    var compatibilityError = getSoftwareCompatibilityError(
                        {
                            kind: "url",
                            url: finalUrl,
                            label: shortName,
                            artifact_type: artifactType
                        },
                        targetOs
                    );
                    if (compatibilityError) {
                        setSwStatus(compatibilityError, "error");
                        return;
                    }

                    upsertSoftwareItem({
                        key: keyForUrl(finalUrl),
                        kind: "url",
                        label: shortName,
                        url: finalUrl,
                        filename: data.filename || "",
                        artifact_type: artifactType,
                        install_strategy: inferInstallStrategy(
                            { kind: "url", artifact_type: artifactType },
                            targetOs
                        ),
                        isSaved: false
                    });

                    renderSoftwareList();
                    swInput.value = "";
                    setSwStatus("", "");
                    setValidateStatus("", "");
                    renderOverview(null);
                })
                .catch(function (err) {
                    setSwStatus("Check failed: " + String(err && err.message ? err.message : err), "error");
                })
                .finally(function () {
                    swCheckBtn.disabled = false;
                });
            return;
        }

        var pkg = raw.toLowerCase();
        if (!PACKAGE_RE.test(pkg)) {
            setSwStatus("Invalid package name. Use lowercase letters, numbers, +, . or -.", "error");
            swCheckBtn.disabled = false;
            return;
        }

        var packageCompatibilityError = getSoftwareCompatibilityError(
            {
                kind: "package",
                label: pkg,
                artifact_type: "package"
            },
            targetOs
        );
        if (packageCompatibilityError) {
            setSwStatus(packageCompatibilityError, "error");
            swCheckBtn.disabled = false;
            return;
        }

        var os = targetOs;
        upsertSoftwareItem({
            key: keyForPackage(pkg),
            kind: "package",
            label: pkg,
            url: "",
            filename: "",
            artifact_type: "package",
            install_strategy: inferInstallStrategy(
                { kind: "package", artifact_type: "package" },
                os
            ),
            isSaved: false
        });

        renderSoftwareList();
        swInput.value = "";
        setSwStatus("", "");
        setValidateStatus("", "");
        renderOverview(null);
        swCheckBtn.disabled = false;
    }

    function fetchSavedLists() {
        if (isoSavedSelect) {
            fetch("/api/iso/saved/", {
                method: "GET",
                credentials: "same-origin",
                headers: { "Accept": "application/json" }
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    populateSaved(isoSavedSelect, data && data.items ? data.items : [], "Select saved ISO");
                })
                .catch(function () {
                    populateSaved(isoSavedSelect, [], "Select saved ISO");
                });
        }

        fetch("/api/software/saved/", {
            method: "GET",
            credentials: "same-origin",
            headers: { "Accept": "application/json" }
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                var items = data && data.items ? data.items : [];
                items.forEach(function (item) {
                    var url = item.url || "";
                    if (!url) {
                        return;
                    }

                    var shortName = item.filename || item.label || url;
                    var artifactType = inferArtifactTypeFromName(shortName || url);
                    var targetOs = getTargetOs();
                    var existing = findSoftwareItemByKey(keyForUrl(url));
                    if (existing) {
                        existing.label = existing.label || shortName;
                        existing.url = existing.url || url;
                        existing.artifact_type = existing.artifact_type || artifactType;
                        existing.install_strategy = existing.install_strategy || inferInstallStrategy(
                            { kind: "url", artifact_type: artifactType },
                            targetOs
                        );
                        existing.isSaved = true;
                    } else {
                        softwareItems.push({
                            key: keyForUrl(url),
                            kind: "url",
                            label: shortName,
                            url: url,
                            filename: item.filename || "",
                            artifact_type: artifactType,
                            install_strategy: inferInstallStrategy(
                                { kind: "url", artifact_type: artifactType },
                                targetOs
                            ),
                            isSaved: true,
                            selected: false
                        });
                    }
                });
                renderSoftwareList();
            })
            .catch(function () {
                renderSoftwareList();
            });
    }

    function openModal() {
        if (!modal) {
            return;
        }

        modal.classList.remove("hidden");

        setScene("vm");
        setVmPage(0);
        setTcPage(0);

        lastIsoCheckedUrl = null;
        lastIsoOk = false;
        lastIsoData = null;

        setIsoStatus("", "");
        setSwStatus("", "");
        setValidateStatus("", "");
        setCreateStatus("", "");
        setBuildStatus(null);
        stopBuildPolling();
        activeBuildJobId = null;
        clearIsoDetails();
        resetSoftwareState();
        isCreatingTemplate = false;

        if (swInput) {
            swInput.value = "";
        }
        if (buildProfileSelect) {
            resetSelectToPlaceholder(buildProfileSelect);
        }
        if (winVirtioUrlInput) {
            winVirtioUrlInput.value = "";
        }
        if (winAdminUsernameInput) {
            winAdminUsernameInput.value = "";
        }
        if (winAdminPasswordInput) {
            winAdminPasswordInput.value = "";
        }
        if (winImageSelectorTypeInput) {
            winImageSelectorTypeInput.value = "image_name";
        }
        if (winImageSelectorValueInput) {
            winImageSelectorValueInput.value = "";
        }
        if (winFirmwareProfileInput) {
            winFirmwareProfileInput.value = "bios_legacy";
        }
        toggleWindowsOptions();
        syncAllCustomSelects();
        closeAllCustomSelects(null);

        if (vmNextBtn) {
            vmNextBtn.disabled = true;
        }

        if (tcTrack) {
            tcCount = tcTrack.querySelectorAll(".content-page").length;
        }

        if (tcNextBtn) {
            tcNextBtn.disabled = true;
            tcNextBtn.textContent = "Next";
        }
        if (tcBackBtn) {
            tcBackBtn.disabled = false;
        }

        renderOverview(null);
        fetchSavedLists();
    }

    function closeModal() {
        if (modal) {
            modal.classList.add("hidden");
        }
        stopBuildPolling();
        closeAllCustomSelects(null);
    }

    function onCloseClick(e) {
        var target = e.target;
        if (target && target.hasAttribute("data-close")) {
            closeModal();
            return;
        }

        if (target && target.closest(".custom-select")) {
            return;
        }

        closeAllCustomSelects(null);
    }

    function onKeyDown(e) {
        if (!modal || modal.classList.contains("hidden")) {
            return;
        }
        if (e.key === "Escape") {
            var hasOpenCustom = customSelectEntries.some(function (entry) {
                return entry.menu.classList.contains("is-open");
            });
            if (hasOpenCustom) {
                closeAllCustomSelects(null);
                return;
            }
            closeModal();
        }
    }

    initCustomSelects();
    toggleWindowsOptions();

    if (openBtn) {
        openBtn.addEventListener("click", openModal);
    }

    if (modal) {
        modal.addEventListener("click", onCloseClick);
    }

    document.addEventListener("keydown", onKeyDown);

    if (toTcBtn) {
        toTcBtn.addEventListener("click", function () {
            setScene("tc");
        });
    }

    if (tcBackBtn) {
        tcBackBtn.addEventListener("click", function () {
            if (tcIndex > 0) {
                setTcPage(tcIndex - 1);
                return;
            }
            setScene("vm");
        });
    }

    if (tcNextBtn) {
        tcNextBtn.addEventListener("click", function () {
            if (tcCount === 0 && tcTrack) {
                tcCount = tcTrack.querySelectorAll(".content-page").length;
            }
            if (tcIndex < (tcCount - 1)) {
                setTcPage(tcIndex + 1);
                return;
            }
            createTemplateDefinition();
        });
    }

    if (templateNameInput) {
        templateNameInput.addEventListener("input", function () {
            setTcNextEnabledIfReady();
            renderOverview(null);
        });
    }

    if (isoSavedSelect && isoUrlInput) {
        isoSavedSelect.addEventListener("change", function () {
            if (isoSavedSelect.value) {
                isoUrlInput.value = isoSavedSelect.value;
            }
            lastIsoCheckedUrl = null;
            lastIsoOk = false;
            lastIsoData = null;
            setIsoStatus("", "");
            clearIsoDetails();
            setTcNextEnabledIfReady();
            renderOverview(null);
        });
    }

    if (isoUrlInput) {
        isoUrlInput.addEventListener("input", function () {
            lastIsoCheckedUrl = null;
            lastIsoOk = false;
            lastIsoData = null;
            setIsoStatus("", "");
            clearIsoDetails();
            setTcNextEnabledIfReady();
            renderOverview(null);
        });

        isoUrlInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                e.preventDefault();
                checkIsoUrl();
            }
        });
    }

    if (isoCheckBtn) {
        isoCheckBtn.addEventListener("click", checkIsoUrl);
    }

    if (swCheckBtn) {
        swCheckBtn.addEventListener("click", handleSoftwareInputCheck);
    }

    if (swInput) {
        swInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                e.preventDefault();
                handleSoftwareInputCheck();
            }
        });

        swInput.addEventListener("input", function () {
            setSwStatus("", "");
            setValidateStatus("", "");
        });
    }

    [winVirtioUrlInput, winAdminUsernameInput, winAdminPasswordInput, winImageSelectorTypeInput, winImageSelectorValueInput, winFirmwareProfileInput].forEach(function (inputEl) {
        if (!inputEl) {
            return;
        }
        inputEl.addEventListener("input", function () {
            setTcNextEnabledIfReady();
            renderOverview(null);
        });
    });

    if (buildProfileSelect) {
        buildProfileSelect.addEventListener("change", function () {
            toggleWindowsOptions();
            setTcNextEnabledIfReady();
            refreshInferredStrategies();
            var clearedCount = clearIncompatibleSelectionsForTarget();
            if (clearedCount > 0) {
                setSwStatus(
                    "Removed " + String(clearedCount) + " incompatible software selection" + (clearedCount === 1 ? "" : "s") + ".",
                    "warn"
                );
            } else {
                setSwStatus("", "");
            }
            setValidateStatus("", "");
            renderOverview(null);
            renderSoftwareList();
            syncCustomSelectForElement(buildProfileSelect);
        });
    }

    if (swSavedBox) {
        swSavedBox.addEventListener("click", function (e) {
            var removeBtn = e.target.closest("[data-software-remove]");
            if (removeBtn) {
                var removeKey = removeBtn.getAttribute("data-software-remove");
                var removeItem = findSoftwareItemByKey(removeKey);
                if (removeItem) {
                    removeItem.selected = false;
                    renderSoftwareList();
                    setSwStatus("", "");
                    setValidateStatus("", "");
                    renderOverview(null);
                }
                return;
            }

            var selectBtn = e.target.closest("[data-software-select]");
            if (!selectBtn) {
                return;
            }

            var key = selectBtn.getAttribute("data-software-select");
            var item = findSoftwareItemByKey(key);
            if (!item) {
                return;
            }

            var targetOs = getTargetOs();
            if (!targetOs) {
                setSwStatus("Select build profile before selecting software.", "error");
                return;
            }

            var compatibilityError = getSoftwareCompatibilityError(item, targetOs);
            if (compatibilityError) {
                setSwStatus(compatibilityError, "error");
                return;
            }

            item.selected = true;
            renderSoftwareList();
            setSwStatus("", "");
            setValidateStatus("", "");
            renderOverview(null);
        });
    }

})();

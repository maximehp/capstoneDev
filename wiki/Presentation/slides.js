const slideFiles = [
  "slides/01-capstone-in-cit-applied-cybersecurity.html",
  "slides/02-what-we-built.html",
  "slides/03-how-the-pieces-connect.html",
  "slides/04-infrastructure.html",
  "slides/05-base-infrastructure.html",
  "slides/06-nas-hardware.html",
  "slides/07-pbs-architecture.html",
  "slides/08-replication-architecture.html",
  "slides/28-iac-ci-cd.html",
  "slides/29-forgejo-and-runners.html",
  "slides/30-iac-full-pipeline.html",
  "slides/31-three-way-data-split.html",
  "slides/32-minio.html",
  "slides/33-packer.html",
  "slides/34-terraform.html",
  "slides/35-ansible.html",
  "slides/36-what-s-still-needed.html",
  "slides/09-networking.html",
  "slides/09-networking-overview.html",
  "slides/10-subnetting.html",
  "slides/11-connectivity.html",
  "slides/12-proxmox-sdn-setup.html",
  "slides/12-networking-troubleshooting.html",
  "slides/12-networking-recommendations.html",
  "slides/13-security.html",
  "slides/14-siem-overview.html",
  "slides/15-log-ingestion-wazuh.html",
  "slides/16-log-analysis-graylog.html",
  "slides/17-automation-shuffle.html",
  "slides/18-intelligence-enrichment-misp.html",
  "slides/19-virtual-firewall-with-opnsense.html",
  "slides/20-vulnerability-scanning-with-kali-linux.html",
  "slides/20-security-whats-still-needed.html",
  "slides/21-monitoring.html",
  "slides/22-nagios-and-agents.html",
  "slides/23-prometheus.html",
  "slides/24-exporters-and-connections.html",
  "slides/25-grafana-and-data-sources.html",
  "slides/26-dashboards-metrics-and-alerts.html",
  "slides/27-potential-future-improvements.html",
  "slides/37-web-development.html",
  "slides/37-development-summary.html",
  "slides/38-frontend-architecture.html",
  "slides/39-user-flow-and-interaction.html",
  "slides/40-backend-architecture.html",
  "slides/41-api-flow-and-execution.html",
  "slides/42-development-whats-still-needed.html",
  "slides/43-conclusion.html",
  "slides/43-from-shared-hardware-to-rebuildable-services.html",
  "slides/44-questions.html"
];

function themeForSlide(file) {
  const slideNumber = Number(file.match(/slides\/(\d+)-/)?.[1]);

  if (slideNumber >= 4 && slideNumber <= 8) return "infrastructure";
  if (slideNumber >= 9 && slideNumber <= 12) return "networking";
  if (slideNumber >= 13 && slideNumber <= 20) return "security";
  if (slideNumber >= 21 && slideNumber <= 27) return "monitoring";
  if (slideNumber >= 28 && slideNumber <= 36) return "infrastructure";
  if (slideNumber >= 37 && slideNumber <= 42) return "development";

  return "blue";
}

function applySlideThemes(root) {
  const sections = root.querySelectorAll("section");

  sections.forEach((section, index) => {
    section.classList.add(`theme-${themeForSlide(slideFiles[index])}`);
    section.dataset.slideFile = slideFiles[index];
  });
}

async function loadSpeakerNotes() {
  try {
    const response = await fetch("speaker-notes.yaml", { cache: "no-store" });
    if (!response.ok || !window.jsyaml) {
      return {};
    }

    return window.jsyaml.load(await response.text())?.slides || {};
  } catch {
    return {};
  }
}

function applySpeakerNotes(root, notesBySlide) {
  const sections = root.querySelectorAll("section");

  sections.forEach((section, index) => {
    const slideFile = slideFiles[index];
    const noteConfig = notesBySlide[slideFile];

    if (!noteConfig) {
      return;
    }

    if (noteConfig.speaker && !section.querySelector(".speaker")) {
      const speaker = document.createElement("div");
      speaker.className = "speaker";
      speaker.textContent = `Speaker: ${noteConfig.speaker}`;
      section.appendChild(speaker);
    }

    if (typeof noteConfig.notes === "string") {
      let notes = section.querySelector("aside.notes");
      if (!notes) {
        notes = document.createElement("aside");
        notes.className = "notes";
        section.appendChild(notes);
      }
      notes.textContent = noteConfig.notes.trim();
    }
  });
}

async function loadSlides() {
  const root = document.getElementById("slides-root");
  const [fragments, speakerNotes] = await Promise.all([
    Promise.all(slideFiles.map(async (file) => {
      const response = await fetch(file);
      if (!response.ok) {
        throw new Error("Unable to load " + file + ": " + response.status);
      }
      return response.text();
    })),
    loadSpeakerNotes(),
  ]);

  root.innerHTML = fragments.join("\n");
  applySlideThemes(root);
  applySpeakerNotes(root, speakerNotes);
}

const deck = new Reveal({
  hash: true,
  controls: false,
  progress: true,
  center: false,
  slideNumber: "c/t",
  transition: "slide",
  backgroundTransition: "fade",
  width: 1280,
  height: 720,
  margin: 0.04,
  minScale: 0.2,
  maxScale: 1.35,
  plugins: [RevealNotes],
});

await loadSlides();
deck.initialize();
window.deck = deck;

const isNotesReceiver = /receiver/i.test(window.location.search);
let activeVanta;
let activeVantaSection;

const colors = {
  background: 0x06101c,
  cyan: 0x45d8ff,
  green: 0x75f0a0,
  orange: 0xff886e,
  rose: 0xff6f7d,
  purple: 0xb48cff,
  security: 0x6e7aff,
};

function clearVantaBackground() {
  activeVanta?.destroy?.();
  activeVanta = undefined;
  activeVantaSection = undefined;

  const background = document.getElementById("vanta-background");
  if (background) {
    background.innerHTML = "";
  }
}

function vantaOptions(section, el) {
  const common = {
    el,
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    minHeight: 200.00,
    minWidth: 200.00,
    scale: 1.00,
    scaleMobile: 1.00,
  };

  if (section === "trunk") {
    if (!window.VANTA?.TRUNK || !window.p5) return undefined;

    return {
      factory: window.VANTA.TRUNK,
      options: {
        ...common,
        p5: window.p5,
        color: 0x176f93,
        backgroundColor: colors.background,
        spacing: 12.0,
        chaos: 1.8,
      },
    };
  }

  if (!window.THREE) {
    return undefined;
  }

  if (section === "infrastructure" && window.VANTA?.BIRDS) {
    return {
      factory: window.VANTA.BIRDS,
      options: {
        ...common,
        backgroundColor: colors.background,
        color1: colors.rose,
        color2: colors.cyan,
        colorMode: "variance",
        wingSpan: 25.00,
        speedLimit: 2.00,
        separation: 67.00,
        alignment: 35.00,
        cohesion: 17.00,
        quantity: 3.00,
      },
    };
  }

  if (section === "networking" && window.VANTA?.NET) {
    return {
      factory: window.VANTA.NET,
      options: {
        ...common,
        color: colors.purple,
        backgroundColor: colors.background,
        points: 11.00,
        maxDistance: 21.00,
        spacing: 17.00,
      },
    };
  }

  if (section === "security" && window.VANTA?.GLOBE) {
    return {
      factory: window.VANTA.GLOBE,
      options: {
        ...common,
        color: colors.security,
        color2: colors.cyan,
        backgroundColor: colors.background,
        size: 1.05,
        scale: 0.9,
        scaleMobile: 0.9,
      },
    };
  }

  if (section === "monitoring" && window.VANTA?.FOG) {
    return {
      factory: window.VANTA.FOG,
      options: {
        ...common,
        highlightColor: colors.orange,
        midtoneColor: 0x6C5570,
        lowlightColor: 0x4B2060,
        baseColor: colors.background,
        blurFactor: 0.36,
        speed: 0.35,
        zoom: 0.58,
        scale: 4.00,
        scaleMobile: 4.00,
      },
    };
  }

  if (section === "development" && window.VANTA?.WAVES) {
    return {
      factory: window.VANTA.WAVES,
      options: {
        ...common,
        color: 0x123f35,
        shininess: 28.00,
        waveHeight: 14.00,
        waveSpeed: 0.20,
        zoom: 0.82,
      },
    };
  }

  return undefined;
}

function updateVantaBackground(section) {
  const background = document.getElementById("vanta-background");

  if (isNotesReceiver) {
    clearVantaBackground();
    return;
  }

  if (!background || activeVantaSection === section) {
    activeVanta?.resize?.();
    return;
  }

  clearVantaBackground();

  const config = vantaOptions(section, background);
  if (!config) {
    return;
  }

  activeVanta = config.factory(config.options);
  activeVantaSection = section;

  if (section === "security") {
    activeVanta.cont?.position?.set(0, -20, 0);
    activeVanta.cont2?.position?.set(-26, 12, 0);
  }

  activeVanta.resize?.();
}

function resizeVantaBackground() {
  activeVanta?.resize?.();
}

function vantaForSlide(slide, theme) {
  if (!slide) {
    return "trunk";
  }

  if (
    slide.classList.contains("title-slide") ||
    slide.classList.contains("overview-slide") ||
    slide.classList.contains("vanta-fade-slide") ||
    slide.classList.contains("conclusion-slide") ||
    slide.classList.contains("closing-slide")
  ) {
    return "trunk";
  }

  if (slide.classList.contains("network")) return "networking";
  if (slide.classList.contains("security")) return "security";
  if (slide.classList.contains("monitoring")) return "monitoring";
  if (slide.classList.contains("dev")) return "development";
  if (slide.classList.contains("infra") || slide.classList.contains("iac")) return "infrastructure";

  if (theme === "networking") return "networking";
  if (theme === "security") return "security";
  if (theme === "monitoring") return "monitoring";
  if (theme === "development") return "development";
  if (theme === "infrastructure") return "infrastructure";

  return "trunk";
}

const speakerOverlay = document.getElementById("speaker-overlay");
let notesServerPost = () => {};

function updateSpeakerOverlay() {
  const currentSlide = deck.getCurrentSlide();
  const speaker = currentSlide?.querySelector(".speaker");
  const themeClass = [...(currentSlide?.classList || [])].find((className) => className.startsWith("theme-"));
  const theme = themeClass?.replace("theme-", "") || "blue";
  const vantaSection = vantaForSlide(currentSlide, theme);

  speakerOverlay.textContent = speaker?.textContent || "";
  document.body.dataset.theme = theme;
  document.body.dataset.vanta = vantaSection;
  updateVantaBackground(vantaSection);
  document.body.classList.toggle("title-background-active", currentSlide?.classList.contains("title-slide"));
  document.body.classList.toggle(
    "trunk-background-active",
    currentSlide?.classList.contains("overview-slide") ||
      currentSlide?.classList.contains("vanta-fade-slide") ||
      currentSlide?.classList.contains("conclusion-slide") ||
      currentSlide?.classList.contains("closing-slide")
  );
  document.body.classList.toggle("section-vanta-title-active", currentSlide?.classList.contains("section-break"));
  notesServerPost();
}

async function loadOptionalScript(src) {
  const response = await fetch(src, { cache: "no-store" });
  if (!response.ok) {
    return false;
  }

  const url = URL.createObjectURL(new Blob([await response.text()], { type: "text/javascript" }));

  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = url;
    script.onload = () => {
      URL.revokeObjectURL(url);
      resolve(true);
    };
    script.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(false);
    };
    document.head.appendChild(script);
  });
}

function isSpeakerNotesPreview() {
  return /receiver/i.test(window.location.search);
}

function hideQr() {
  document.getElementById("qr")?.remove();
}

function showQr(location) {
  if (isSpeakerNotesPreview()) {
    return;
  }

  hideQr();

  const container = document.createElement("div");
  container.id = "qr";
  container.style = "position:absolute;top:0;left:0;display:grid;background:#fff;color:#111;z-index:999;padding:10px;font-family:sans-serif;font-size:14px;";
  container.onclick = hideQr;

  const title = document.createElement("span");
  title.textContent = "Scan to open notes.";
  const qr = document.createElement("img");
  qr.src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(location)}`;
  qr.alt = "Speaker notes QR code";
  qr.style = "padding:5px";
  const hint = document.createElement("span");
  hint.textContent = "Click to close.";

  container.append(title, qr, hint);
  document.body.appendChild(container);
}

async function connectRevealNotesServer() {
  if (isSpeakerNotesPreview()) {
    return;
  }

  if (!/notes=true|qr=true/i.test(window.location.search) && window.location.port !== "1947") {
    return;
  }

  try {
    if (!window.io) {
      const loaded = await loadOptionalScript("/socket.io/socket.io.js");
      if (!loaded) {
        return;
      }
    }
  } catch {
    return;
  }

  const socket = window.io.connect(window.location.origin);
  const socketId = Math.random().toString().slice(2);
  const notesLocation = `${window.location.origin}/notes/${socketId}`;

  console.log(`View slide notes at ${notesLocation}`);

  if (/qr=true/i.test(window.location.search)) {
    showQr(notesLocation);
  }

  notesServerPost = () => {
    const slideElement = deck.getCurrentSlide();
    const notesElement = slideElement?.querySelector("aside.notes");
    const messageData = {
      notes: "",
      markdown: false,
      socketId,
      state: deck.getState(),
    };

    if (slideElement?.hasAttribute("data-notes")) {
      messageData.notes = slideElement.getAttribute("data-notes");
    }

    if (notesElement) {
      messageData.notes = notesElement.innerHTML;
      messageData.markdown = typeof notesElement.getAttribute("data-markdown") === "string";
    }

    socket.emit("statechanged", messageData);
  };

  socket.on("new-subscriber", (data) => {
    if (!data?.socketId || data.socketId === socketId) {
      hideQr();
      notesServerPost();
    }
  });

  socket.on("statechanged-speaker", (data) => {
    if (data?.state) {
      deck.setState(data.state);
    }
  });

  [
    "slidechanged",
    "fragmentshown",
    "fragmenthidden",
    "overviewhidden",
    "overviewshown",
    "paused",
    "resumed",
  ].forEach((eventName) => deck.on(eventName, notesServerPost));

  notesServerPost();
}

deck.on("ready", () => {
  updateSpeakerOverlay();
  connectRevealNotesServer();
});
deck.on("slidechanged", updateSpeakerOverlay);
deck.on("resize", resizeVantaBackground);
updateSpeakerOverlay();
requestAnimationFrame(() => {
  updateSpeakerOverlay();
  resizeVantaBackground();
});

document.addEventListener("keydown", (event) => {
  if (event.key.toLowerCase() === "f") {
    const root = document.documentElement;
    if (!document.fullscreenElement && root.requestFullscreen) {
      root.requestFullscreen();
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  }
});

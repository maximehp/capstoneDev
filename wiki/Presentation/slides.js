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
  "slides/10-subnetting.html",
  "slides/11-connectivity.html",
  "slides/12-proxmox-sdn-setup.html",
  "slides/13-security.html",
  "slides/14-siem-overview.html",
  "slides/15-log-ingestion-wazuh.html",
  "slides/16-log-analysis-graylog.html",
  "slides/17-automation-shuffle.html",
  "slides/18-intelligence-enrichment-misp.html",
  "slides/19-virtual-firewall-with-opnsense.html",
  "slides/20-vulnerability-scanning-with-kali-linux.html",
  "slides/21-monitoring.html",
  "slides/22-nagios-and-agents.html",
  "slides/23-prometheus.html",
  "slides/24-exporters-and-connections.html",
  "slides/25-grafana-and-data-sources.html",
  "slides/26-dashboards-metrics-and-alerts.html",
  "slides/27-potential-future-improvements.html",
  "slides/37-web-development.html",
  "slides/38-frontend-architecture.html",
  "slides/39-user-flow-and-interaction.html",
  "slides/40-backend-architecture.html",
  "slides/41-api-flow-and-execution.html",
  "slides/42-data-model-and-job-system.html",
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
  });
}

async function loadSlides() {
  const root = document.getElementById("slides-root");
  const fragments = await Promise.all(
    slideFiles.map(async (file) => {
      const response = await fetch(file);
      if (!response.ok) {
        throw new Error("Unable to load " + file + ": " + response.status);
      }
      return response.text();
    })
  );

  root.innerHTML = fragments.join("\n");
  applySlideThemes(root);
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

let titleVanta;

function initTitleBackground() {
  if (titleVanta) {
    return;
  }

  const titleBackground = document.getElementById("title-vanta-background");

  if (!titleBackground || !window.VANTA?.TRUNK || !window.p5) {
    return;
  }

  titleVanta = window.VANTA.TRUNK({
    el: titleBackground,
    p5: window.p5,
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    minHeight: 200.0,
    minWidth: 200.0,
    scale: 1.0,
    scaleMobile: 1.0,
    color: 0x176f93,
    backgroundColor: 0x06101c,
    spacing: 12.0,
    chaos: 1.8,
  });

  titleVanta.resize?.();
}

const speakerOverlay = document.getElementById("speaker-overlay");

function updateSpeakerOverlay() {
  const currentSlide = deck.getCurrentSlide();
  const speaker = currentSlide?.querySelector(".speaker");
  const themeClass = [...(currentSlide?.classList || [])].find((className) => className.startsWith("theme-"));

  speakerOverlay.textContent = speaker?.textContent || "";
  document.body.dataset.theme = themeClass?.replace("theme-", "") || "blue";
  document.body.classList.toggle("title-background-active", currentSlide?.classList.contains("title-slide"));
  document.body.classList.toggle("overview-background-active", currentSlide?.classList.contains("overview-slide"));
}

deck.on("ready", () => {
  updateSpeakerOverlay();
  initTitleBackground();
});
deck.on("slidechanged", updateSpeakerOverlay);
deck.on("resize", () => titleVanta?.resize?.());
updateSpeakerOverlay();
requestAnimationFrame(() => {
  initTitleBackground();
  updateSpeakerOverlay();
  titleVanta?.resize?.();
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

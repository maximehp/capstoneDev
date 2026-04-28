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
}

const deck = new Reveal({
  hash: true,
  controls: true,
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

const speakerOverlay = document.getElementById("speaker-overlay");

function updateSpeakerOverlay() {
  const speaker = deck.getCurrentSlide()?.querySelector(".speaker");
  speakerOverlay.textContent = speaker?.textContent || "";
}

deck.on("ready", updateSpeakerOverlay);
deck.on("slidechanged", updateSpeakerOverlay);
updateSpeakerOverlay();

document.addEventListener("click", (event) => {
  const blockedSelector = "a, button, input, textarea, select, label, .controls, .progress";

  if (event.target.closest(blockedSelector)) {
    return;
  }

  deck.next();
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

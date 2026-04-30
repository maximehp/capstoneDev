// pipeline-anim.js — JS pipeline diagram animator using RAF

const DOT_R          = 5;    // dot radius px
const DOT_SPEED      = 100;  // px per second — every leg moves at the same visual speed
const DOT_FADE       = 0.32; // portion of each line used to fade in/out
const DOT_UNDERLAP   = 12;   // px the dot travels beyond each connector edge
const PAUSE          = 700;  // ms pause after a box lights up
const INIT_PAUSE     = 420;  // ms pause on the first box
const LOOP_PAUSE     = 1500; // ms pause before restarting the loop
const BRANCH_STAGGER = 190;  // ms stagger between Ansible fan-out branches
const GLOW_HOLD      = 500;  // ms before a lit box begins fading back out
const GLOW_LEAD      = 0.14; // portion of the last line where the target glow starts early
const TRANSITION_MS  = 1500;  // ms to wait for the Reveal.js slide transition to finish

// ── Overlay ───────────────────────────────────────────────────────────────────

const overlay = document.createElement('div');
overlay.id = 'pipeline-dot-overlay';
overlay.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:9999;overflow:visible;';
document.body.appendChild(overlay);

// ── Utilities ─────────────────────────────────────────────────────────────────

const abortErr = () => new DOMException('Aborted', 'AbortError');
const isAbort  = (e) => e?.name === 'AbortError';

function sleep(ms, signal) {
  return new Promise((res, rej) => {
    if (signal?.aborted) return rej(abortErr());
    const t = setTimeout(res, ms);
    signal?.addEventListener('abort', () => { clearTimeout(t); rej(abortErr()); }, { once: true });
  });
}

function pt(el, side = 'center') {
  const r = el.getBoundingClientRect();
  switch (side) {
    case 'left':   return { x: r.left,                 y: (r.top + r.bottom) / 2 };
    case 'right':  return { x: r.right,                y: (r.top + r.bottom) / 2 };
    case 'top':    return { x: (r.left + r.right) / 2, y: r.top };
    case 'bottom': return { x: (r.left + r.right) / 2, y: r.bottom };
    default:       return { x: (r.left + r.right) / 2, y: (r.top + r.bottom) / 2 };
  }
}

function lerp(a, b, t) { return a + (b - a) * t; }

function lineOpacity(t) {
  const fade = Math.min(DOT_FADE, 0.5);
  const ease = (x) => x * x * (3 - 2 * x);
  if (t < fade) return ease(t / fade);
  if (t > 1 - fade) return ease((1 - t) / fade);
  return 1;
}

function underlapSegment(from, to) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const dist = Math.hypot(dx, dy);
  if (!dist) return { from, to };

  const ux = dx / dist;
  const uy = dy / dist;

  return {
    from: { x: from.x - ux * DOT_UNDERLAP, y: from.y - uy * DOT_UNDERLAP },
    to:   { x: to.x   + ux * DOT_UNDERLAP, y: to.y   + uy * DOT_UNDERLAP },
  };
}

function makeSegmentMask(from, to) {
  const pad = DOT_R + 16;
  const dx = Math.abs(to.x - from.x);
  const dy = Math.abs(to.y - from.y);
  const horizontal = dx >= dy;
  const left = horizontal ? Math.min(from.x, to.x) : from.x - pad;
  const top = horizontal ? from.y - pad : Math.min(from.y, to.y);
  const width = Math.max(1, horizontal ? dx : pad * 2);
  const height = Math.max(1, horizontal ? pad * 2 : dy);
  const mask = document.createElement('div');

  mask.style.cssText =
    `position:fixed;` +
    `left:${left}px;top:${top}px;` +
    `width:${width}px;height:${height}px;` +
    `overflow:hidden;pointer-events:none;`;
  overlay.appendChild(mask);

  return { mask, left, top };
}

function activeAccentColors() {
  const slide = window.deck?.getCurrentSlide?.() || document.querySelector('.reveal .slides section.present');
  const styles = getComputedStyle(slide || document.documentElement);
  const color = styles.getPropertyValue('--accent').trim() || '#45d8ff';
  const rgb = styles.getPropertyValue('--accent-rgb').trim();

  return {
    color,
    glow: rgb ? `rgba(${rgb}, 0.7)` : color,
  };
}

function makeDot(p, override = false) {
  const { color, glow } = override === true
    ? { color: '#f5c842', glow: 'rgba(245,200,66,0.7)' }
    : typeof override === 'string'
      ? { color: override, glow: override }
      : activeAccentColors();
  const d = document.createElement('div');
  d.style.cssText =
    `position:absolute;` +
    `width:${DOT_R * 2}px;height:${DOT_R * 2}px;border-radius:50%;` +
    `background:${color};` +
    `box-shadow:0 0 7px 3px ${glow};` +
    `left:${p.x - DOT_R}px;top:${p.y - DOT_R}px;` +
    `opacity:0;` +
    `pointer-events:none;`;
  overlay.appendChild(d);
  return d;
}

function clearOverlay() { overlay.innerHTML = ''; }

// Animate dot from `from` to `to` inside a real connector-gap mask.
function travelLeg(dot, maskInfo, from, to, durationMs, signal, onApproach) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(abortErr());
    const t0 = performance.now();
    let raf;
    let approached = false;

    const onAbort = () => {
      cancelAnimationFrame(raf);
      overlay.appendChild(dot);
      maskInfo.mask.remove();
      reject(abortErr());
    };
    signal?.addEventListener('abort', onAbort, { once: true });
    maskInfo.mask.appendChild(dot);

    function tick(now) {
      const t = Math.min(1, (now - t0) / durationMs);
      dot.style.left = (lerp(from.x, to.x, t) - maskInfo.left - DOT_R) + 'px';
      dot.style.top  = (lerp(from.y, to.y, t) - maskInfo.top - DOT_R) + 'px';
      dot.style.opacity = Math.max(0, lineOpacity(t)).toFixed(3);
      if (!approached && t >= 1 - GLOW_LEAD) {
        approached = true;
        onApproach?.();
      }
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        signal?.removeEventListener('abort', onAbort);
        overlay.appendChild(dot);
        maskInfo.mask.remove();
        resolve();
      }
    }

    raf = requestAnimationFrame(tick);
  });
}

// Walk dot along a series of waypoints at constant speed (DOT_SPEED px/s)
async function travel(dot, waypoints, signal, options = {}) {
  for (let i = 0; i < waypoints.length - 1; i++) {
    const a = waypoints[i];
    const b = waypoints[i + 1];
    const { from, to } = underlapSegment(a, b);
    const maskInfo = makeSegmentMask(a, b);
    const dist = Math.hypot(to.x - from.x, to.y - from.y);
    const dur  = Math.max(30, dist / DOT_SPEED * 1000);
    const onApproach = i === waypoints.length - 2 ? options.onApproach : undefined;
    await travelLeg(dot, maskInfo, from, to, dur, signal, onApproach);
  }
}

// ── Glow helpers ──────────────────────────────────────────────────────────────

const glowTimers = new WeakMap();

function lit(el, gold = false) {
  const className = gold ? 'lit-gold' : 'lit';
  if (el.classList.contains(className)) return;

  clearTimeout(glowTimers.get(el));
  el.classList.remove(gold ? 'lit' : 'lit-gold');
  el.classList.add(className);
  glowTimers.set(el, setTimeout(() => unlit(el), GLOW_HOLD));
}

function unlit(el) {
  clearTimeout(glowTimers.get(el));
  glowTimers.delete(el);
  el.classList.remove('lit', 'lit-gold');
}

const unlitAll = (slide) => slide.querySelectorAll('.lit,.lit-gold').forEach(unlit);

async function travelToward(dot, waypoints, signal, target, gold = false) {
  await travel(dot, waypoints, signal, {
    onApproach: () => lit(target, gold),
  });
  dot.remove();
  lit(target, gold);
}

// ── Packer ────────────────────────────────────────────────────────────────────

async function packerOnce(slide, signal) {
  const steps = [...slide.querySelectorAll('.pkr-pipeline .anim-step')];
  if (steps.length < 2) return;

  unlitAll(slide);
  lit(steps[0]);
  await sleep(INIT_PAUSE, signal);

  for (let i = 0; i < steps.length - 1; i++) {
    const gold = steps[i + 1].classList.contains('anim-step-gold');
    const from = pt(steps[i], 'bottom');
    const to   = pt(steps[i + 1], 'top');
    const dot  = makeDot(from, gold);
    await travel(dot, [from, to], signal);
    dot.remove();
    lit(steps[i + 1], gold);
    await sleep(PAUSE, signal);
  }

  await sleep(LOOP_PAUSE, signal);
}

// ── Terraform ─────────────────────────────────────────────────────────────────

async function terraformOnce(slide, signal) {
  const flow = slide.querySelector('.tf-flow');
  if (!flow) return;

  const init    = flow.querySelector('.tf-main-init');
  const destroy = flow.querySelector('.tf-destroy');
  const plan    = flow.querySelector('.tf-main-plan');
  const apply   = flow.querySelector('.tf-main-apply');
  const write   = flow.querySelector('.tf-main-write');

  if (!init || !plan || !apply || !write) return;

  unlitAll(slide);
  lit(init);
  await sleep(INIT_PAUSE, signal);

  const fork   = flow.querySelector('.tf-fork');
  const bpL    = flow.querySelector('.tf-bp-l');
  const bpR    = flow.querySelector('.tf-bp-r');
  const rejoin = flow.querySelector('.tf-rejoin');

  if (destroy && fork && bpL && bpR && rejoin) {
    // Up path: init right → fork center (row-3 corner) → bp-l center (row-1 corner) → destroy left
    const dot1 = makeDot(pt(init, 'right'));
    await travel(dot1, [
      pt(init,    'right'),
      pt(fork,    'center'),
      pt(bpL,     'center'),
      pt(destroy, 'left'),
    ], signal);
    dot1.remove();
    lit(destroy);
    await sleep(PAUSE, signal);

    // Down path: destroy right → bp-r center (row-1 corner) → rejoin center (row-3 corner) → plan left
    const dot2 = makeDot(pt(destroy, 'right'));
    await travel(dot2, [
      pt(destroy, 'right'),
      pt(bpR,     'center'),
      pt(rejoin,  'center'),
      pt(plan,    'left'),
    ], signal);
    dot2.remove();
  } else {
    const from = pt(init, 'right');
    const to   = pt(plan, 'left');
    const dot  = makeDot(from);
    await travel(dot, [from, to], signal);
    dot.remove();
  }

  lit(plan);
  await sleep(PAUSE, signal);

  // plan → apply
  const dot3 = makeDot(pt(plan, 'right'));
  await travel(dot3, [pt(plan, 'right'), pt(apply, 'left')], signal);
  dot3.remove();
  lit(apply);
  await sleep(PAUSE, signal);

  // apply → write (gold)
  const dot4 = makeDot(pt(apply, 'right'), true);
  await travel(dot4, [pt(apply, 'right'), pt(write, 'left')], signal);
  dot4.remove();
  lit(write, true);

  await sleep(LOOP_PAUSE, signal);
}

// ── Ansible ───────────────────────────────────────────────────────────────────

async function ansibleOnce(slide, signal) {
  const minio    = slide.querySelector('.ans-minio-card');
  const runner   = slide.querySelector('.ans-runner');
  const branches = [...slide.querySelectorAll('.ans-branch-wrap')];

  if (!minio || !runner || branches.length === 0) return;

  unlitAll(slide);
  lit(minio, true);
  await sleep(INIT_PAUSE, signal);

  // MinIO → Runner
  const minioRight = pt(minio,  'right');
  const runnerLeft = pt(runner, 'left');
  const hdot = makeDot(minioRight);
  await travel(hdot, [minioRight, runnerLeft], signal);
  hdot.remove();
  lit(runner);
  await sleep(PAUSE, signal);

  // Fan out to all roles — each dot exits the runner at the branch's own y level (purely horizontal)
  const runnerRightX = pt(runner, 'right').x;

  await Promise.all(branches.map(async (branch, i) => {
    await sleep(i * BRANCH_STAGGER, signal);
    const step = branch.querySelector('.anim-step');
    if (!step) return;
    const to   = pt(step, 'left');
    const from = { x: runnerRightX, y: to.y }; // same y as the branch, so path is horizontal
    const dot  = makeDot(from);
    await travel(dot, [from, to], signal);
    dot.remove();
    lit(step);
  }));

  await sleep(LOOP_PAUSE, signal);
}

// ── IAC Full Pipeline ─────────────────────────────────────────────────────────

async function iacOnce(slide, signal) {
  const steps = [...slide.querySelectorAll('.iac-step')];
  const minio = slide.querySelector('.iac-minio');
  if (steps.length < 2) return;

  const forgejo   = steps.find(s => s.querySelector('strong')?.textContent.includes('Forgejo'));
  const runner    = steps.find(s => s.querySelector('strong')?.textContent.includes('Act Runner'));
  const packer    = steps.find(s => s.querySelector('strong')?.textContent.includes('Packer'));
  const terraform = steps.find(s => s.querySelector('strong')?.textContent.includes('Terraform'));
  const ansible   = steps.find(s => s.querySelector('strong')?.textContent.includes('Ansible'));

  if (!forgejo || !runner || !packer || !terraform || !ansible) return;

  unlitAll(slide);
  lit(forgejo);
  await sleep(INIT_PAUSE, signal);

  // Vertical chain: Forgejo → Runner → Packer → Terraform
  for (const [src, dst] of [[forgejo, runner], [runner, packer], [packer, terraform]]) {
    const from = pt(src, 'bottom');
    const to   = pt(dst, 'top');
    const dot  = makeDot(from);
    await travelToward(dot, [from, to], signal, dst);
    await sleep(PAUSE, signal);
  }

  // At Terraform: parallel — down to Ansible AND left to MinIO (gold)
  const tfBottom = pt(terraform, 'bottom');
  const ansTop   = pt(ansible,   'top');

  const parallel = [(async () => {
    const dot = makeDot(tfBottom);
    await travelToward(dot, [tfBottom, ansTop], signal, ansible);
  })()];

  if (minio) {
    // Write path: Terraform left → horizontal at terraform y → down to minio center
    const tfLeft  = pt(terraform, 'left');
    const connW   = slide.querySelector('.iac-conn-h-write');
    const writeY  = connW ? pt(connW, 'center').y : tfLeft.y;
    const mRight  = pt(minio, 'right');
    const wFrom   = { x: tfLeft.x,  y: writeY };
    const wTo     = { x: mRight.x,  y: writeY };

    parallel.push((async () => {
      const dot = makeDot(wFrom, true);
      await travelToward(dot, [wFrom, wTo], signal, minio, true);
    })());
  }

  await Promise.all(parallel);

  // MinIO → Ansible (read, gold)
  if (minio) {
    await sleep(PAUSE, signal);
    const connR  = slide.querySelector('.iac-conn-h-read');
    const readY  = connR ? pt(connR, 'center').y : pt(ansible, 'center').y;
    const rFrom  = { x: pt(minio, 'right').x,   y: readY };
    const rTo    = { x: pt(ansible, 'left').x,   y: readY };
    const dot    = makeDot(rFrom, true);
    await travel(dot, [rFrom, rTo], signal);
    dot.remove();
  }

  await sleep(LOOP_PAUSE, signal);
}

// ── Frontend Pathway ─────────────────────────────────────────────────────────

async function frontendOnce(slide, signal) {
  const steps = [...slide.querySelectorAll('.frontend-pathway .anim-step')];
  if (steps.length < 2) return;

  unlitAll(slide);
  lit(steps[0]);
  await sleep(INIT_PAUSE, signal);

  for (let i = 0; i < steps.length - 1; i++) {
    const from = pt(steps[i], 'bottom');
    const to   = pt(steps[i + 1], 'top');
    const dot  = makeDot(from);
    await travelToward(dot, [from, to], signal, steps[i + 1]);
    await sleep(PAUSE, signal);
  }

  await sleep(LOOP_PAUSE, signal);
}

// ── PBS Architecture Pipeline ─────────────────────────────────────────────────

async function pbsOnce(slide, signal) {
  const steps  = [...slide.querySelectorAll('.pbs-pipeline > .anim-step')];
  const arrows = [...slide.querySelectorAll('.pbs-pipeline .pbs-conn-arrow')];
  if (steps.length < 2) return;

  unlitAll(slide);
  lit(steps[0]);
  await sleep(INIT_PAUSE, signal);

  for (let i = 0; i < steps.length - 1; i++) {
    const gold   = steps[i + 1].classList.contains('anim-step-gold');
    const lineY  = arrows[i] ? pt(arrows[i], 'center').y : pt(steps[i], 'right').y;
    const from   = { x: pt(steps[i],     'right').x, y: lineY };
    const to     = { x: pt(steps[i + 1], 'left').x,  y: lineY };
    const dot    = makeDot(from, gold);
    await travel(dot, [from, to], signal);
    dot.remove();
    lit(steps[i + 1], gold);
    await sleep(PAUSE, signal);
  }

  await sleep(LOOP_PAUSE, signal);
}

// ── Replication Architecture ──────────────────────────────────────────────────
async function repOnce(slide, signal) {
  const steps  = [...slide.querySelectorAll('.rep-pipeline > .anim-step')];
  const arrows = [...slide.querySelectorAll('.rep-pipeline .rep-conn-arrow')];
  if (steps.length < 2) return;

  unlitAll(slide);
  lit(steps[0]);
  await sleep(INIT_PAUSE, signal);

  for (let i = 0; i < steps.length - 1; i++) {
    const gold  = steps[i + 1].classList.contains('anim-step-gold');
    const lineY = arrows[i] ? pt(arrows[i], 'center').y : pt(steps[i], 'right').y;
    const from  = { x: pt(steps[i],     'right').x, y: lineY };
    const to    = { x: pt(steps[i + 1], 'left').x,  y: lineY };
    const dot   = makeDot(from, gold);
    await travel(dot, [from, to], signal);
    dot.remove();
    lit(steps[i + 1], gold);
    await sleep(PAUSE, signal);
  }

  await sleep(LOOP_PAUSE, signal);
}

// ── MinIO Pipeline ────────────────────────────────────────────────────────────

async function minioOnce(slide, signal) {
  const tfActor   = slide.querySelector('.minio-actor-tf');
  const store     = slide.querySelector('.minio-store-diagram');
  const ansActor  = slide.querySelector('.minio-actor-ans');
  const conns     = [...slide.querySelectorAll('.minio-conn')];
  const leftConn  = conns[0];
  const rightConn = conns[1];

  if (!tfActor || !store || !ansActor || !leftConn || !rightConn) return;

  unlitAll(slide);
  lit(tfActor);
  await sleep(INIT_PAUSE, signal);

  const tfRightX    = pt(tfActor, 'right').x;
  const storeLeftX  = pt(store,   'left').x;
  const storeRightX = pt(store,   'right').x;
  const ansLeftX    = pt(ansActor,'left').x;

  // Two dots — one per rail, each travelling along its own line's Y
  const leftRails = [...leftConn.querySelectorAll('.minio-conn-rail')];

  for (let i = 0; i < leftRails.length; i++) {
    const railY = pt(leftRails[i], 'center').y;
    const from  = { x: tfRightX,   y: railY };
    const to    = { x: storeLeftX, y: railY };
    const dot   = makeDot(from);
    await travel(dot, [from, to], signal);
    dot.remove();
    if (i < leftRails.length - 1) await sleep(PAUSE * 0.5, signal);
  }

  lit(store);
  await sleep(PAUSE, signal);

  // Gold dot along the right rail (vm_info.json read)
  const rightRail = rightConn.querySelector('.minio-conn-rail');
  const rRailY    = pt(rightRail, 'center').y;
  const rfrom     = { x: storeRightX, y: rRailY };
  const rto       = { x: ansLeftX,    y: rRailY };
  const rdot      = makeDot(rfrom, true);
  await travel(rdot, [rfrom, rto], signal);
  rdot.remove();
  lit(ansActor, true);

  await sleep(LOOP_PAUSE, signal);
}

// ── Monitoring Stack ──────────────────────────────────────────────────────────

async function monStackOnce(slide, signal) {
  const nodes = [...slide.querySelectorAll('.mon-stack-diagram .mon-node')];
  if (nodes.length < 2) return;

  unlitAll(slide);
  lit(nodes[0]);
  await sleep(INIT_PAUSE, signal);

  for (let i = 0; i < nodes.length - 1; i++) {
    const from = pt(nodes[i],     'right');
    const to   = pt(nodes[i + 1], 'left');
    const dot  = makeDot(from);
    await travel(dot, [from, to], signal);
    dot.remove();
    lit(nodes[i + 1]);
    await sleep(PAUSE, signal);
  }

  await sleep(LOOP_PAUSE, signal);
}

// ── Prometheus Flow ───────────────────────────────────────────────────────────

async function promFlowOnce(slide, signal) {
  const nodes = [...slide.querySelectorAll('.pf-node')];
  if (nodes.length < 2) return;

  unlitAll(slide);
  lit(nodes[0]);
  await sleep(INIT_PAUSE, signal);

  for (let i = 0; i < nodes.length - 1; i++) {
    const from = pt(nodes[i],     'right');
    const to   = pt(nodes[i + 1], 'left');
    const dot  = makeDot(from);
    await travel(dot, [from, to], signal);
    dot.remove();
    lit(nodes[i + 1]);
    await sleep(PAUSE, signal);
  }

  await sleep(LOOP_PAUSE, signal);
}

// ── Slide handler ─────────────────────────────────────────────────────────────

let ctrl = null;

function stopAnimation() {
  ctrl?.abort();
  ctrl = null;
  clearOverlay();
}

async function runLoop(fn, slide) {
  stopAnimation();
  const c = new AbortController();
  ctrl = c;
  slide.classList.add('js-animated');
  try {
    // Wait for the Reveal.js slide transition to finish before measuring DOM positions
    await sleep(TRANSITION_MS, c.signal);
    while (!c.signal.aborted) {
      unlitAll(slide);
      await fn(slide, c.signal);
    }
  } catch (e) {
    if (!isAbort(e)) console.warn('[pipeline-anim]', e);
  } finally {
    unlitAll(slide);
    clearOverlay();
    slide.classList.remove('js-animated');
  }
}

function handleSlide(slide) {
  if (!slide)                                { stopAnimation();                     return; }
  if (slide.querySelector('.pbs-pipeline')) { runLoop(pbsOnce,       slide);        return; }
  if (slide.querySelector('.rep-pipeline')) { runLoop(repOnce,       slide);        return; }
  if (slide.querySelector('.pkr-pipeline')) { runLoop(packerOnce,    slide);        return; }
  if (slide.querySelector('.tf-flow'))      { runLoop(terraformOnce, slide);        return; }
  if (slide.querySelector('.ans-fan'))      { runLoop(ansibleOnce,   slide);        return; }
  if (slide.querySelector('.iac-diagram-v')){ runLoop(iacOnce,       slide);        return; }
  if (slide.querySelector('.frontend-pathway')) { runLoop(frontendOnce, slide);      return; }
  if (slide.querySelector('.minio-diagram'))      { runLoop(minioOnce,     slide); return; }
  if (slide.querySelector('.mon-stack-diagram')) { runLoop(monStackOnce,  slide); return; }
  if (slide.querySelector('.prom-flow'))         { runLoop(promFlowOnce,  slide); return; }
  stopAnimation();
}

// ── Reveal.js integration ─────────────────────────────────────────────────────

function waitForDeck() {
  return new Promise(resolve => {
    if (window.deck) return resolve(window.deck);
    const id = setInterval(() => {
      if (window.deck) { clearInterval(id); resolve(window.deck); }
    }, 50);
  });
}

const deck = await waitForDeck();
deck.on('slidechanged', ({ currentSlide }) => handleSlide(currentSlide));

if (deck.isReady()) {
  handleSlide(deck.getCurrentSlide());
} else {
  deck.on('ready', () => handleSlide(deck.getCurrentSlide()));
}

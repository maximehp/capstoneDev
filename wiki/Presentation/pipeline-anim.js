// pipeline-anim.js — JS pipeline diagram animator using RAF

const DOT_R          = 5;    // dot radius px
const LEG_MS         = 460;  // ms per connector segment
const PAUSE          = 220;  // ms pause after a box lights up
const INIT_PAUSE     = 420;  // ms pause on the first box
const LOOP_PAUSE     = 1500; // ms pause before restarting the loop
const BRANCH_STAGGER = 190;  // ms stagger between Ansible fan-out branches

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

function makeDot(p, gold = false) {
  const color = gold ? '#f5c842' : '#45d8ff';
  const glow  = gold ? 'rgba(245,200,66,0.7)' : 'rgba(69,216,255,0.7)';
  const d = document.createElement('div');
  d.style.cssText =
    `position:fixed;` +
    `width:${DOT_R * 2}px;height:${DOT_R * 2}px;border-radius:50%;` +
    `background:${color};` +
    `box-shadow:0 0 7px 3px ${glow};` +
    `left:${p.x - DOT_R}px;top:${p.y - DOT_R}px;` +
    `pointer-events:none;`;
  overlay.appendChild(d);
  return d;
}

function clearOverlay() { overlay.innerHTML = ''; }

// Animate dot from `from` to `to` over `durationMs`, respecting abort signal
function travelLeg(dot, from, to, durationMs, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(abortErr());
    const t0 = performance.now();
    let raf;

    const onAbort = () => { cancelAnimationFrame(raf); reject(abortErr()); };
    signal?.addEventListener('abort', onAbort, { once: true });

    function tick(now) {
      const t = Math.min(1, (now - t0) / durationMs);
      dot.style.left = (lerp(from.x, to.x, t) - DOT_R) + 'px';
      dot.style.top  = (lerp(from.y, to.y, t) - DOT_R) + 'px';
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        signal?.removeEventListener('abort', onAbort);
        resolve();
      }
    }

    raf = requestAnimationFrame(tick);
  });
}

// Walk dot along a series of waypoints, one leg at a time
async function travel(dot, waypoints, signal) {
  for (let i = 0; i < waypoints.length - 1; i++) {
    await travelLeg(dot, waypoints[i], waypoints[i + 1], LEG_MS, signal);
  }
}

// ── Glow helpers ──────────────────────────────────────────────────────────────

const lit     = (el, gold = false) => el.classList.add(gold ? 'lit-gold' : 'lit');
const unlit   = (el) => el.classList.remove('lit', 'lit-gold');
const unlitAll = (slide) => slide.querySelectorAll('.lit,.lit-gold').forEach(unlit);

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
  const vconnL  = flow.querySelector('.tf-vconn-l');
  const vconnR  = flow.querySelector('.tf-vconn-r');
  const plan    = flow.querySelector('.tf-main-plan');
  const apply   = flow.querySelector('.tf-main-apply');
  const write   = flow.querySelector('.tf-main-write');

  if (!init || !plan || !apply || !write) return;

  unlitAll(slide);
  lit(init);
  await sleep(INIT_PAUSE, signal);

  if (destroy && vconnL && vconnR) {
    // Up path: init top → right to vconn-l center x → up to destroy y → into destroy
    const initTop  = pt(init,    'top');
    const vLx      = pt(vconnL,  'center').x;
    const destC    = pt(destroy, 'center');
    const corner1  = { x: vLx, y: initTop.y };
    const corner2  = { x: vLx, y: destC.y };
    const destLeft = { x: pt(destroy, 'left').x, y: destC.y };

    const dot1 = makeDot(initTop);
    await travel(dot1, [initTop, corner1, corner2, destLeft], signal);
    dot1.remove();
    lit(destroy);
    await sleep(PAUSE, signal);

    // Down path: destroy right → right to vconn-r center x → down to plan y → into plan
    const destRight = pt(destroy, 'right');
    const vRx       = pt(vconnR,  'center').x;
    const planLeft  = pt(plan,    'left');
    const corner3   = { x: vRx, y: destRight.y };
    const corner4   = { x: vRx, y: planLeft.y };

    const dot2 = makeDot(destRight);
    await travel(dot2, [destRight, corner3, corner4, planLeft], signal);
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

  // Fan out to all roles simultaneously with per-branch stagger
  const runnerRight = pt(runner, 'right');

  await Promise.all(branches.map(async (branch, i) => {
    await sleep(i * BRANCH_STAGGER, signal);
    const step = branch.querySelector('.anim-step');
    if (!step) return;
    const to     = pt(step, 'left');
    const corner = { x: to.x, y: runnerRight.y };
    const dot    = makeDot({ x: runnerRight.x, y: runnerRight.y });
    await travel(dot, [runnerRight, corner, to], signal);
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
    await travel(dot, [from, to], signal);
    dot.remove();
    lit(dst);
    await sleep(PAUSE, signal);
  }

  // At Terraform: parallel — down to Ansible AND left to MinIO (gold)
  const tfBottom = pt(terraform, 'bottom');
  const ansTop   = pt(ansible,   'top');

  const parallel = [(async () => {
    const dot = makeDot(tfBottom);
    await travel(dot, [tfBottom, ansTop], signal);
    dot.remove();
    lit(ansible);
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
      await travel(dot, [wFrom, wTo], signal);
      dot.remove();
      lit(minio, true);
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
  if (slide.querySelector('.pkr-pipeline')) { runLoop(packerOnce,    slide);        return; }
  if (slide.querySelector('.tf-flow'))      { runLoop(terraformOnce, slide);        return; }
  if (slide.querySelector('.ans-fan'))      { runLoop(ansibleOnce,   slide);        return; }
  if (slide.querySelector('.iac-diagram-v')){ runLoop(iacOnce,       slide);        return; }
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

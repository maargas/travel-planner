// Rotating Earth, orthographic projection. Coarse continent outlines as [lat, lon].
const LAND = [
  // Africa
  [[35,-6],[37,10],[31,32],[23,35],[12,43],[11,51],[-1,42],[-12,40],[-26,33],[-34,26],[-34,18],[-23,14],[-12,13],[-5,9],[4,9],[6,-3],[10,-15],[20,-17],[28,-13]],
  // Europe
  [[36,-9],[43,-9],[48,-5],[51,2],[58,5],[63,5],[71,25],[66,40],[59,38],[55,30],[47,38],[41,29],[40,20],[38,15],[43,13],[44,4],[36,-6]],
  // Asia
  [[41,29],[47,38],[56,45],[66,60],[73,80],[72,110],[70,140],[66,170],[59,163],[52,141],[43,132],[36,126],[31,122],[22,114],[10,105],[1,104],[8,98],[16,95],[22,90],[21,72],[24,67],[25,57],[13,45],[20,39],[30,35],[37,36]],
  // North America
  [[70,-165],[71,-155],[70,-130],[69,-100],[73,-80],[63,-65],[52,-56],[45,-64],[40,-74],[31,-81],[25,-80],[29,-95],[21,-97],[16,-95],[19,-105],[27,-114],[34,-120],[42,-125],[49,-125],[58,-137],[60,-148],[59,-162]],
  // South America
  [[12,-72],[11,-62],[8,-52],[0,-50],[-6,-35],[-13,-38],[-23,-41],[-33,-53],[-41,-63],[-51,-69],[-54,-66],[-47,-75],[-37,-73],[-23,-71],[-14,-76],[-5,-81],[2,-79],[8,-77]],
  // Australia
  [[-11,131],[-12,142],[-19,147],[-27,153],[-38,150],[-38,141],[-32,134],[-34,123],[-31,115],[-22,114],[-17,123],[-14,129]],
];

const GREENLAND = [[[83,-30],[76,-20],[70,-22],[60,-44],[67,-53],[76,-70],[81,-60]]];

export function mountGlobe(canvas, opts = {}) {
  const ctx = canvas.getContext('2d');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let spin = opts.startLon ?? -50;
  let raf = null;

  const rad = (d) => (d * Math.PI) / 180;

  function project(lat, lon, r, cx, cy) {
    const p = rad(lat);
    const l = rad(lon + spin);
    const x = Math.cos(p) * Math.sin(l);
    const y = Math.sin(p);
    const z = Math.cos(p) * Math.cos(l);
    return { x: cx + x * r, y: cy - y * r, visible: z >= 0 };
  }

  function tracePoly(poly, r, cx, cy) {
    let open = false;
    let drew = false;
    for (const [lat, lon] of poly) {
      const pt = project(lat, lon, r, cx, cy);
      if (!pt.visible) { open = false; continue; }
      if (!open) { ctx.moveTo(pt.x, pt.y); open = true; } else { ctx.lineTo(pt.x, pt.y); }
      drew = true;
    }
    return drew;
  }

  function read(name, fallback) {
    const v = getComputedStyle(document.body).getPropertyValue(name).trim();
    return v || fallback;
  }

  function draw() {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const cx = w / 2;
    const cy = h / 2;
    const r = Math.min(w, h) / 2 - 2;

    const oceanTop = read('--globe-ocean-top', '#3FA0DC');
    const oceanBot = read('--globe-ocean-bot', '#0E4A80');
    const landFill = read('--globe-land', '#4FA35C');
    const grid = read('--globe-grid', 'rgba(255,255,255,0.28)');
    const rim = read('--globe-rim', 'rgba(255,255,255,0.55)');

    // Ocean sphere
    const sphere = ctx.createLinearGradient(cx - r * 0.5, cy - r, cx + r * 0.6, cy + r);
    sphere.addColorStop(0, oceanTop);
    sphere.addColorStop(1, oceanBot);
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = sphere;
    ctx.fill();

    // Continents
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.clip();

    ctx.fillStyle = landFill;
    for (const poly of [...LAND, ...GREENLAND]) {
      ctx.beginPath();
      if (tracePoly(poly, r, cx, cy)) { ctx.closePath(); ctx.fill(); }
    }

    // Graticule
    ctx.strokeStyle = grid;
    ctx.lineWidth = 1;
    for (let lat = -60; lat <= 60; lat += 30) {
      ctx.beginPath();
      let open = false;
      for (let lon = -180; lon <= 180; lon += 4) {
        const pt = project(lat, lon, r, cx, cy);
        if (!pt.visible) { open = false; continue; }
        open ? ctx.lineTo(pt.x, pt.y) : (ctx.moveTo(pt.x, pt.y), (open = true));
      }
      ctx.stroke();
    }
    for (let lon = -180; lon < 180; lon += 30) {
      ctx.beginPath();
      let open = false;
      for (let lat = -90; lat <= 90; lat += 3) {
        const pt = project(lat, lon, r, cx, cy);
        if (!pt.visible) { open = false; continue; }
        open ? ctx.lineTo(pt.x, pt.y) : (ctx.moveTo(pt.x, pt.y), (open = true));
      }
      ctx.stroke();
    }
    ctx.restore();

    // Rim light
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = rim;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  function loop() {
    spin += 0.12;
    draw();
    raf = requestAnimationFrame(loop);
  }

  draw();
  if (!reduced) raf = requestAnimationFrame(loop);

  // Stop spinning when off-screen or tab hidden — no wasted battery on a phone.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(raf); raf = null; }
    else if (!reduced && !raf) raf = requestAnimationFrame(loop);
  });

  window.addEventListener('resize', draw);
  return { draw };
}

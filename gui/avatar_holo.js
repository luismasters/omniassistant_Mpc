/**
 * ═══════════════════════════════════════════════════════════════
 *  HoloAvatar v2 — AI State Indicator Engine
 *  Engine: HTML5 Canvas 2D + RequestAnimationFrame
 *  Architecture: State Machine → Renderer → Particle System
 * ═══════════════════════════════════════════════════════════════
 */

'use strict';

/* ─────────────────────────────────────────────────────────────
   1. DEFINICIÓN DE ESTADOS
   ───────────────────────────────────────────────────────────── */
const STATES = {
  idle: {
    id: 'idle',
    code: 'ST_00',
    label: 'REPOSO',
    sublabel: 'Vigilancia Pasiva',
    icon: '◎',
    desc: 'En espera activa',
    primary:    [32, 100, 255],   // #2064ff azul vívido
    secondary:  [10,  60, 180],
    accent:     [80, 160, 255],
    glow:       0.35,
    pulseSpeed: 0.0008,
    pulseAmp:   0.06,
    ringSpeed:  0.002,
    coreSize:   0.30,
    particleCount: 18,
    particleSpeed: 0.3,
    waveActive: false,
    meshOpacity: 0.35,
    metrics: { neural: 12, audio: 0, resp: 0, exec: 0 },
  },

  listening: {
    id: 'listening',
    code: 'ST_01',
    label: 'ESCUCHANDO',
    sublabel: 'Captura espectral activa Whisper',
    icon: '◉',
    desc: 'Audio espectral activo',
    primary:    [56, 189, 248],   // #38bdf8 cian espectro
    secondary:  [14, 116, 144],
    accent:     [186, 230, 253],
    glow:       0.75,
    pulseSpeed: 0.0035,
    pulseAmp:   0.18,
    ringSpeed:  0.008,
    coreSize:   0.35,
    particleCount: 35,
    particleSpeed: 1.0,
    waveActive: true,
    isEqualizerMode: true,
    meshOpacity: 0.2,
    metrics: { neural: 28, audio: 92, resp: 0, exec: 0 },
  },

  thinking: {
    id: 'thinking',
    code: 'ST_02',
    label: 'PROCESANDO',
    sublabel: 'Razonando Consulta',
    icon: '⬡',
    desc: 'Consultando modelo',
    primary:    [160,  90, 255],  // #a05aff violeta
    secondary:  [100,  50, 200],
    accent:     [200, 150, 255],
    glow:       0.5,
    pulseSpeed: 0.0025,
    pulseAmp:   0.10,
    ringSpeed:  0.012,
    coreSize:   0.32,
    particleCount: 45,
    particleSpeed: 1.2,
    waveActive: false,
    meshOpacity: 0.65,
    meshSpin: true,
    metrics: { neural: 95, audio: 5, resp: 15, exec: 0 },
  },

  speaking: {
    id: 'speaking',
    code: 'ST_03',
    label: 'HABLANDO',
    sublabel: 'Sintetizando Respuesta',
    icon: '▶',
    desc: 'Respuesta de voz',
    primary:    [255, 170,  30],  // #ffaa1e ámbar
    secondary:  [200, 110,   0],
    accent:     [255, 220, 100],
    glow:       0.6,
    pulseSpeed: 0.0030,
    pulseAmp:   0.18,
    ringSpeed:  0.008,
    coreSize:   0.38,
    particleCount: 35,
    particleSpeed: 0.9,
    waveActive: true,
    waveType: 'speech',
    meshOpacity: 0.45,
    metrics: { neural: 55, audio: 0, resp: 90, exec: 0 },
  },

  executing: {
    id: 'executing',
    code: 'ST_04',
    label: 'EJECUTANDO',
    sublabel: 'Acción del Sistema',
    icon: '⚡',
    desc: 'Modificando OS / código',
    primary:    [255, 100,  20],  // #ff6414 naranja fuego
    secondary:  [200,  60,   0],
    accent:     [255, 160,  60],
    glow:       0.7,
    pulseSpeed: 0.0040,
    pulseAmp:   0.22,
    ringSpeed:  0.018,
    coreSize:   0.40,
    particleCount: 55,
    particleSpeed: 2.0,
    waveActive: false,
    meshOpacity: 0.7,
    glitchEffect: true,
    metrics: { neural: 75, audio: 0, resp: 30, exec: 95 },
  },

  warning: {
    id: 'warning',
    code: 'ST_05',
    label: 'ATENCIÓN',
    sublabel: 'Confirmación Requerida',
    icon: '⚠',
    desc: 'Requiere usuario',
    primary:    [255, 200,  30],  // #ffc81e dorado
    secondary:  [200, 140,   0],
    accent:     [255, 240, 100],
    glow:       0.65,
    pulseSpeed: 0.0022,
    pulseAmp:   0.20,
    ringSpeed:  0.004,
    coreSize:   0.33,
    particleCount: 22,
    particleSpeed: 0.6,
    waveActive: false,
    warningFlash: true,
    meshOpacity: 0.55,
    metrics: { neural: 40, audio: 0, resp: 20, exec: 35 },
  },

  error: {
    id: 'error',
    code: 'ST_06',
    label: 'ERROR CRÍTICO',
    sublabel: 'Excepción del Sistema',
    icon: '✕',
    desc: 'Fallo de ejecución',
    primary:    [255,  45,  45],  // #ff2d2d carmesí
    secondary:  [180,  10,  10],
    accent:     [255, 120, 120],
    glow:       0.8,
    pulseSpeed: 0.0035,
    pulseAmp:   0.28,
    ringSpeed:  -0.005,
    coreSize:   0.36,
    particleCount: 40,
    particleSpeed: 1.5,
    waveActive: false,
    glitchEffect: true,
    meshOpacity: 0.8,
    metrics: { neural: 20, audio: 0, resp: 0, exec: 10 },
  },

  gaming: {
    id: 'gaming',
    code: 'ST_07',
    label: 'MODO GAMER',
    sublabel: 'Alto Rendimiento',
    icon: '🎮',
    desc: 'Operación en segundo plano',
    primary:    [236,  72, 153],  // #ec4899 rosa neón / magenta gamer
    secondary:  [160,  20, 120],
    accent:     [0,   240, 255],  // cian neón secundario
    glow:       0.8,
    pulseSpeed: 0.0045,
    pulseAmp:   0.15,
    ringSpeed:  0.020,
    coreSize:   0.28,
    particleCount: 65,
    particleSpeed: 2.2,
    waveActive: false,
    meshOpacity: 0.4,
    neonTrails: true,
    isGamepadMode: true,
    metrics: { neural: 30, audio: 0, resp: 0, exec: 20 },
  },
};

/* ─────────────────────────────────────────────────────────────
   2. AVATAR ENGINE — Core renderer
   ───────────────────────────────────────────────────────────── */
class HoloAvatarEngine {
  constructor(canvas, particleCanvas) {
    this.canvas  = canvas;
    this.ctx     = canvas.getContext('2d');
    this.pCanvas = particleCanvas;
    this.pCtx    = particleCanvas ? particleCanvas.getContext('2d') : null;

    // Coordenadas lógicas centradas (400x400)
    this.W  = 400;
    this.H  = 400;
    this.CX = 200;
    this.CY = 200;

    this.pW = 400;
    this.pH = 400;

    // State machine
    this.currentState  = STATES.idle;
    this.previousState = null;
    this.blendAlpha    = 1.0;
    this.transitioning = false;

    // Animation clock
    this.time     = 0;
    this.frame    = 0;
    this.lastTime = null;
    this.fps      = 60;
    this.fpsTimer = 0;
    this.fpsCount = 0;

    // Lerp targets
    this.lerpColor   = { r: 32, g: 100, b: 255 };
    this.lerpGlow    = 0.35;
    this.lerpCore    = 0.30;
    this.lerpPulse   = 0.0008;
    this.lerpAmp     = 0.06;
    this.lerpRing    = 0.002;
    this.lerpMesh    = 0.35;

    // Morphs de modos especiales
    this.gamepadMorph   = 0;
    this.equalizerMorph = 0;

    // Audio Equalizer Binary Rain Particles
    this.binaryRain = null;

    // Vertices icosféricos
    this.meshVertices = this.buildIcosphere(12);
    this.meshAngleX   = 0;
    this.meshAngleY   = 0;
    this.meshAngleZ   = 0;

    // Anillos orbitales
    this.rings = [
      { angle: 0, tilt: 0.3,  speed: 1.0, radius: 0.68, dashLen: 0.25 },
      { angle: 1.2, tilt: -0.7, speed: -0.6, radius: 0.56, dashLen: 0.40 },
      { angle: 2.4, tilt: 1.1,  speed: 0.9, radius: 0.78, dashLen: 0.15 },
    ];

    // Partículas
    this.particles = [];
    this.initParticles(40);

    // Ondas
    this.wavePhase = 0;
    this.waveData  = new Array(64).fill(0).map(() => Math.random() * 0.3);

    // Glitch
    this.glitchTimer  = 0;
    this.glitchOffset = 0;

    // Warning
    this.warnPhase = 0;

    // Uptime
    this.startTime = Date.now();
  }

  buildIcosphere(count) {
    const verts = [];
    const phi = Math.PI * (3 - Math.sqrt(5));

    for (let i = 0; i < count; i++) {
      const y   = 1 - (i / (count - 1)) * 2;
      const rad = Math.sqrt(Math.max(0, 1 - y * y));
      const th  = phi * i;
      verts.push({ x: Math.cos(th) * rad, y, z: Math.sin(th) * rad });
    }

    for (let i = 0; i < 20; i++) {
      const th  = Math.random() * Math.PI * 2;
      const ph  = Math.acos(2 * Math.random() - 1);
      verts.push({
        x: Math.sin(ph) * Math.cos(th),
        y: Math.cos(ph),
        z: Math.sin(ph) * Math.sin(th),
      });
    }

    return verts;
  }

  project3D(v, rx, ry, rz, scale) {
    let y1 = v.y * Math.cos(rx) - v.z * Math.sin(rx);
    let z1 = v.y * Math.sin(rx) + v.z * Math.cos(rx);
    let x2 = v.x * Math.cos(ry) + z1 * Math.sin(ry);
    let z2 = -v.x * Math.sin(ry) + z1 * Math.cos(ry);
    let x3 = x2 * Math.cos(rz) - y1 * Math.sin(rz);
    let y3 = x2 * Math.sin(rz) + y1 * Math.cos(rz);
    const fov = 2.5;
    const depth = fov / (fov + z2 * 0.4);
    return {
      x: 200 + x3 * scale * depth,
      y: 200 + y3 * scale * depth,
      z: z2,
      depth,
    };
  }

  initParticles(count) {
    this.particles = [];
    for (let i = 0; i < 80; i++) {
      this.particles.push(this.newParticle());
    }
  }

  newParticle() {
    const angle = Math.random() * Math.PI * 2;
    const dist  = 100 + Math.random() * 180;
    return {
      x: 200 + Math.cos(angle) * dist,
      y: 200 + Math.sin(angle) * dist,
      life: Math.random(),
      maxLife: 0.5 + Math.random() * 2.5,
      size: 0.5 + Math.random() * 2.0,
      orbitRadius: dist,
      orbitSpeed: (Math.random() - 0.5) * 0.004,
      orbitAngle: angle,
    };
  }

  lerp(a, b, t) { return a + (b - a) * t; }

  lerpColorTo(target, speed = 0.04) {
    this.lerpColor.r = this.lerp(this.lerpColor.r, target[0], speed);
    this.lerpColor.g = this.lerp(this.lerpColor.g, target[1], speed);
    this.lerpColor.b = this.lerp(this.lerpColor.b, target[2], speed);
  }

  setState(stateKey) {
    if (this.currentState.id === stateKey) return;
    if (!STATES[stateKey]) return;

    this.previousState = this.currentState;
    this.currentState  = STATES[stateKey];
    this.blendAlpha    = 0;
    this.transitioning = true;

    const count = this.currentState.particleCount;
    this.particles = this.particles.slice(0, count);
    while (this.particles.length < count) {
      this.particles.push(this.newParticle());
    }
  }

  update(dt) {
    const st = this.currentState;
    this.time += dt;

    if (this.transitioning) {
      this.blendAlpha += dt * 1.5;
      if (this.blendAlpha >= 1) {
        this.blendAlpha    = 1;
        this.transitioning = false;
      }
    }

    const sp = 0.04;
    this.lerpColorTo(st.primary, sp);
    this.lerpGlow   = this.lerp(this.lerpGlow,  st.glow,      sp);
    this.lerpCore   = this.lerp(this.lerpCore,  st.coreSize,  sp);
    this.lerpAmp    = this.lerp(this.lerpAmp,   st.pulseAmp,  sp);
    this.lerpRing   = this.lerp(this.lerpRing,  st.ringSpeed, sp * 0.5);
    this.lerpMesh   = this.lerp(this.lerpMesh,  st.meshOpacity, sp);

    // Morphs de modos especiales
    const targetGamepad   = st.isGamepadMode ? 1.0 : 0.0;
    const targetEqualizer = st.isEqualizerMode ? 1.0 : 0.0;

    this.gamepadMorph   = this.lerp(this.gamepadMorph, targetGamepad, 0.06);
    this.equalizerMorph = this.lerp(this.equalizerMorph, targetEqualizer, 0.08);

    const spinMult = st.meshSpin ? 2.5 : 1;
    this.meshAngleX += dt * 0.35 * spinMult;
    this.meshAngleY += dt * 0.55 * spinMult;
    this.meshAngleZ += dt * 0.15 * spinMult;

    this.rings.forEach(r => {
      r.angle += dt * this.lerpRing * r.speed;
    });

    this.wavePhase += dt * (st.waveActive ? 3.5 : 0.8);
    if (st.waveActive) {
      for (let i = 0; i < this.waveData.length; i++) {
        const target = st.waveType === 'speech'
          ? Math.abs(Math.sin(this.time * 4 + i * 0.4)) * (0.4 + Math.sin(i * 0.3 + this.time * 2) * 0.3)
          : Math.abs(Math.sin(this.time * 2.5 + i * 0.5)) * (0.5 + Math.random() * 0.5);
        this.waveData[i] = this.lerp(this.waveData[i], target, 0.15);
      }
    } else {
      for (let i = 0; i < this.waveData.length; i++) {
        this.waveData[i] = this.lerp(this.waveData[i], 0.05, 0.05);
      }
    }

    if (st.glitchEffect) {
      this.glitchTimer += dt;
      if (this.glitchTimer > 0.08 + Math.random() * 0.3) {
        this.glitchOffset = (Math.random() - 0.5) * 8;
        this.glitchTimer  = 0;
      }
    } else {
      this.glitchOffset = this.lerp(this.glitchOffset, 0, 0.2);
    }

    this.warnPhase += dt * (st.warningFlash ? 4 : 0);

    const speed = st.particleSpeed;
    this.particles.forEach(p => {
      p.orbitAngle += p.orbitSpeed * speed;
      const tx = 200 + Math.cos(p.orbitAngle) * p.orbitRadius;
      const ty = 200 + Math.sin(p.orbitAngle) * p.orbitRadius;
      p.x = this.lerp(p.x, tx, 0.02 * speed);
      p.y = this.lerp(p.y, ty, 0.02 * speed);
      p.life += dt / p.maxLife;
      if (p.life > 1) {
        Object.assign(p, this.newParticle());
        p.life = 0;
      }
    });

    this.fpsTimer += dt;
    this.fpsCount++;
    if (this.fpsTimer >= 1) {
      this.fps      = this.fpsCount;
      this.fpsCount = 0;
      this.fpsTimer = 0;
      const elFps = document.getElementById('fps-counter') || document.getElementById('holoFpsCount');
      if (elFps) elFps.textContent = this.fps + 'fps';
    }
  }

  render() {
    const ctx = this.ctx;
    const st  = this.currentState;
    const R   = this.lerpColor;
    const t   = this.time;

    ctx.clearRect(0, 0, this.W, this.H);

    const pulse = 1 + Math.sin(t * st.pulseSpeed * 1000) * this.lerpAmp;

    this.drawAura(ctx, pulse, R);
    this.drawOrbitalRings(ctx, R);

    // Mando Holográfico (Modo Gamer)
    if (this.gamepadMorph > 0.01) {
      this.drawHoloGamepad(ctx, pulse, R, this.gamepadMorph);
    }

    // Visualizador Espectral HUD (Modo Escuchando)
    if (this.equalizerMorph > 0.01) {
      this.drawListeningEqualizer(ctx, pulse, R, this.equalizerMorph);
    }

    // Esfera central y malla (Modos Estándar)
    const baseAlpha = (1.0 - this.gamepadMorph) * (1.0 - this.equalizerMorph);
    if (baseAlpha > 0.01) {
      ctx.save();
      ctx.globalAlpha = baseAlpha;

      this.drawMesh(ctx, R);

      if ((st.waveActive && !st.isEqualizerMode) || this.waveData.some(v => v > 0.06)) {
        this.drawWaves(ctx, R);
      }

      this.drawCore(ctx, pulse, R);

      ctx.restore();
    }

    if (Math.abs(this.glitchOffset) > 0.5) {
      this.drawGlitch(ctx, R);
    }

    if (st.warningFlash) {
      this.drawWarningRing(ctx, R);
    }

    if (this.pCtx) {
      this.renderParticles();
    }
  }

  drawAura(ctx, pulse, R) {
    const coreR = 200 * this.lerpCore * pulse;
    const glow  = this.lerpGlow;

    const outerGrad = ctx.createRadialGradient(
      200, 200, coreR * 0.8,
      200, 200, 190
    );
    outerGrad.addColorStop(0,   `rgba(${R.r|0},${R.g|0},${R.b|0},${glow * 0.35})`);
    outerGrad.addColorStop(0.5, `rgba(${R.r|0},${R.g|0},${R.b|0},${glow * 0.12})`);
    outerGrad.addColorStop(1,   `rgba(${R.r|0},${R.g|0},${R.b|0},0)`);

    ctx.beginPath();
    ctx.arc(200, 200, 190, 0, Math.PI * 2);
    ctx.fillStyle = outerGrad;
    ctx.fill();
  }

  drawCore(ctx, pulse, R) {
    const coreR = 200 * this.lerpCore * pulse;
    const CX = 200 + this.glitchOffset * 0.5;
    const CY = 200;

    const coreGrad = ctx.createRadialGradient(
      CX - coreR * 0.25, CY - coreR * 0.25, coreR * 0.05,
      CX, CY, coreR
    );
    coreGrad.addColorStop(0,   `rgba(255,255,255,0.92)`);
    coreGrad.addColorStop(0.15, `rgba(${R.r|0},${R.g|0},${R.b|0},0.95)`);
    coreGrad.addColorStop(0.5,  `rgba(${R.r * 0.6|0},${R.g * 0.6|0},${R.b * 0.6|0},0.85)`);
    coreGrad.addColorStop(0.85, `rgba(${R.r * 0.3|0},${R.g * 0.3|0},${R.b * 0.3|0},0.7)`);
    coreGrad.addColorStop(1,    `rgba(0,0,0,0)`);

    ctx.save();
    ctx.beginPath();
    ctx.arc(CX, CY, coreR, 0, Math.PI * 2);
    ctx.fillStyle = coreGrad;
    ctx.fill();

    const specGrad = ctx.createRadialGradient(
      CX - coreR * 0.3, CY - coreR * 0.3, 0,
      CX - coreR * 0.2, CY - coreR * 0.2, coreR * 0.55
    );
    specGrad.addColorStop(0,   'rgba(255,255,255,0.6)');
    specGrad.addColorStop(0.5, 'rgba(255,255,255,0.15)');
    specGrad.addColorStop(1,   'rgba(255,255,255,0)');

    ctx.beginPath();
    ctx.arc(CX, CY, coreR, 0, Math.PI * 2);
    ctx.fillStyle = specGrad;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(CX, CY, coreR, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(${R.r|0},${R.g|0},${R.b|0},0.7)`;
    ctx.lineWidth   = 1.5;
    ctx.shadowColor = `rgb(${R.r|0},${R.g|0},${R.b|0})`;
    ctx.shadowBlur  = 20;
    ctx.stroke();
    ctx.shadowBlur  = 0;
    ctx.restore();
  }

  drawMesh(ctx, R) {
    const scale   = 200 * 0.60;
    const verts   = this.meshVertices;
    const alpha   = this.lerpMesh;

    const projected = verts.map(v =>
      this.project3D(v, this.meshAngleX, this.meshAngleY, this.meshAngleZ, scale)
    );

    ctx.save();
    ctx.globalAlpha = alpha;

    for (let i = 0; i < projected.length; i++) {
      for (let j = i + 1; j < projected.length; j++) {
        const a = verts[i], b = verts[j];
        const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
        const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);

        if (dist < 0.75) {
          const pa = projected[i], pb = projected[j];
          const depthAlpha = 0.25 + ((pa.depth + pb.depth) / 2) * 0.5;

          ctx.beginPath();
          ctx.moveTo(pa.x, pa.y);
          ctx.lineTo(pb.x, pb.y);
          ctx.strokeStyle = `rgba(${R.r|0},${R.g|0},${R.b|0},${depthAlpha * 0.6})`;
          ctx.lineWidth = 0.5 + depthAlpha * 0.4;
          ctx.stroke();
        }
      }
    }

    projected.forEach(p => {
      const dotSize = 1.5 * p.depth;
      const dotAlpha = 0.4 + p.depth * 0.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, dotSize, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${R.r|0},${R.g|0},${R.b|0},${dotAlpha})`;
      ctx.fill();
    });

    ctx.globalAlpha = 1;
    ctx.restore();
  }

  drawListeningEqualizer(ctx, pulse, R, morph) {
    const CX = 200 + this.glitchOffset;
    const CY = 200;
    const t  = this.time;
    const cyan     = `rgb(56, 189, 248)`;

    ctx.save();
    ctx.globalAlpha = morph;

    const boxW = 310, boxH = 240;
    const left = CX - boxW / 2;
    const right = CX + boxW / 2;
    const top = CY - boxH / 2 - 5;
    const bottom = CY + boxH / 2 - 5;
    const bLen = 14;

    ctx.strokeStyle = cyan;
    ctx.lineWidth   = 1.8;
    ctx.shadowColor = cyan;
    ctx.shadowBlur  = 12;

    ctx.beginPath(); ctx.moveTo(left, top + bLen); ctx.lineTo(left, top); ctx.lineTo(left + bLen, top); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(right - bLen, top); ctx.lineTo(right, top); ctx.lineTo(right, top + bLen); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(left, bottom - bLen); ctx.lineTo(left, bottom); ctx.lineTo(left + bLen, bottom); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(right - bLen, bottom); ctx.lineTo(right, bottom); ctx.lineTo(right, bottom - bLen); ctx.stroke();

    ctx.shadowBlur = 0;

    ctx.save();
    ctx.beginPath();
    ctx.rect(left, top, boxW, boxH);
    ctx.clip();

    ctx.fillStyle = `rgba(6, 20, 40, 0.35)`;
    ctx.fillRect(left, top, boxW, boxH);

    const reticleR = 85;
    const reticleY = CY - 25;
    ctx.save();
    ctx.translate(CX, reticleY);
    ctx.rotate(t * 0.15);
    ctx.beginPath();
    ctx.arc(0, 0, reticleR, 0, Math.PI * 2);
    ctx.setLineDash([6, 10]);
    ctx.strokeStyle = `rgba(56, 189, 248, 0.28)`;
    ctx.lineWidth   = 1.2;
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();

    if (!this.binaryRain) {
      this.binaryRain = [];
      for (let i = 0; i < 22; i++) {
        this.binaryRain.push({
          x: CX - 120 + Math.random() * 240,
          y: top + Math.random() * boxH,
          speed: 35 + Math.random() * 70,
          val: Math.random() > 0.5 ? '1' : '0',
          opacity: 0.15 + Math.random() * 0.55,
        });
      }
    }

    ctx.font = '10px "Fira Code", monospace';
    ctx.textAlign = 'center';
    this.binaryRain.forEach(b => {
      b.y += 0.016 * b.speed;
      if (b.y > bottom - 25) {
        b.y = top + 8;
        b.x = CX - 130 + Math.random() * 260;
        b.val = Math.random() > 0.5 ? '1' : '0';
      }
      ctx.fillStyle = `rgba(56, 189, 248, ${b.opacity * 0.7})`;
      ctx.fillText(b.val, b.x, b.y);
    });

    const barCount = 18;
    const totalW   = 270;
    const startX   = CX - totalW / 2 + 8;
    const stepX    = (totalW - 16) / (barCount - 1);
    const baseBarY = bottom - 24;
    const maxBarH  = 115;

    for (let i = 0; i < barCount; i++) {
      const bx = startX + i * stepX;
      const freq1 = Math.sin(t * 6 + i * 0.65);
      const freq2 = Math.cos(t * 9 + i * 0.95);
      const freq3 = Math.sin(t * 14 + i * 0.35);
      const centerFactor = 1 - Math.pow(Math.abs(i - (barCount - 1) / 2) / ((barCount - 1) / 2), 1.6) * 0.25;

      let normH = (Math.abs(freq1 * 0.4 + freq2 * 0.35 + freq3 * 0.25) * 0.75 + 0.15) * centerFactor;
      normH = Math.min(1, Math.max(0.08, normH));
      const bh = normH * maxBarH;

      const barY = baseBarY - bh;
      const barWidth = 9;

      ctx.save();
      ctx.shadowColor = `rgb(56, 189, 248)`;
      ctx.shadowBlur  = 16;

      const barGrad = ctx.createLinearGradient(bx, baseBarY, bx, barY);
      barGrad.addColorStop(0,   `rgba(14, 116, 144, 0.3)`);
      barGrad.addColorStop(0.4, `rgba(56, 189, 248, 0.85)`);
      barGrad.addColorStop(1,   `rgba(186, 230, 253, 1)`);

      ctx.beginPath();
      if (ctx.roundRect) {
        ctx.roundRect(bx - barWidth / 2, barY, barWidth, bh, barWidth / 2);
      } else {
        ctx.rect(bx - barWidth / 2, barY, barWidth, bh);
      }
      ctx.fillStyle = barGrad;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(bx, barY + 3, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();

      ctx.restore();
    }

    ctx.restore();
    ctx.restore();
  }

  drawHoloGamepad(ctx, pulse, R, morph) {
    const CX = 200 + this.glitchOffset;
    const CY = 200;
    const t  = this.time;
    const tiltY = Math.sin(t * 1.5) * 5;

    ctx.save();
    ctx.globalAlpha = morph;
    ctx.translate(CX, CY + tiltY);

    const mainColor = `rgb(${R.r|0}, ${R.g|0}, ${R.b|0})`;
    const cyanColor = `rgb(0, 240, 255)`;

    ctx.save();
    ctx.shadowColor = mainColor;
    ctx.shadowBlur  = 25;
    ctx.strokeStyle = mainColor;
    ctx.lineWidth   = 2.5;

    ctx.beginPath();
    ctx.moveTo(-110, -35);
    ctx.bezierCurveTo(-130, -35, -150, 0, -140, 55);
    ctx.bezierCurveTo(-130, 95, -85, 90, -65, 45);
    ctx.bezierCurveTo(-45, 15, 45, 15, 65, 45);
    ctx.bezierCurveTo(85, 90, 130, 95, 140, 55);
    ctx.bezierCurveTo(150, 0, 130, -35, 110, -35);
    ctx.bezierCurveTo(70, -38, -70, -38, -110, -35);
    ctx.closePath();

    const chassisGrad = ctx.createLinearGradient(-120, -40, 120, 80);
    chassisGrad.addColorStop(0,   `rgba(${R.r|0},${R.g|0},${R.b|0},0.25)`);
    chassisGrad.addColorStop(0.5, `rgba(0, 240, 255, 0.15)`);
    chassisGrad.addColorStop(1,   `rgba(${R.r|0},${R.g|0},${R.b|0},0.25)`);
    ctx.fillStyle = chassisGrad;
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.beginPath();
    ctx.moveTo(-95, -25);
    ctx.bezierCurveTo(-115, -25, -125, 10, -120, 45);
    ctx.bezierCurveTo(-112, 70, -82, 65, -62, 30);
    ctx.bezierCurveTo(-40, -5, 40, -5, 62, 30);
    ctx.bezierCurveTo(82, 65, 112, 70, 120, 45);
    ctx.bezierCurveTo(125, 10, 115, -25, 95, -25);
    ctx.strokeStyle = `rgba(0, 240, 255, 0.4)`;
    ctx.lineWidth   = 1;
    ctx.stroke();

    ctx.lineWidth = 2;
    ctx.strokeStyle = cyanColor;
    ctx.shadowColor = cyanColor;
    ctx.shadowBlur  = 12;

    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(-105, -46, 40, 8, 3); else ctx.rect(-105, -46, 40, 8);
    ctx.stroke();

    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(65, -46, 40, 8, 3); else ctx.rect(65, -46, 40, 8);
    ctx.stroke();

    const dpadX = -75, dpadY = 5;
    ctx.shadowColor = mainColor;
    ctx.shadowBlur  = 15;
    ctx.fillStyle   = `rgba(${R.r|0}, ${R.g|0}, ${R.b|0}, 0.6)`;
    ctx.strokeStyle = mainColor;
    ctx.lineWidth   = 1.8;

    ctx.beginPath();
    ctx.moveTo(dpadX - 7,  dpadY - 22);
    ctx.lineTo(dpadX + 7,  dpadY - 22);
    ctx.lineTo(dpadX + 7,  dpadY - 7);
    ctx.lineTo(dpadX + 22, dpadY - 7);
    ctx.lineTo(dpadX + 22, dpadY + 7);
    ctx.lineTo(dpadX + 7,  dpadY + 7);
    ctx.lineTo(dpadX + 7,  dpadY + 22);
    ctx.lineTo(dpadX - 7,  dpadY + 22);
    ctx.lineTo(dpadX - 7,  dpadY + 7);
    ctx.lineTo(dpadX - 22, dpadY + 7);
    ctx.lineTo(dpadX - 22, dpadY - 7);
    ctx.lineTo(dpadX - 7,  dpadY - 7);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    const arrowAlpha = 0.5 + Math.sin(t * 4) * 0.4;
    ctx.fillStyle = `rgba(0, 240, 255, ${arrowAlpha})`;
    ctx.beginPath(); ctx.moveTo(dpadX, dpadY - 18); ctx.lineTo(dpadX - 4, dpadY - 11); ctx.lineTo(dpadX + 4, dpadY - 11); ctx.fill();
    ctx.beginPath(); ctx.moveTo(dpadX, dpadY + 18); ctx.lineTo(dpadX - 4, dpadY + 11); ctx.lineTo(dpadX + 4, dpadY + 11); ctx.fill();

    const btnX = 75, btnY = 5;
    const buttons = [
      { x: btnX,      y: btnY - 16, label: 'Y', col: cyanColor },
      { x: btnX + 16, y: btnY,      label: 'B', col: mainColor },
      { x: btnX,      y: btnY + 16, label: 'A', col: cyanColor },
      { x: btnX - 16, y: btnY,      label: 'X', col: mainColor },
    ];

    buttons.forEach((b) => {
      ctx.save();
      ctx.shadowColor = b.col;
      ctx.shadowBlur  = 12;
      ctx.beginPath();
      ctx.arc(b.x, b.y, 8, 0, Math.PI * 2);
      ctx.fillStyle   = `rgba(10, 20, 45, 0.8)`;
      ctx.strokeStyle = b.col;
      ctx.lineWidth   = 1.5;
      ctx.fill();
      ctx.stroke();

      ctx.font         = 'bold 9px Outfit, sans-serif';
      ctx.fillStyle    = '#ffffff';
      ctx.textAlign    = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(b.label, b.x, b.y + 0.5);
      ctx.restore();
    });

    const stickL = { x: -35, y: 32 };
    const stickR = { x: 35,  y: 32 };
    const stickOrbitAngle = t * 2.5;

    [stickL, stickR].forEach((stk, idx) => {
      ctx.save();
      ctx.beginPath();
      ctx.arc(stk.x, stk.y, 16, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(0, 240, 255, 0.4)`;
      ctx.lineWidth   = 1;
      ctx.stroke();

      const sx = stk.x + Math.cos(stickOrbitAngle + idx * Math.PI) * 4;
      const sy = stk.y + Math.sin(stickOrbitAngle + idx * Math.PI) * 4;

      const sg = ctx.createRadialGradient(sx, sy, 1, sx, sy, 10);
      sg.addColorStop(0,   'rgba(255, 255, 255, 0.9)');
      sg.addColorStop(0.5, mainColor);
      sg.addColorStop(1,   'rgba(0, 0, 0, 0.8)');

      ctx.shadowColor = mainColor;
      ctx.shadowBlur  = 15;
      ctx.beginPath();
      ctx.arc(sx, sy, 10, 0, Math.PI * 2);
      ctx.fillStyle = sg;
      ctx.fill();
      ctx.strokeStyle = cyanColor;
      ctx.lineWidth   = 1.5;
      ctx.stroke();
      ctx.restore();
    });

    const coreR = 14 * pulse;
    const cg = ctx.createRadialGradient(0, -8, 0, 0, -8, coreR);
    cg.addColorStop(0,   '#ffffff');
    cg.addColorStop(0.4, cyanColor);
    cg.addColorStop(0.8, mainColor);
    cg.addColorStop(1,   'rgba(0,0,0,0)');

    ctx.save();
    ctx.shadowColor = cyanColor;
    ctx.shadowBlur  = 25;
    ctx.beginPath();
    ctx.arc(0, -8, coreR, 0, Math.PI * 2);
    ctx.fillStyle = cg;
    ctx.fill();

    ctx.font         = 'bold 8px "Fira Code", monospace';
    ctx.fillStyle    = '#ffffff';
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('AI', 0, -7.5);
    ctx.restore();

    ctx.restore();
    ctx.restore();
  }

  drawOrbitalRings(ctx, R) {
    ctx.save();

    this.rings.forEach((ring, idx) => {
      const orbitR = 200 * ring.radius;
      const tilt   = ring.tilt;
      const scaleY = Math.abs(Math.cos(tilt + this.time * 0.0005));
      const alpha  = (0.3 + scaleY * 0.5) * (idx === 0 ? 1 : 0.7);

      ctx.save();
      ctx.translate(200, 200);
      ctx.rotate(ring.angle);
      ctx.scale(1, Math.cos(tilt));

      const dashTotal = Math.PI * 2 * orbitR;
      const dashLen   = dashTotal * ring.dashLen;
      const gapLen    = dashTotal * (1 - ring.dashLen);

      ctx.beginPath();
      ctx.ellipse(0, 0, orbitR, orbitR, 0, 0, Math.PI * 2);
      ctx.setLineDash([dashLen, gapLen]);
      ctx.lineDashOffset = -this.time * 80 * Math.abs(this.lerpRing);
      ctx.strokeStyle = `rgba(${R.r|0},${R.g|0},${R.b|0},${alpha * 0.5})`;
      ctx.lineWidth   = 1;
      ctx.shadowColor = `rgb(${R.r|0},${R.g|0},${R.b|0})`;
      ctx.shadowBlur  = 6;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.shadowBlur = 0;

      const nodeAngle  = ring.angle * 3 + this.time * 0.5 * ring.speed;
      const nodeX      = Math.cos(nodeAngle) * orbitR;
      const nodeY      = Math.sin(nodeAngle) * orbitR;
      const nodeAlpha  = 0.6 + Math.sin(this.time * 2 + idx) * 0.3;
      const nodeR      = 3 + Math.sin(this.time * 3 + idx) * 1.5;

      const ng = ctx.createRadialGradient(nodeX, nodeY, 0, nodeX, nodeY, nodeR * 4);
      ng.addColorStop(0,   `rgba(255,255,255,${nodeAlpha * 0.9})`);
      ng.addColorStop(0.4, `rgba(${R.r|0},${R.g|0},${R.b|0},${nodeAlpha * 0.6})`);
      ng.addColorStop(1,   'rgba(0,0,0,0)');

      ctx.beginPath();
      ctx.arc(nodeX, nodeY, nodeR * 4, 0, Math.PI * 2);
      ctx.fillStyle = ng;
      ctx.fill();

      ctx.restore();
    });

    ctx.restore();
  }

  drawWaves(ctx, R) {
    const waveCount  = this.waveData.length;
    const baseRadius = 200 * 0.42;
    const maxAmp     = 200 * 0.25;

    ctx.save();
    ctx.translate(200, 200);

    ctx.beginPath();
    for (let i = 0; i <= waveCount; i++) {
      const idx    = i % waveCount;
      const angle  = (i / waveCount) * Math.PI * 2 - Math.PI / 2;
      const amp    = this.waveData[idx] * maxAmp;
      const radius = baseRadius + amp;
      const x      = Math.cos(angle) * radius;
      const y      = Math.sin(angle) * radius;

      if (i === 0) ctx.moveTo(x, y);
      else         ctx.lineTo(x, y);
    }
    ctx.closePath();

    const waveAlpha = 0.6;
    ctx.strokeStyle = `rgba(${R.r|0},${R.g|0},${R.b|0},${waveAlpha})`;
    ctx.lineWidth   = 2;
    ctx.shadowColor = `rgb(${R.r|0},${R.g|0},${R.b|0})`;
    ctx.shadowBlur  = 12;
    ctx.stroke();

    ctx.beginPath();
    for (let i = 0; i <= waveCount; i++) {
      const idx    = i % waveCount;
      const angle  = (i / waveCount) * Math.PI * 2 - Math.PI / 2;
      const amp    = this.waveData[(idx + 8) % waveCount] * maxAmp * 0.6;
      const radius = baseRadius - amp * 0.8;
      const x      = Math.cos(angle) * radius;
      const y      = Math.sin(angle) * radius;

      if (i === 0) ctx.moveTo(x, y);
      else         ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = `rgba(${R.r|0},${R.g|0},${R.b|0},${waveAlpha * 0.3})`;
    ctx.lineWidth   = 1;
    ctx.shadowBlur  = 6;
    ctx.stroke();
    ctx.shadowBlur  = 0;

    ctx.restore();
  }

  drawGlitch(ctx, R) {
    const numLines = 3 + Math.floor(Math.random() * 4);
    ctx.save();
    ctx.globalAlpha = 0.15 + Math.random() * 0.2;

    for (let i = 0; i < numLines; i++) {
      const y    = Math.random() * 400;
      const h    = 1 + Math.random() * 4;
      const w    = 40 + Math.random() * 120;
      const x    = Math.random() * (400 - w);
      const offX = this.glitchOffset * (0.5 + Math.random());

      ctx.fillStyle = `rgba(${R.r|0},${R.g|0},${R.b|0},0.5)`;
      ctx.fillRect(x + offX, y, w, h);

      ctx.fillStyle = `rgba(255,255,255,0.3)`;
      ctx.fillRect(x - offX * 0.3, y + 2, w * 0.7, h * 0.5);
    }

    ctx.globalAlpha = 1;
    ctx.restore();
  }

  drawWarningRing(ctx, R) {
    const flash = (Math.sin(this.warnPhase) + 1) / 2;
    const ringR = 200 * 0.88;

    ctx.save();
    ctx.beginPath();
    ctx.arc(200, 200, ringR, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(${R.r|0},${R.g|0},${R.b|0},${0.3 + flash * 0.5})`;
    ctx.lineWidth   = 2 + flash * 2;
    ctx.shadowColor = `rgb(${R.r|0},${R.g|0},${R.b|0})`;
    ctx.shadowBlur  = 20 + flash * 20;
    ctx.stroke();
    ctx.shadowBlur  = 0;
    ctx.restore();
  }

  renderParticles() {
    if (!this.pCtx) return;
    const pCtx = this.pCtx;
    const R    = this.lerpColor;
    const st   = this.currentState;

    pCtx.clearRect(0, 0, this.pW, this.pH);

    const offsetX = (this.pW - this.W) / 2;
    const offsetY = (this.pH - this.H) / 2;

    this.particles.forEach(p => {
      if (p.life <= 0 || p.life >= 1) return;

      const lifeAlpha = Math.sin(p.life * Math.PI);
      const alpha     = lifeAlpha * 0.7;
      const size      = p.size * lifeAlpha;

      const px = p.x + offsetX;
      const py = p.y + offsetY;

      if (st.neonTrails) {
        pCtx.beginPath();
        pCtx.arc(
          px - Math.cos(p.orbitAngle) * 8,
          py - Math.sin(p.orbitAngle) * 8,
          size * 3, 0, Math.PI * 2
        );
        pCtx.fillStyle = `rgba(${R.r|0},${R.g|0},${R.b|0},${alpha * 0.15})`;
        pCtx.fill();
      }

      const grd = pCtx.createRadialGradient(
        px, py, 0,
        px, py, size * 5
      );
      grd.addColorStop(0,   `rgba(${R.r|0},${R.g|0},${R.b|0},${alpha * 0.8})`);
      grd.addColorStop(0.4, `rgba(${R.r|0},${R.g|0},${R.b|0},${alpha * 0.3})`);
      grd.addColorStop(1,   'rgba(0,0,0,0)');

      pCtx.beginPath();
      pCtx.arc(px, py, size * 5, 0, Math.PI * 2);
      pCtx.fillStyle = grd;
      pCtx.fill();

      pCtx.beginPath();
      pCtx.arc(px, py, size, 0, Math.PI * 2);
      pCtx.fillStyle = `rgba(255,255,255,${alpha * 0.9})`;
      pCtx.fill();
    });
  }

  tick(timestamp) {
    if (!this.lastTime) this.lastTime = timestamp;
    const dt = Math.min((timestamp - this.lastTime) / 1000, 0.05);
    this.lastTime = timestamp;
    this.frame++;

    this.update(dt);
    this.render();

    requestAnimationFrame(ts => this.tick(ts));
  }

  start() {
    requestAnimationFrame(ts => this.tick(ts));
  }
}

/* ─────────────────────────────────────────────────────────────
   3. UI CONTROLLER
   ───────────────────────────────────────────────────────────── */
class HoloAvatarUI {
  constructor(engine) {
    this.engine       = engine;
    this.currentState = 'idle';

    this.bindEvents();
    this.updateLoop();
  }

  stateColor(stateId) {
    const colors = {
      idle:      '#3a7bd5',
      listening: '#00e5a0',
      thinking:  '#a78bfa',
      speaking:  '#f59e0b',
      executing: '#f97316',
      warning:   '#fbbf24',
      error:     '#ef4444',
      gaming:    '#ec4899',
    };
    return colors[stateId] || '#40b4ff';
  }

  activateState(stateId, customMsg = '') {
    if (this.currentState === stateId && !customMsg) return;
    if (!STATES[stateId]) return;
    this.currentState = stateId;

    this.engine.setState(stateId);
    document.body.setAttribute('data-state', stateId);

    const st = STATES[stateId];
    const labelEl    = document.getElementById('status-label');
    const sublabelEl = document.getElementById('status-sublabel');
    const codeEl     = document.getElementById('status-code');

    if (labelEl) {
      labelEl.style.opacity = '0';
      setTimeout(() => {
        labelEl.textContent    = st.label;
        if (sublabelEl) sublabelEl.textContent = customMsg || st.sublabel;
        if (codeEl) codeEl.textContent     = st.code;
        labelEl.style.color    = this.stateColor(stateId);
        labelEl.style.textShadow = `0 0 8px ${this.stateColor(stateId)}, 0 0 20px ${this.stateColor(stateId)}66`;
        labelEl.style.opacity  = '1';
        if (sublabelEl) sublabelEl.style.opacity = '1';
      }, 150);

      labelEl.style.transition = 'opacity 0.15s ease';
    }

    this.updateMetrics(st.metrics);

    document.querySelectorAll('.metric-fill').forEach(fill => {
      fill.style.background = `linear-gradient(90deg, ${this.stateColor(stateId)}, ${this.stateColor(stateId)}aa)`;
      fill.style.boxShadow  = `0 0 8px ${this.stateColor(stateId)}88`;
    });
  }

  updateMetrics(metrics) {
    if (!metrics) return;
    const animate = (id, valId, target) => {
      const el  = document.getElementById(id);
      const val = document.getElementById(valId);
      if (!el || target === undefined) return;

      const current = parseFloat(el.style.width) || 0;
      const diff    = target - current;
      let step = 0;

      const run = () => {
        step++;
        const prog = step / 25;
        if (prog >= 1) {
          el.style.width = target + '%';
          if (val) val.textContent = target + '%';
          return;
        }
        const v = current + diff * (1 - Math.pow(1 - prog, 3));
        el.style.width = v + '%';
        if (val) val.textContent = Math.round(v) + '%';
        requestAnimationFrame(run);
      };
      requestAnimationFrame(run);
    };

    animate('metric-neural', 'val-neural', metrics.neural);
    animate('metric-audio',  'val-audio',  metrics.audio);
    animate('metric-resp',   'val-resp',   metrics.resp);
    animate('metric-exec',   'val-exec',   metrics.exec);
  }

  bindEvents() {
    const stateKeys = ['idle', 'listening', 'thinking', 'speaking', 'executing', 'warning', 'error', 'gaming'];
    document.addEventListener('keydown', e => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      const idx = parseInt(e.key) - 1;
      if (idx >= 0 && idx < stateKeys.length) {
        this.activateState(stateKeys[idx]);
      }
    });
  }

  updateLoop() {
    const clockEl  = document.getElementById('digitalClock') || document.getElementById('clock');
    const uptimeEl = document.getElementById('uptime');

    const tick = () => {
      const now = new Date();
      const h   = String(now.getHours()).padStart(2, '0');
      const m   = String(now.getMinutes()).padStart(2, '0');
      const s   = String(now.getSeconds()).padStart(2, '0');
      if (clockEl) clockEl.textContent = `${h}:${m}:${s}`;

      if (uptimeEl) {
        const elapsed = Date.now() - this.engine.startTime;
        const es = Math.floor(elapsed / 1000);
        const uh = String(Math.floor(es / 3600)).padStart(2, '0');
        const um = String(Math.floor((es % 3600) / 60)).padStart(2, '0');
        const us = String(es % 60).padStart(2, '0');
        uptimeEl.textContent = `${uh}:${um}:${us}`;
      }

      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
}

/* ─────────────────────────────────────────────────────────────
   4. INICIALIZACIÓN E INTEGRACIÓN CON EMO CANVAS & ANIME AVATAR
   ───────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Inicializar Anime Avatar Engine (Robot A10)
  const animeStage = document.getElementById('animeAvatarStage');
  if (animeStage && window.animeAvatarEngine) {
    window.animeAvatarEngine.init(animeStage);
  }

  // Inicializar HoloAvatar Engine (Canvas 2D)
  const avatarCanvas   = document.getElementById('avatar-canvas');
  const particleCanvas = document.getElementById('particle-canvas');

  if (avatarCanvas) {
    const dpr = window.devicePixelRatio || 1;
    const setupHiDPI = (canvas, cssW, cssH, logW = 400, logH = 400) => {
      canvas.style.width  = cssW + 'px';
      canvas.style.height = cssH + 'px';
      canvas.width  = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      const ctx = canvas.getContext('2d');
      ctx.scale(dpr * (cssW / logW), dpr * (cssH / logH));
    };
    setupHiDPI(avatarCanvas, 220, 220, 400, 400);
    if (particleCanvas) setupHiDPI(particleCanvas, 220, 220, 400, 400);

    const engine = new HoloAvatarEngine(avatarCanvas, particleCanvas);
    engine.start();

    const ui = new HoloAvatarUI(engine);

    window.holoEngine = engine;
    window.holoUI     = ui;
  }

  // Configurar Selector de Modo de Avatar (Animado por defecto vs Holográfico)
  setupAvatarModeToggle();

  hookEmoFace();
});

function setupAvatarModeToggle() {
  const btnAnime = document.getElementById('btnModeAnime');
  const btnHolo = document.getElementById('btnModeHolo');
  const animeStage = document.getElementById('animeAvatarStage');
  const holoStage = document.getElementById('holoAvatarStage');

  function setAvatarMode(mode) {
    if (mode === 'holo') {
      if (animeStage) animeStage.classList.add('hidden');
      if (holoStage) holoStage.classList.remove('hidden');
      if (btnAnime) btnAnime.classList.remove('active');
      if (btnHolo) btnHolo.classList.add('active');
    } else {
      // Default: 'anime'
      if (animeStage) animeStage.classList.remove('hidden');
      if (holoStage) holoStage.classList.add('hidden');
      if (btnAnime) btnAnime.classList.add('active');
      if (btnHolo) btnHolo.classList.remove('active');
    }
    try {
      localStorage.setItem('argus_avatar_mode', mode);
    } catch(e){}
  }

  if (btnAnime) btnAnime.addEventListener('click', () => setAvatarMode('anime'));
  if (btnHolo) btnHolo.addEventListener('click', () => setAvatarMode('holo'));

  const savedMode = localStorage.getItem('argus_avatar_mode') || 'anime';
  setAvatarMode(savedMode);
}

function hookEmoFace() {
  const mapEmoToHoloState = (emoEstado) => {
    const isGamerMode = document.body.classList.contains('theme-gamer');
    const cloudBubble = document.getElementById('emoCloudBubble');
    const hayRecordatorioActivo = cloudBubble && !cloudBubble.classList.contains('hidden');

    switch (emoEstado) {
      case 'idle':
        if (hayRecordatorioActivo) return 'warning';
        return isGamerMode ? 'gaming' : 'idle';
      case 'listening':
        return 'listening';
      case 'thinking':
        return 'thinking';
      case 'talking':
      case 'speaking':
        return 'speaking';
      case 'confirm':
      case 'warning':
      case 'sad':
        return 'warning';
      case 'executing':
        return 'executing';
      case 'error':
      case 'angry':
        return 'error';
      case 'gaming':
        return 'gaming';
      default:
        if (hayRecordatorioActivo) return 'warning';
        return isGamerMode ? 'gaming' : 'idle';
    }
  };

  if (window.emoFace) {
    const originalSetEstado = window.emoFace.setEstado.bind(window.emoFace);
    window.emoFace.setEstado = function(nuevo_estado, msg = '') {
      originalSetEstado(nuevo_estado, msg);
      const stateKey = mapEmoToHoloState(nuevo_estado);

      if (window.holoUI) {
        window.holoUI.activateState(stateKey, msg);
      }
      if (window.animeAvatarEngine) {
        window.animeAvatarEngine.activateState(stateKey, msg);
      }
    };

    if (window.emoFace.setClima) {
      const originalSetClima = window.emoFace.setClima.bind(window.emoFace);
      window.emoFace.setClima = function(climaCondicion) {
        originalSetClima(climaCondicion);
      };
    }
  } else {
    setTimeout(hookEmoFace, 50);
  }
}

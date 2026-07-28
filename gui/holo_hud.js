/**
 * HUD Holográfico Interactivo (HoloHud) — Argus Copilot
 * Replica de holo_states.html adaptada y optimizada para el sidebar.
 * 
 * Se conecta de forma transparente con EmoCanvasFace interceptando setEstado y setClima.
 */

class HoloHud {
  constructor(canvasId, containerId) {
    this.canvas = document.getElementById(canvasId);
    this.stageContainer = document.getElementById(containerId);
    if (!this.canvas || !this.stageContainer) return;
    this.ctx = this.canvas.getContext('2d');

    // Dimensiones iniciales del lienzo
    this.W = 250;
    this.H = 180;
    this.cx = this.W / 2;
    this.cy = this.H / 2;

    this.currentState = 'ACTIVO';
    this.phase = 0;
    this.N = 160;

    // Configuración de Estados
    this.STATES = {
      ACTIVO: {
        code: 'ST-01',
        color: '#2dd4bf',
        freq: '120 Hz',
        desc: 'Sistema en reposo pasivo. Núcleo cuántico en vigilancia de entorno.'
      },
      ESCUCHANDO: {
        code: 'ST-02',
        color: '#38bdf8',
        freq: '44.1 kHz',
        desc: 'Captura espectral activa Whisper. Procesando audio de micrófono.'
      },
      PENSANDO: {
        code: 'ST-03',
        color: '#a78bfa',
        freq: '2.4 GHz',
        desc: 'Evaluación neuronal y razonamiento lógico. Sintetizando vectores.'
      },
      HABLANDO: {
        code: 'ST-04',
        color: '#f472b6',
        freq: '24 kHz (VOCAL ORB)',
        desc: 'Orbe vocal tipo JARVIS. Núcleo armónico con ondas acústicas dinámicas.'
      },
      EJECUTANDO: {
        code: 'ST-05',
        color: '#fbbf24',
        freq: '3D HYPERCUBE // 4.8 GHz',
        desc: 'Hipercubo 3D en rotación continua con barra de progreso en tiempo real.'
      },
      AVISO: {
        code: 'ST-06',
        color: '#fb923c',
        freq: '0.8 Hz',
        desc: 'Notificación del sistema requerida. Emitiendo señal de confirmación.'
      },
      ALERTA: {
        code: 'ST-07',
        color: '#f87171',
        freq: 'MAX RISK',
        desc: '¡Atención! Condición crítica o excepción detectada en el flujo.'
      },
      GAMING: {
        code: 'ST-08',
        color: '#c084fc',
        freq: '165 Hz (OVERCLOCK)',
        desc: 'Modo Gaming. Control holográfico con Joysticks y botones ABXY activos.'
      }
    };

    // Matrix Rain Background Setup
    this.BINARY_COLS = 16;
    this.binaryDrops = [];

    // Partículas
    this.particles = [];
    this.COLS = 16;
    this.rowsPerCol = Math.ceil(this.N / this.COLS);
    this.GRID_COLS = 12;

    // Vértices y aristas del Cubo 3D
    this.CUBE_VERTICES = [
      [-20, -20, -20], [20, -20, -20], [20, 20, -20], [-20, 20, -20], // Cara trasera
      [-20, -20,  20], [20, -20,  20], [20, 20,  20], [-20, 20,  20]  // Cara delantera
    ];
    this.CUBE_EDGES = [
      [0,1],[1,2],[2,3],[3,0], // Atrás
      [4,5],[5,6],[6,7],[7,4], // Adelante
      [0,4],[1,5],[2,6],[3,7]  // Columnas conectoras
    ];

    // FPS Counter variables
    this.lastTime = performance.now();
    this.frameCount = 0;
    this.fpsValue = 60;

    this.init();
  }

  init() {
    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());

    // Inicializar partículas con coordenadas de destino por defecto
    for (let i = 0; i < this.N; i++) {
      const angle = Math.random() * Math.PI * 2;
      const radius = Math.random() * 40;
      this.particles.push({
        x: this.cx + Math.cos(angle) * radius,
        y: this.cy + Math.sin(angle) * radius,
        tx: this.cx,
        ty: this.cy,
        seed: Math.random() * 10,
        size: 1.2 + Math.random() * 1.5,
        alpha: 0.6 + Math.random() * 0.4,
        col: i % this.COLS,
        rowInCol: Math.floor(i / this.COLS),
        gx: i % this.GRID_COLS,
        gy: Math.floor(i / this.GRID_COLS),
        arm: i % 2
      });
    }

    this.setState('ACTIVO');
    this.startRenderLoop();
    this.startSpeakingPoll();
  }

  startSpeakingPoll() {
    let wasSpeaking = false;
    setInterval(async () => {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.esta_hablando === 'function') {
        try {
          const hablando = await window.pywebview.api.esta_hablando();
          if (hablando) {
            wasSpeaking = true;
            if (window.emoFace && window.emoFace.estado !== 'talking') {
              window.emoFace.setEstado('talking');
            } else if (!window.emoFace && this.currentState !== 'HABLANDO') {
              this.setState('HABLANDO');
            }
          } else if (wasSpeaking) {
            wasSpeaking = false;
            if (window.emoFace && window.emoFace.estado === 'talking') {
              window.emoFace.setEstado('idle');
            } else if (!window.emoFace) {
              const isGamerMode = document.body.classList.contains('theme-gamer');
              this.setState(isGamerMode ? 'GAMING' : 'ACTIVO');
            }
          }
        } catch (e) {
          console.error("Error al consultar estado de habla:", e);
        }
      }
    }, 300);
  }

  initBinaryRain() {
    this.binaryDrops.length = 0;
    const colStep = this.W / this.BINARY_COLS;
    for (let c = 0; c < this.BINARY_COLS; c++) {
      this.binaryDrops.push({
        x: c * colStep + colStep / 2,
        y: Math.random() * this.H,
        speed: 1.0 + Math.random() * 1.5,
        length: 5 + Math.floor(Math.random() * 6),
        chars: Array.from({ length: 12 }, () => (Math.random() > 0.5 ? '1' : '0'))
      });
    }
  }

  resizeCanvas() {
    if (!this.stageContainer || !this.canvas) return;
    const rect = this.stageContainer.getBoundingClientRect();
    this.W = Math.floor(rect.width) || 250;
    this.H = Math.floor(rect.height) || 180;
    this.canvas.width = this.W;
    this.canvas.height = this.H;
    this.cx = this.W / 2;
    this.cy = this.H / 2;
    this.initBinaryRain();
  }

  hexToRgb(hex) {
    const v = parseInt(hex.slice(1), 16);
    return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
  }

  // Permite configurar el estado holográfico con textos en la UI
  setState(name) {
    if (!this.STATES[name]) return;
    this.currentState = name;
    const s = this.STATES[name];

    // Aplicar variable de color al CSS del documento
    document.documentElement.style.setProperty('--holo-current-color', s.color);

    // Actualizar elementos de texto si existen
    const elCode = document.getElementById('holoStateCode');
    const elName = document.getElementById('holoStateName');
    const elDesc = document.getElementById('holoStateDesc');
    const elFreq = document.getElementById('holoStateFreq');
    const elHex = document.getElementById('holoStateHexCode');
    const elCard = document.querySelector('.holo-readout-card');

    if (elCode) elCode.textContent = s.code;
    if (elName) elName.textContent = name;
    if (elDesc) elDesc.textContent = s.desc;
    if (elFreq) elFreq.textContent = s.freq;
    if (elHex) elHex.textContent = s.color.toUpperCase();

    if (elCard) {
      elCard.style.setProperty('--holo-border-color', s.color);
    }
  }

  // Mapea los estados de EMO a estados del HUD Holográfico
  mapAndSetEstado(emoEstado, msg = '') {
    let holoEstado = 'ACTIVO';
    const isGamerMode = document.body.classList.contains('theme-gamer');

    if (emoEstado === 'idle') {
      holoEstado = isGamerMode ? 'GAMING' : 'ACTIVO';
    } else if (emoEstado === 'listening') {
      holoEstado = 'ESCUCHANDO';
    } else if (emoEstado === 'thinking') {
      holoEstado = 'PENSANDO';
    } else if (emoEstado === 'talking') {
      holoEstado = 'HABLANDO';
    } else if (emoEstado === 'confirm') {
      holoEstado = 'EJECUTANDO';
    } else if (emoEstado === 'error') {
      holoEstado = 'ALERTA';
    } else if (emoEstado === 'sad') {
      holoEstado = 'AVISO';
    } else if (emoEstado === 'angry') {
      holoEstado = 'ALERTA';
    } else if (['hot', 'cold', 'rainy', 'stormy', 'windy', 'cloudy'].includes(emoEstado)) {
      holoEstado = 'AVISO';
    }

    this.setState(holoEstado);

    // Si se pasa un mensaje personalizado en confirmación o aviso, cambiar la descripción
    if (msg) {
      const elDesc = document.getElementById('holoStateDesc');
      if (elDesc) elDesc.textContent = msg;
    }
  }

  // Fórmulas geométricas para animar partículas hacia su destino
  getGamepadContourPoint(t) {
    const angle = t * Math.PI * 2;
    const rx = 52, ry = 30; // dimensiones compactas
    let x = Math.cos(angle) * rx;
    let y = Math.sin(angle) * ry;

    // Puente superior
    if (y < -5 && Math.abs(x) < 22) {
      y += 9 * (1 - Math.abs(x) / 22);
    }
    // Puente inferior
    if (y > 3 && Math.abs(x) < 19) {
      y -= 11 * (1 - Math.abs(x) / 19);
    }
    // Grips laterales
    if (y > 1 && Math.abs(x) > 22) {
      const gripFactor = Math.sin(((Math.abs(x) - 22) / (rx - 22)) * Math.PI);
      y += 16 * gripFactor;
      x += Math.sign(x) * 7 * gripFactor;
    }
    return { x: this.cx + x, y: this.cy + y - 2 };
  }

  get3DCubePoint(x3d, y3d, z3d, rotY, rotX) {
    // Rotación eje Y
    const x1 = x3d * Math.cos(rotY) + z3d * Math.sin(rotY);
    const z1 = -x3d * Math.sin(rotY) + z3d * Math.cos(rotY);

    // Rotación eje X
    const y2 = y3d * Math.cos(rotX) - z1 * Math.sin(rotX);
    const z2 = y3d * Math.sin(rotX) + z1 * Math.cos(rotX);

    const fov = 150;
    const scale = fov / (fov + z2);

    return {
      x: this.cx + x1 * scale,
      y: this.cy + y2 * scale * 0.8 + 4,
      z: z2
    };
  }

  assignTargets() {
    const barBaseY = this.H - 25;

    this.particles.forEach((p, i) => {
      const nx = i / this.N;

      if (this.currentState === 'ACTIVO') {
        const isInner = i % 3 === 0;
        const ringRadius = isInner 
          ? 20 + Math.sin(this.phase * 0.8 + p.seed) * 3
          : 42 + Math.sin(this.phase * 0.4 + p.seed * 2) * 5;
        const rot = isInner ? this.phase * 0.25 : -this.phase * 0.15;
        const angle = nx * Math.PI * 2 + rot;
        
        p.tx = this.cx + Math.cos(angle) * ringRadius;
        p.ty = this.cy + Math.sin(angle) * ringRadius * 0.8;

      } else if (this.currentState === 'ESCUCHANDO') {
        const colSeed = p.col * 1.25;
        const env = Math.abs(Math.sin(this.phase * 3.5 + colSeed) * Math.sin(this.phase * 1.2 + colSeed * 0.5));
        const maxBarH = 65; // compacto
        const barH = 12 + env * maxBarH;
        const spanW = this.W * 0.8;
        const colX = (this.W - spanW) / 2 + (p.col + 0.5) * (spanW / this.COLS);
        const filledRows = Math.max(1, Math.round((barH / maxBarH) * this.rowsPerCol));

        p.tx = colX;
        p.ty = p.rowInCol < filledRows
          ? barBaseY - (p.rowInCol / this.rowsPerCol) * maxBarH
          : barBaseY;

      } else if (this.currentState === 'PENSANDO') {
        const dir = p.arm === 0 ? 1 : -1;
        const angle = nx * Math.PI * 6 * dir + this.phase * dir * 1.5;
        const r = 8 + nx * 40;
        p.tx = this.cx + Math.cos(angle) * r;
        p.ty = this.cy + Math.sin(angle) * r * 0.75;

      } else if (this.currentState === 'HABLANDO') {
        const ringIdx = i % 4;
        const angle = nx * Math.PI * 2 + this.phase * (ringIdx % 2 === 0 ? 1.5 : -1.2);
        const voiceAmp = Math.pow(Math.abs(Math.sin(this.phase * 3.8 + p.seed * 0.2)), 2.2) * 20;
        
        let baseR = 12;
        if (ringIdx === 1) baseR = 24;
        else if (ringIdx === 2) baseR = 36;
        else if (ringIdx === 3) baseR = 48;

        const r = baseR + (ringIdx === 0 ? voiceAmp * 0.4 : voiceAmp * (ringIdx / 3));
        p.tx = this.cx + Math.cos(angle) * r;
        p.ty = this.cy + Math.sin(angle) * r * 0.78;

      } else if (this.currentState === 'EJECUTANDO') {
        if (i < 96) {
          // Vértices del cubo 3D
          const edgeIdx = Math.floor(i / 8) % 12;
          const edgeT = (i % 8) / 8;
          const edge = this.CUBE_EDGES[edgeIdx];
          
          const v1 = this.CUBE_VERTICES[edge[0]];
          const v2 = this.CUBE_VERTICES[edge[1]];

          const x3d = v1[0] + (v2[0] - v1[0]) * edgeT;
          const y3d = v1[1] + (v2[1] - v1[1]) * edgeT;
          const z3d = v1[2] + (v2[2] - v1[2]) * edgeT;

          const pt3d = this.get3DCubePoint(x3d, y3d, z3d, this.phase * 1.6, this.phase * 1.1);
          p.tx = pt3d.x;
          p.ty = pt3d.y;

        } else if (i < 130) {
          // Anillo flotante diana
          const a = ((i - 96) / 34) * Math.PI * 2 - this.phase * 2.2;
          const r = 48 + Math.sin(this.phase * 3 + p.seed) * 3;
          p.tx = this.cx + Math.cos(a) * r;
          p.ty = this.cy + Math.sin(a) * r * 0.8 + 4;

        } else {
          // Destellos cuánticos de emisión radial
          const a = (i / 30) * Math.PI * 2;
          const pulseDist = ((this.phase * 2.5 + (i % 5) * 0.2) % 1) * 50;
          p.tx = this.cx + Math.cos(a) * pulseDist;
          p.ty = this.cy + Math.sin(a) * pulseDist * 0.8 + 4;
        }

      } else if (this.currentState === 'AVISO') {
        const angle = nx * Math.PI * 2;
        const r = 32 + Math.sin(this.phase * 0.9 + p.seed) * 4;
        p.tx = this.cx + Math.cos(angle) * r;
        p.ty = this.cy + Math.sin(angle) * r * 0.8;

      } else if (this.currentState === 'ALERTA') {
        const angle = nx * Math.PI * 2 + this.phase * 3;
        const r = 48 + Math.sin(this.phase * 11 + p.seed * 3) * 12;
        p.tx = this.cx + Math.cos(angle) * r;
        p.ty = this.cy + Math.sin(angle) * r;

      } else if (this.currentState === 'GAMING') {
        if (i < 65) {
          const pt = this.getGamepadContourPoint(i / 65);
          p.tx = pt.x;
          p.ty = pt.y;
        } else if (i < 85) {
          // D-Pad
          const idx = i - 65;
          const arm = Math.floor(idx / 5);
          const step = (idx % 5) * 3;
          const dpadCx = this.cx - 30, dpadCy = this.cy - 5;
          if (arm === 0) { p.tx = dpadCx; p.ty = dpadCy - 3 - step; }
          else if (arm === 1) { p.tx = dpadCx + 3 + step; p.ty = dpadCy; }
          else if (arm === 2) { p.tx = dpadCx; p.ty = dpadCy + 3 + step; }
          else { p.tx = dpadCx - 3 - step; p.ty = dpadCy; }
        } else if (i < 105) {
          // Botones de acción ABXY
          const idx = i - 85;
          const btnIdx = Math.floor(idx / 5);
          const subAngle = (idx % 5) / 5 * Math.PI * 2 + this.phase * 2;
          const btnCx = this.cx + 30, btnCy = this.cy - 5;
          let ox = 0, oy = 0;
          if (btnIdx === 0) { ox = 0; oy = -10; }
          else if (btnIdx === 1) { ox = 10; oy = 0; }
          else if (btnIdx === 2) { ox = 0; oy = 10; }
          else { ox = -10; oy = 0; }
          p.tx = btnCx + ox + Math.cos(subAngle) * 3;
          p.ty = btnCy + oy + Math.sin(subAngle) * 3;
        } else if (i < 125) {
          // Joystick Izquierdo
          const a = ((i - 105) / 20) * Math.PI * 2 + this.phase * 1.5;
          p.tx = (this.cx - 15) + Math.cos(a) * 6;
          p.ty = (this.cy + 8) + Math.sin(a) * 6;
        } else if (i < 145) {
          // Joystick Derecho
          const a = ((i - 125) / 20) * Math.PI * 2 - this.phase * 1.5;
          p.tx = (this.cx + 15) + Math.cos(a) * 6;
          p.ty = (this.cy + 8) + Math.sin(a) * 6;
        } else {
          // Botón central de menú
          const a = (i / 15) * Math.PI * 2 + this.phase * 2;
          p.tx = this.cx + Math.cos(a) * 5;
          p.ty = (this.cy - 7) + Math.sin(a) * 5;
        }
      }
    });
  }

  drawBinaryWaterfall(red, green, blue) {
    this.ctx.font = '8px "JetBrains Mono", monospace';
    this.ctx.textAlign = 'center';

    this.binaryDrops.forEach(drop => {
      drop.y += drop.speed;
      if (drop.y - drop.length * 9 > this.H) {
        drop.y = -10;
        drop.speed = 1.0 + Math.random() * 1.5;
        for (let k = 0; k < drop.chars.length; k++) {
          if (Math.random() < 0.35) drop.chars[k] = Math.random() > 0.5 ? '1' : '0';
        }
      }

      for (let j = 0; j < drop.length; j++) {
        const charY = drop.y - j * 9;
        if (charY < 0 || charY > this.H) continue;

        const isHead = (j === 0);
        const alpha = isHead ? 0.25 : 0.12 * (1 - j / drop.length);
        this.ctx.fillStyle = `rgba(${red},${green},${blue},${alpha})`;
        this.ctx.fillText(drop.chars[j], drop.x, charY);
      }
    });
  }

  drawExtras(rgb) {
    const [red, green, blue] = rgb;

    if (this.currentState === 'PENSANDO') {
      this.ctx.lineWidth = 0.5;
      for (let i = 0; i < this.N - 1; i++) {
        const p1 = this.particles[i], p2 = this.particles[i + 1];
        if (p1.arm !== p2.arm) continue;
        const dist = Math.hypot(p1.x - p2.x, p1.y - p2.y);
        if (dist < 22) {
          this.ctx.strokeStyle = `rgba(${red},${green},${blue},${0.3 * (1 - dist / 22)})`;
          this.ctx.beginPath();
          this.ctx.moveTo(p1.x, p1.y);
          this.ctx.lineTo(p2.x, p2.y);
          this.ctx.stroke();
        }
      }
    }

    if (this.currentState === 'HABLANDO') {
      for (let k = 1; k <= 4; k++) {
        const radiusBase = k * 12;
        const wavePulse = Math.pow(Math.abs(Math.sin(this.phase * 3.8)), 2) * 4;
        this.ctx.lineWidth = 0.9;
        this.ctx.strokeStyle = `rgba(${red},${green},${blue},${0.3 - k * 0.05})`;
        this.ctx.beginPath();
        this.ctx.ellipse(this.cx, this.cy, radiusBase + wavePulse, (radiusBase + wavePulse) * 0.78, 0, 0, Math.PI * 2);
        this.ctx.stroke();
      }

      this.ctx.lineWidth = 1.1;
      this.ctx.strokeStyle = `rgba(${red},${green},${blue},0.5)`;
      this.ctx.beginPath();
      const halfW = 60;
      for (let x = -halfW; x <= halfW; x += 3) {
        const normX = x / halfW;
        const envelope = Math.cos(normX * Math.PI * 0.5);
        const waveY = this.cy + Math.sin(x * 0.2 + this.phase * 7) * Math.sin(x * 0.06 - this.phase * 3) * 11 * envelope;
        if (x === -halfW) this.ctx.moveTo(this.cx + x, waveY);
        else this.ctx.lineTo(this.cx + x, waveY);
      }
      this.ctx.stroke();

      this.ctx.fillStyle = `rgba(${red},${green},${blue},0.12)`;
      this.ctx.beginPath();
      this.ctx.arc(this.cx, this.cy, 14, 0, Math.PI * 2);
      this.ctx.fill();
    }

    if (this.currentState === 'EJECUTANDO') {
      // Barra de carga de progreso superior compacta
      const progWidth = 90;
      const progX = this.cx - progWidth / 2;
      const progY = this.cy - 50;
      this.ctx.lineWidth = 0.8;
      this.ctx.strokeStyle = `rgba(${red},${green},${blue},0.4)`;
      this.ctx.strokeRect(progX, progY, progWidth, 5);

      const fillVal = ((this.phase * 0.4) % 1);
      this.ctx.fillStyle = `rgba(${red},${green},${blue},0.75)`;
      this.ctx.fillRect(progX + 1, progY + 1, (progWidth - 2) * fillVal, 3);

      this.ctx.font = '7.5px "JetBrains Mono", monospace';
      this.ctx.fillStyle = `rgba(${red},${green},${blue},0.9)`;
      this.ctx.fillText('CPU // TASK_RUNNING', this.cx - 36, this.cy - 57);

      // Hipercubo 3D
      const pts3d = this.CUBE_VERTICES.map(v => this.get3DCubePoint(v[0], v[1], v[2], this.phase * 1.6, this.phase * 1.1));
      this.ctx.lineWidth = 1.0;
      this.ctx.strokeStyle = `rgba(${red},${green},${blue},0.5)`;
      this.CUBE_EDGES.forEach(edge => {
        const p1 = pts3d[edge[0]];
        const p2 = pts3d[edge[1]];
        this.ctx.beginPath();
        this.ctx.moveTo(p1.x, p1.y);
        this.ctx.lineTo(p2.x, p2.y);
        this.ctx.stroke();
      });

      // Diana circular
      this.ctx.lineWidth = 0.8;
      this.ctx.strokeStyle = `rgba(${red},${green},${blue},0.3)`;
      this.ctx.beginPath();
      this.ctx.arc(this.cx, this.cy + 4, 48, 0, Math.PI * 2);
      this.ctx.stroke();

      // Marcas cruzadas
      const markR = 48;
      for (let m = 0; m < 4; m++) {
        const a = (m * Math.PI) / 2 + this.phase * 0.5;
        this.ctx.beginPath();
        this.ctx.moveTo(this.cx + Math.cos(a) * (markR - 4), this.cy + Math.sin(a) * (markR - 4) * 0.8 + 4);
        this.ctx.lineTo(this.cx + Math.cos(a) * (markR + 4), this.cy + Math.sin(a) * (markR + 4) * 0.8 + 4);
        this.ctx.stroke();
      }
    }

    if (this.currentState === 'AVISO') {
      const t = (this.phase * 0.4) % 1;
      this.ctx.strokeStyle = `rgba(${red},${green},${blue},${0.4 * (1 - t)})`;
      this.ctx.lineWidth = 1.0;
      this.ctx.beginPath();
      this.ctx.arc(this.cx, this.cy, 8 + t * 45, 0, Math.PI * 2);
      this.ctx.stroke();
    }

    if (this.currentState === 'ALERTA') {
      for (let k = 0; k < 3; k++) {
        const t = ((this.phase * 2.0 + k * 0.33) % 1);
        this.ctx.strokeStyle = `rgba(${red},${green},${blue},${0.45 * (1 - t)})`;
        this.ctx.lineWidth = 1.2;
        this.ctx.beginPath();
        this.ctx.arc(this.cx, this.cy, 6 + t * 55, 0, Math.PI * 2);
        this.ctx.stroke();
      }
    }

    if (this.currentState === 'GAMING') {
      // Vector de contorno del mando
      this.ctx.lineWidth = 1.1;
      this.ctx.strokeStyle = `rgba(${red},${green},${blue},0.55)`;
      this.ctx.beginPath();
      const totalSteps = 60;
      for (let s = 0; s <= totalSteps; s++) {
        const pt = this.getGamepadContourPoint(s / totalSteps);
        if (s === 0) this.ctx.moveTo(pt.x, pt.y);
        else this.ctx.lineTo(pt.x, pt.y);
      }
      this.ctx.closePath();
      this.ctx.stroke();

      this.ctx.fillStyle = `rgba(${red},${green},${blue},0.05)`;
      this.ctx.fill();

      // Cruceta (D-pad)
      const dpadCx = this.cx - 30, dpadCy = this.cy - 5;
      this.ctx.lineWidth = 1.0;
      this.ctx.strokeStyle = `rgba(${red},${green},${blue},0.5)`;
      this.ctx.beginPath();
      this.ctx.moveTo(dpadCx - 10, dpadCy); this.ctx.lineTo(dpadCx + 10, dpadCy);
      this.ctx.moveTo(dpadCx, dpadCy - 10); this.ctx.lineTo(dpadCx, dpadCy + 10);
      this.ctx.stroke();

      // Botones ABXY
      const btnCx = this.cx + 30, btnCy = this.cy - 5;
      const offsets = [[0,-10], [10,0], [0,10], [-10,0]];
      this.ctx.lineWidth = 0.8;
      this.ctx.strokeStyle = `rgba(${red},${green},${blue},0.65)`;
      offsets.forEach(([ox, oy]) => {
        this.ctx.beginPath();
        this.ctx.arc(btnCx + ox, btnCy + oy, 3.2, 0, Math.PI * 2);
        this.ctx.stroke();
      });

      // Joysticks analógicos
      const jL = { x: this.cx - 15, y: this.cy + 8 };
      this.ctx.beginPath(); this.ctx.arc(jL.x, jL.y, 7, 0, Math.PI * 2); this.ctx.stroke();
      this.ctx.beginPath(); this.ctx.arc(jL.x + Math.cos(this.phase * 3) * 1.5, jL.y + Math.sin(this.phase * 3) * 1.5, 2, 0, Math.PI * 2); this.ctx.stroke();

      const jR = { x: this.cx + 15, y: this.cy + 8 };
      this.ctx.beginPath(); this.ctx.arc(jR.x, jR.y, 7, 0, Math.PI * 2); this.ctx.stroke();
      this.ctx.beginPath(); this.ctx.arc(jR.x - Math.cos(this.phase * 3) * 1.5, jR.y - Math.sin(this.phase * 3) * 1.5, 2, 0, Math.PI * 2); this.ctx.stroke();

      // Botón central
      this.ctx.beginPath();
      this.ctx.arc(this.cx, this.cy - 7, 5, 0, Math.PI * 2);
      this.ctx.stroke();

      // Triggers traseros (L/R Bumpers)
      this.ctx.lineWidth = 1.1;
      this.ctx.strokeStyle = `rgba(${red},${green},${blue},0.5)`;
      this.ctx.beginPath();
      this.ctx.arc(this.cx - 32, this.cy - 20, 11, Math.PI * 1.1, Math.PI * 1.6);
      this.ctx.stroke();
      this.ctx.beginPath();
      this.ctx.arc(this.cx + 32, this.cy - 20, 11, Math.PI * 1.4, Math.PI * 1.9);
      this.ctx.stroke();
    }
  }

  startRenderLoop() {
    const render = () => {
      this.phase += 0.022;
      this.frameCount++;

      const now = performance.now();
      if (now - this.lastTime >= 1000) {
        this.fpsValue = this.frameCount;
        const elFps = document.getElementById('holoFpsCount');
        if (elFps) elFps.textContent = this.fpsValue;
        this.frameCount = 0;
        this.lastTime = now;
      }

      // Estilo de fundido para estela de partículas
      this.ctx.fillStyle = 'rgba(3, 7, 10, 0.35)';
      this.ctx.fillRect(0, 0, this.W, this.H);

      this.assignTargets();

      const s = this.STATES[this.currentState];
      const rgb = this.hexToRgb(s.color);
      const [red, green, blue] = rgb;

      // 1. Dibujar cascada binaria Matrix de fondo
      this.drawBinaryWaterfall(red, green, blue);

      // 2. Efectos extras del estado
      this.drawExtras(rgb);

      const ease = this.currentState === 'ALERTA' ? 0.22
                 : this.currentState === 'GAMING' ? 0.18
                 : this.currentState === 'EJECUTANDO' ? 0.18
                 : this.currentState === 'HABLANDO' ? 0.18
                 : 0.08;

      // 3. Renderizar y animar partículas hacia sus coordenadas target
      this.particles.forEach(p => {
        p.x += (p.tx - p.x) * ease;
        p.y += (p.ty - p.y) * ease;

        const jitter = (this.currentState === 'ALERTA')
          ? (Math.random() - 0.5) * 2.2
          : (this.currentState === 'EJECUTANDO') ? (Math.random() - 0.5) * 1.2
          : (this.currentState === 'GAMING') ? (Math.random() - 0.5) * 0.6 : 0;

        this.ctx.beginPath();
        this.ctx.arc(p.x + jitter, p.y + jitter, p.size, 0, Math.PI * 2);
        this.ctx.fillStyle = `rgba(${red},${green},${blue}, ${p.alpha})`;

        this.ctx.shadowColor = s.color;
        this.ctx.shadowBlur = (['ALERTA', 'GAMING', 'HABLANDO', 'EJECUTANDO'].includes(this.currentState)) ? 8 : 4;
        this.ctx.fill();
      });

      this.ctx.shadowBlur = 0;

      requestAnimationFrame(render);
    };

    requestAnimationFrame(render);
  }
}

// Inicialización e integración con EmoCanvasFace
document.addEventListener('DOMContentLoaded', () => {
  // Crear el HUD Holográfico
  window.holoHud = new HoloHud('holoCanvas', 'holoStageContainer');

  // Interceptar la instancia de EmoCanvasFace (si ya fue creada)
  hookEmoFace();
});

function hookEmoFace() {
  if (window.emoFace) {
    const originalSetEstado = window.emoFace.setEstado.bind(window.emoFace);
    window.emoFace.setEstado = function(nuevo_estado, msg = '') {
      originalSetEstado(nuevo_estado, msg);
      if (window.holoHud) {
        window.holoHud.mapAndSetEstado(nuevo_estado, msg);
      }
    };

    if (window.emoFace.setClima) {
      const originalSetClima = window.emoFace.setClima.bind(window.emoFace);
      window.emoFace.setClima = function(climaCondicion) {
        originalSetClima(climaCondicion);
        if (window.holoHud) {
          window.holoHud.mapAndSetEstado(climaCondicion);
        }
      };
    }
  } else {
    // Si aún no está disponible (tiempos de inicialización asíncronos), reintentar en 50ms
    setTimeout(hookEmoFace, 50);
  }
}

/**
 * ═══════════════════════════════════════════════════════════════
 *  AnimeAvatar Engine — Interactive SVG + Anime.js Robot Avatar
 *  Integrado para Argus OmniAssistant PyWebView HUD
 * ═══════════════════════════════════════════════════════════════
 */

'use strict';

(function() {
  const THEMES = {
    cyan:   { main: '#00f0ff', glow: 'rgba(0, 240, 255, 0.5)', soft: 'rgba(0, 240, 255, 0.12)' },
    yellow: { main: '#ffd700', glow: 'rgba(255, 215, 0, 0.5)', soft: 'rgba(255, 215, 0, 0.12)' },
    green:  { main: '#10b981', glow: 'rgba(16, 185, 129, 0.5)', soft: 'rgba(16, 185, 129, 0.12)' },
    orange: { main: '#ff6b00', glow: 'rgba(255, 107, 0, 0.5)', soft: 'rgba(255, 107, 0, 0.12)' },
    pink:   { main: '#ff007f', glow: 'rgba(255, 0, 127, 0.5)', soft: 'rgba(255, 0, 127, 0.12)' },
    red:    { main: '#ff2a5f', glow: 'rgba(255, 42, 95, 0.5)', soft: 'rgba(255, 42, 95, 0.12)' }
  };

  let activeTimeline = null;
  let activeAnimations = [];
  let currentEasing = 'easeInOutSine';
  let soundEnabled = true;
  let audioCtx = null;

  /**
   * Sintetizador Web Audio API para sonidos de robot Argus
   */
  function playRobotBeep(freq = 600, duration = 0.12, type = 'sine') {
    if (!soundEnabled) return;
    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(freq * 1.5, audioCtx.currentTime + duration);

      gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start();
      osc.stop(audioCtx.currentTime + duration);
    } catch (e) {
      // Ignorar error de audio si no hay permisos de reproducción automática
    }
  }

  function playSadWhine() {
    if (!soundEnabled) return;
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') audioCtx.resume();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(650, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(220, audioCtx.currentTime + 0.4);
      gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.4);
    } catch(e){}
  }

  /**
   * Construye la pantalla SVG del display OLED del Robot
   */
  function buildHologramSVG(container) {
    let eqHTML = '';
    for (let i = 0; i < 8; i++) {
      eqHTML += `<rect class="eq-bar" x="${60 + i * 16}" y="172" width="10" height="20" rx="3" fill="var(--theme-color)" opacity="0" transform-origin="${60 + i * 16} 182" />`;
    }

    let matrixHTML = '';
    for (let i = 0; i < 16; i++) {
      const mx = 20 + (i % 8) * 26;
      const my = 20 + Math.floor(i / 8) * 30;
      matrixHTML += `<text class="matrix-pixel" x="${mx}" y="${my}" fill="#10b981" font-family="monospace" font-size="12" opacity="0">01</text>`;
    }

    container.innerHTML = `
      <svg class="emo-display-svg" viewBox="0 0 240 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id="emo-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <!-- Fondo Lluvia Matrix -->
        <g id="matrix-layer">${matrixHTML}</g>

        <!-- Ondas emitidas por las copas de audífonos A10 -->
        <g id="ear-cup-waves">
          <path class="ear-wave left-ear-wave" d="M 16,75 Q 4,95 16,115" fill="none" stroke="var(--theme-color)" stroke-width="2.5" stroke-linecap="round" opacity="0" filter="url(#emo-glow)" />
          <path class="ear-wave left-ear-wave" d="M 26,65 Q 12,95 26,125" fill="none" stroke="var(--theme-color)" stroke-width="2" stroke-linecap="round" opacity="0" filter="url(#emo-glow)" />
          <path class="ear-wave right-ear-wave" d="M 224,75 Q 236,95 224,115" fill="none" stroke="var(--theme-color)" stroke-width="2.5" stroke-linecap="round" opacity="0" filter="url(#emo-glow)" />
          <path class="ear-wave right-ear-wave" d="M 214,65 Q 228,95 214,125" fill="none" stroke="var(--theme-color)" stroke-width="2" stroke-linecap="round" opacity="0" filter="url(#emo-glow)" />
        </g>

        <!-- Ring giratorio de procesamiento -->
        <circle id="processing-spinner" cx="120" cy="95" r="36" fill="none" stroke="var(--theme-color)" stroke-width="3" stroke-dasharray="24 16" transform-origin="120 95" opacity="0" filter="url(#emo-glow)" />

        <!-- Línea láser de escaneo en ejecución -->
        <line id="laser-scan-line" x1="20" y1="95" x2="220" y2="95" stroke="var(--theme-color)" stroke-width="2" filter="url(#emo-glow)" opacity="0" />

        <!-- HUD Analítico para modo Mentor -->
        <g id="mentor-hud" opacity="0">
          <circle cx="120" cy="95" r="48" fill="none" stroke="var(--theme-color)" stroke-width="1" stroke-dasharray="8 6" transform-origin="120 95" />
          <path d="M 32,55 L 32,45 L 42,45 M 208,55 L 208,45 L 198,45 M 32,135 L 32,145 L 42,145 M 208,135 L 208,145 L 198,145" fill="none" stroke="var(--theme-color)" stroke-width="2" />
          <text x="120" y="168" fill="var(--theme-color)" font-family="monospace" font-size="8" text-anchor="middle" letter-spacing="1">ANALYTICAL ENGINE v4.0</text>
        </g>

        <!-- HUD Gaming (D-Pad & Botones Arcade ABXY) -->
        <g id="gaming-hud" opacity="0">
          <g transform="translate(14, 132)">
            <path d="M 10,0 L 16,0 L 16,10 L 26,10 L 26,16 L 16,16 L 16,26 L 10,26 L 10,16 L 0,16 L 0,10 L 10,10 Z" fill="#0f172a" stroke="var(--theme-color)" stroke-width="1.5" filter="url(#emo-glow)" />
            <polygon points="13,2 10,6 16,6" fill="#00f0ff" class="dpad-dir dpad-up" />
            <polygon points="13,24 10,20 16,20" fill="#00f0ff" class="dpad-dir dpad-down" />
            <polygon points="2,13 6,10 6,16" fill="#00f0ff" class="dpad-dir dpad-left" />
            <polygon points="24,13 20,10 20,16" fill="#00f0ff" class="dpad-dir dpad-right" />
          </g>

          <g transform="translate(196, 132)">
            <circle class="game-btn game-btn-y" cx="13" cy="3" r="4.5" fill="#ffd700" filter="url(#emo-glow)" />
            <text x="13" y="5.5" fill="#000" font-family="sans-serif" font-weight="900" font-size="5.5" text-anchor="middle">Y</text>
            <circle class="game-btn game-btn-x" cx="3" cy="13" r="4.5" fill="#38bdf8" filter="url(#emo-glow)" />
            <text x="3" y="15.5" fill="#000" font-family="sans-serif" font-weight="900" font-size="5.5" text-anchor="middle">X</text>
            <circle class="game-btn game-btn-b" cx="23" cy="13" r="4.5" fill="#ff2a5f" filter="url(#emo-glow)" />
            <text x="23" y="15.5" fill="#000" font-family="sans-serif" font-weight="900" font-size="5.5" text-anchor="middle">B</text>
            <circle class="game-btn game-btn-a" cx="13" cy="23" r="4.5" fill="#10b981" filter="url(#emo-glow)" />
            <text x="13" y="25.5" fill="#000" font-family="sans-serif" font-weight="900" font-size="5.5" text-anchor="middle">A</text>
          </g>
        </g>

        <!-- Triángulo de alerta warning -->
        <g id="warning-hud" opacity="0">
          <polygon points="120,38 102,68 138,68" fill="none" stroke="#ff6b00" stroke-width="2.5" />
          <text x="120" y="63" fill="#ff6b00" font-family="sans-serif" font-weight="bold" font-size="12" text-anchor="middle">!</text>
        </g>

        <!-- Barra superior de estado -->
        <g id="status-bar" opacity="0.85">
          <rect x="15" y="12" width="22" height="11" rx="2" fill="none" stroke="#64748b" stroke-width="1.5" />
          <rect x="17" y="14" width="16" height="7" rx="1" fill="#10b981" />
          <rect x="37" y="15" width="2" height="5" fill="#64748b" />
          <text x="44" y="21" fill="#94a3b8" font-family="sans-serif" font-size="9" font-weight="bold">98%</text>
          <text x="120" y="22" fill="var(--theme-color)" font-family="sans-serif" font-size="12" font-weight="900" text-anchor="middle" letter-spacing="1.5">ARGUS</text>
          <path d="M 195,14 Q 200,10 205,14 M 197,17 Q 200,14 203,17 M 200,20 L 200,21" fill="none" stroke="#64748b" stroke-width="1.5" stroke-linecap="round" />
          <circle cx="218" cy="16" r="3" fill="#38bdf8" />
        </g>

        <!-- Grupo principal de ojos LED y expresiones -->
        <g id="emo-eyes-group" transform-origin="120 100">
          <path id="angry-brow-left" d="M 40,55 L 95,72" stroke="#ff2a5f" stroke-width="6" stroke-linecap="round" opacity="0" />
          <path id="angry-brow-right" d="M 200,55 L 145,72" stroke="#ff2a5f" stroke-width="6" stroke-linecap="round" opacity="0" />

          <g id="error-x-group" opacity="0">
            <path d="M 52,75 L 92,115 M 92,75 L 52,115" stroke="#ff2a5f" stroke-width="7" stroke-linecap="round" />
            <path d="M 148,75 L 188,115 M 188,75 L 148,115" stroke="#ff2a5f" stroke-width="7" stroke-linecap="round" />
          </g>

          <rect id="emo-left-eye" class="emo-eye" x="42" y="65" width="60" height="60" rx="18" fill="var(--theme-color)" filter="url(#emo-glow)" transform-origin="72 95" />
          <rect id="emo-right-eye" class="emo-eye" x="138" y="65" width="60" height="60" rx="18" fill="var(--theme-color)" filter="url(#emo-glow)" transform-origin="168 95" />

          <circle id="emo-sad-tear" cx="185" cy="115" r="4" fill="#00f0ff" filter="url(#emo-glow)" opacity="0" />

          <!-- Mejillas con barras ecualizadoras al hablar -->
          <g id="speaking-cheek-bars" opacity="0">
            <line class="speaking-bar" x1="16" y1="135" x2="16" y2="155" stroke="var(--theme-color)" stroke-width="3" stroke-linecap="round" transform-origin="16 145" />
            <line class="speaking-bar" x1="23" y1="130" x2="23" y2="160" stroke="var(--theme-color)" stroke-width="3" stroke-linecap="round" transform-origin="23 145" />
            <line class="speaking-bar" x1="30" y1="136" x2="30" y2="154" stroke="var(--theme-color)" stroke-width="3" stroke-linecap="round" transform-origin="30 145" />
            <line class="speaking-bar" x1="210" y1="136" x2="210" y2="154" stroke="var(--theme-color)" stroke-width="3" stroke-linecap="round" transform-origin="210 145" />
            <line class="speaking-bar" x1="217" y1="130" x2="217" y2="160" stroke="var(--theme-color)" stroke-width="3" stroke-linecap="round" transform-origin="217 145" />
            <line class="speaking-bar" x1="224" y1="135" x2="224" y2="155" stroke="var(--theme-color)" stroke-width="3" stroke-linecap="round" transform-origin="224 145" />
          </g>

          <path id="emo-mouth" d="M 102,142 Q 120,154 138,142" fill="none" stroke="var(--theme-color)" stroke-width="4" stroke-linecap="round" filter="url(#emo-glow)" transform-origin="120 145" />

          <path id="understood-sparkle" d="M 120,135 Q 120,145 130,145 Q 120,145 120,155 Q 120,145 110,145 Q 120,145 120,135" fill="var(--theme-color)" filter="url(#emo-glow)" opacity="0" />

          <g id="emo-sunglasses" transform="translate(0, -70)" opacity="0">
            <path d="M 32,70 L 105,70 L 95,110 L 42,110 Z" fill="#000" stroke="var(--theme-color)" stroke-width="3" />
            <path d="M 135,70 L 208,70 L 198,110 L 145,110 Z" fill="#000" stroke="var(--theme-color)" stroke-width="3" />
            <line x1="105" y1="78" x2="135" y2="78" stroke="var(--theme-color)" stroke-width="4" />
            <line x1="45" y1="78" x2="75" y2="102" stroke="#ffffff" stroke-width="3" opacity="0.7" />
            <line x1="148" y1="78" x2="178" y2="102" stroke="#ffffff" stroke-width="3" opacity="0.7" />
          </g>
        </g>

        <!-- Estrellas de éxito -->
        <g id="success-stars" opacity="0">
          <path class="star-burst" d="M 40,40 L 44,48 L 52,48 L 46,54 L 48,62 L 40,56 L 32,62 L 34,54 L 28,48 L 36,48 Z" fill="#ffd700" filter="url(#emo-glow)" />
          <path class="star-burst" d="M 200,40 L 204,48 L 212,48 L 206,54 L 208,62 L 200,56 L 192,62 L 194,54 L 188,48 L 196,48 Z" fill="#ffd700" filter="url(#emo-glow)" />
        </g>

        <g id="eq-group">${eqHTML}</g>

        <!-- Zzz para reposo / sleep -->
        <g id="zzz-group">
          <text class="zzz-letter" x="175" y="60" fill="var(--theme-color)" font-family="sans-serif" font-size="14" font-weight="bold" opacity="0">Z</text>
          <text class="zzz-letter" x="190" y="45" fill="var(--theme-color)" font-family="sans-serif" font-size="18" font-weight="bold" opacity="0">Z</text>
          <text class="zzz-letter" x="205" y="30" fill="var(--theme-color)" font-family="sans-serif" font-size="22" font-weight="bold" opacity="0">z</text>
        </g>
      </svg>
    `;
  }

  function stopAllAnimations() {
    if (activeTimeline) {
      activeTimeline.pause();
      activeTimeline = null;
    }
    activeAnimations.forEach(anim => anim && anim.pause && anim.pause());
    activeAnimations = [];
  }

  function setTheme(themeName) {
    if (!THEMES[themeName]) return;
    const theme = THEMES[themeName];
    document.documentElement.style.setProperty('--theme-color', theme.main);
    document.documentElement.style.setProperty('--theme-glow', theme.glow);
    document.documentElement.style.setProperty('--theme-soft-bg', theme.soft);
  }

  /**
   * Ejecuta secuencias de animación Anime.js según el estado
   */
  function applyStateAnimation(stateName, speedMultiplier = 1, easingOverride = null) {
    if (typeof anime === 'undefined') return;
    stopAllAnimations();
    const speed = 1 / speedMultiplier;
    const easing = easingOverride || currentEasing;

    document.querySelectorAll('.emo-headphone-cup').forEach(cup => cup.classList.remove('glowing'));
    anime.set('#emo-sunglasses', { translateY: -70, opacity: 0 });
    anime.set('#angry-brow-left, #angry-brow-right', { opacity: 0 });
    anime.set('.eq-bar', { opacity: 0, scaleY: 0 });
    anime.set('.matrix-pixel', { opacity: 0 });
    anime.set('.zzz-letter', { opacity: 0 });
    anime.set('.ear-wave', { opacity: 0, translateX: 0 });
    anime.set('#processing-spinner', { opacity: 0, rotate: 0 });
    anime.set('#laser-scan-line', { opacity: 0, translateY: 0 });
    anime.set('#error-x-group', { opacity: 0 });
    anime.set('#mentor-hud', { opacity: 0 });
    anime.set('#gaming-hud', { opacity: 0 });
    anime.set('#speaking-cheek-bars', { opacity: 0 });
    anime.set('.speaking-bar', { scaleY: 1 });
    anime.set('#warning-hud', { opacity: 0 });
    anime.set('#success-stars', { opacity: 0, scale: 1 });
    anime.set('#understood-sparkle', { opacity: 0, scale: 1 });
    anime.set('#emo-sad-tear', { opacity: 0, translateY: 0 });
    anime.set('#emo-left-eye, #emo-right-eye', { rx: 18, ry: 18, width: 60, height: 60, scaleY: 1, scaleX: 1, scale: 1, opacity: 1, fill: 'var(--theme-color)' });
    anime.set('#emo-eyes-group', { rotate: 0, translateX: 0, translateY: 0, scale: 1 });
    anime.set('.emo-head-casing', { rotate: 0, translateY: 0, rotateX: 0 });
    anime.set('#emo-mouth', { d: 'M 102,142 Q 120,154 138,142', opacity: 1 });

    switch (stateName) {
      case 'idle':
      case 'reposo':
        setTheme('cyan');
        activeTimeline = anime.timeline({ loop: true });
        activeTimeline
          .add({
            targets: '.emo-eye',
            scaleY: [1, 0.08, 1],
            duration: 160 * speed,
            delay: 3200 * speed,
            easing: 'easeInOutQuad'
          })
          .add({
            targets: '#emo-eyes-group',
            translateX: [-8, 8, 0],
            duration: 1000 * speed,
            easing: 'easeInOutSine'
          }, 1200 * speed)
          .add({
            targets: '.emo-head-casing',
            translateY: [-3, 3],
            duration: 2200 * speed,
            direction: 'alternate',
            easing: 'easeInOutSine'
          }, 0);
        break;

      case 'waiting':
        setTheme('cyan');
        activeTimeline = anime.timeline({ loop: true, direction: 'alternate' });
        activeTimeline
          .add({
            targets: '#emo-left-eye, #emo-right-eye',
            scaleY: [1, 0.85, 1],
            rx: [18, 22],
            duration: 2400 * speed,
            easing: 'easeInOutSine'
          })
          .add({
            targets: '.emo-head-casing',
            translateY: [0, 4, 0],
            duration: 2400 * speed,
            easing: 'easeInOutSine'
          }, 0);
        break;

      case 'listening':
      case 'escuchando':
        setTheme('cyan');
        document.querySelectorAll('.emo-headphone-cup').forEach(cup => cup.classList.add('glowing'));

        activeAnimations.push(
          anime({
            targets: '.left-ear-wave',
            translateX: [12, -10],
            opacity: [0, 0.95, 0],
            delay: anime.stagger(220 * speed),
            duration: 1100 * speed,
            loop: true,
            easing: 'easeOutCubic'
          })
        );
        activeAnimations.push(
          anime({
            targets: '.right-ear-wave',
            translateX: [-12, 10],
            opacity: [0, 0.95, 0],
            delay: anime.stagger(220 * speed),
            duration: 1100 * speed,
            loop: true,
            easing: 'easeOutCubic'
          })
        );
        activeAnimations.push(
          anime({
            targets: '.emo-headphone-cup',
            transform: ['scale(1)', 'scale(1.06)', 'scale(1)'],
            duration: 750 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );
        activeAnimations.push(
          anime({
            targets: '#emo-left-eye, #emo-right-eye',
            scaleY: [1, 0.82, 1],
            ry: [18, 14, 18],
            duration: 1100 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutSine'
          })
        );
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            rotate: [-2, 2],
            translateY: [-2, 2],
            duration: 1300 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutSine'
          })
        );
        break;

      case 'thinking':
      case 'processing':
      case 'procesando':
        setTheme('cyan');
        anime.set('#processing-spinner', { opacity: 0.9 });
        activeAnimations.push(
          anime({
            targets: '#processing-spinner',
            rotate: '1turn',
            duration: 1200 * speed,
            loop: true,
            easing: 'linear'
          })
        );
        activeAnimations.push(
          anime({
            targets: '#emo-left-eye, #emo-right-eye',
            rx: [18, 30, 18],
            duration: 900 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );
        break;

      case 'speaking':
      case 'talking':
      case 'hablando':
        setTheme('cyan');
        anime.set('#speaking-cheek-bars', { opacity: 0.85 });
        activeAnimations.push(
          anime({
            targets: '.speaking-bar',
            scaleY: () => anime.random(0.4, 1.45),
            delay: anime.stagger(60 * speed, { from: 'center' }),
            duration: 240 * speed,
            loop: true,
            direction: 'alternate',
            easing: 'easeInOutSine'
          })
        );
        activeAnimations.push(
          anime({
            targets: '#emo-mouth',
            d: [
              { value: 'M 98,140 Q 120,162 142,140' },
              { value: 'M 95,142 Q 120,152 145,142' },
              { value: 'M 102,142 Q 120,148 138,142' },
              { value: 'M 104,140 Q 120,158 136,140' },
              { value: 'M 96,139 Q 120,160 144,139' },
              { value: 'M 100,142 Q 120,149 140,142' }
            ],
            duration: 180 * speed,
            delay: (el, i) => i * 40 * speed,
            loop: true,
            easing: 'easeInOutQuad'
          })
        );
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            translateY: [0, -3.5, 0, -1.5, 0],
            rotate: [-1.5, 1.5, -0.8, 0],
            duration: 1600 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );
        activeTimeline = anime.timeline({ loop: true });
        activeTimeline
          .add({
            targets: '#emo-left-eye, #emo-right-eye',
            scaleY: [1, 0.9, 1.05, 0.95, 1],
            ry: [18, 15, 20, 16, 18],
            duration: 1200 * speed,
            easing: 'easeInOutSine'
          })
          .add({
            targets: '.emo-eye',
            scaleY: [1, 0.08, 1],
            duration: 140 * speed,
            delay: 1500 * speed,
            easing: 'easeInOutQuad'
          });
        break;

      case 'executing':
      case 'ejecutando':
        setTheme('cyan');
        anime.set('#laser-scan-line', { opacity: 0.85 });
        activeAnimations.push(
          anime({
            targets: '#laser-scan-line',
            translateY: [-25, 25],
            duration: 1000 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutSine'
          })
        );
        activeAnimations.push(
          anime({
            targets: '#emo-left-eye, #emo-right-eye',
            scaleY: 0.6,
            ry: 10,
            duration: 500 * speed,
            easing: 'easeInOutSine'
          })
        );
        break;

      case 'error':
        setTheme('red');
        anime.set('#emo-left-eye, #emo-right-eye', { opacity: 0 });
        anime.set('#error-x-group', { opacity: 1 });
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            translateX: [-6, 6, -4, 4, 0],
            duration: 350 * speed,
            loop: true,
            easing: 'easeInOutQuint'
          })
        );
        break;

      case 'gaming':
      case 'gamer':
        setTheme('pink');
        anime.set('#gaming-hud', { opacity: 1 });
        activeAnimations.push(
          anime({
            targets: '.dpad-dir',
            opacity: [0.3, 1, 0.3],
            scale: [1, 1.3, 1],
            delay: anime.stagger(150 * speed),
            duration: 600 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );
        activeAnimations.push(
          anime({
            targets: '.game-btn',
            scale: [1, 1.45, 1],
            delay: anime.stagger(120 * speed, { from: 'center' }),
            duration: 450 * speed,
            loop: true,
            direction: 'alternate',
            easing: 'easeInOutBack'
          })
        );
        activeAnimations.push(
          anime({
            targets: '#emo-left-eye, #emo-right-eye',
            scale: [1, 1.25],
            rx: [18, 8, 22],
            duration: 380 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutBounce'
          })
        );
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            rotate: [-6, 6],
            translateY: [-8, 2],
            duration: 280 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutQuad'
          })
        );
        break;

      case 'mentor':
        setTheme('cyan');
        anime.set('#mentor-hud', { opacity: 0.9 });
        activeAnimations.push(
          anime({
            targets: '#mentor-hud circle',
            rotate: '1turn',
            duration: 3000 * speed,
            loop: true,
            easing: 'linear'
          })
        );
        activeAnimations.push(
          anime({
            targets: '#emo-left-eye, #emo-right-eye',
            scaleY: 0.75,
            rx: 24,
            duration: 600 * speed
          })
        );
        break;

      case 'warning':
      case 'confirm':
        setTheme('orange');
        anime.set('#warning-hud', { opacity: 1 });
        anime.set('#angry-brow-left, #angry-brow-right', { opacity: 1 });
        activeAnimations.push(
          anime({
            targets: '#emo-left-eye, #emo-right-eye',
            scaleY: 0.65,
            ry: 10,
            duration: 400 * speed
          })
        );
        break;

      case 'happy':
        setTheme('yellow');
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            rotate: [-7, 7, -4, 4, 0],
            translateY: [-10, 0],
            duration: 750 * speed,
            easing: 'easeOutElastic(1, .5)'
          })
        );
        activeAnimations.push(
          anime({
            targets: '#emo-left-eye, #emo-right-eye',
            ry: [18, 6],
            duration: 500 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutBack'
          })
        );
        activeTimeline = anime.timeline({ loop: true, direction: 'alternate' });
        activeTimeline.add({
          targets: '#emo-mouth',
          d: [{ value: 'M 95,138 Q 120,165 145,138' }],
          duration: 400 * speed,
          easing: 'easeInOutSine'
        });
        break;

      case 'sad':
        setTheme('cyan');
        anime.set('#emo-sad-tear', { opacity: 1 });
        activeAnimations.push(
          anime({
            targets: '#emo-left-eye, #emo-right-eye',
            scaleY: 0.35,
            ry: 8,
            duration: 1000 * speed,
            easing: 'easeInOutSine'
          })
        );
        activeAnimations.push(
          anime({
            targets: '#emo-mouth',
            d: [{ value: 'M 102,152 Q 120,138 138,152' }],
            duration: 800 * speed
          })
        );
        activeAnimations.push(
          anime({
            targets: '#emo-sad-tear',
            translateY: [0, 45],
            opacity: [1, 0],
            duration: 1500 * speed,
            loop: true,
            easing: 'easeInQuad'
          })
        );
        break;

      default:
        setTheme('cyan');
        activeTimeline = anime.timeline({ loop: true });
        activeTimeline
          .add({
            targets: '.emo-eye',
            scaleY: [1, 0.08, 1],
            duration: 160 * speed,
            delay: 3200 * speed,
            easing: 'easeInOutQuad'
          });
        break;
    }
  }

  /**
   * Controlador UI del Avatar Animado Robot
   */
  class AnimeAvatarEngine {
    constructor() {
      this.currentState = 'idle';
      this.container = null;
      this.chassis = null;
    }

    init(containerEl) {
      this.container = containerEl;
      if (!this.container) return;

      this.renderBody();
      this.bindInteractions();
      this.activateState('idle');
    }

    renderBody() {
      this.container.innerHTML = `
        <div class="emo-chassis-wrapper" id="anime-robot-chassis" title="¡Haz clic en la cabeza de Argus para acariciarlo!">
          <!-- Diadema y Halo acrílico superior -->
          <div class="emo-headphone-arc-container">
            <div class="headband-glass-halo"></div>
            <div class="emo-headphone-arc"></div>
          </div>

          <!-- Audífono Izquierdo con insignia A10 -->
          <div class="emo-headphone-cup left">
            <div class="cup-stem"></div>
            <div class="cup-cushion"></div>
            <div class="cup-outer-plate">
              <div class="cup-text-logo">A10</div>
            </div>
          </div>

          <!-- Audífono Derecho con insignia A10 -->
          <div class="emo-headphone-cup right">
            <div class="cup-stem"></div>
            <div class="cup-cushion"></div>
            <div class="cup-outer-plate">
              <div class="cup-text-logo">A10</div>
            </div>
          </div>

          <!-- Cabeza de cerámica metálica blanca -->
          <div class="emo-head-casing" id="anime-head-casing">
            <!-- Pantalla OLED brillante -->
            <div class="emo-oled-screen">
              <div id="anime-svg-wrapper" style="width:100%; height:100%;"></div>
            </div>
          </div>

          <!-- Base y pies -->
          <div class="emo-feet-stand">
            <div class="emo-foot"></div>
            <div class="emo-foot"></div>
          </div>
        </div>
      `;

      const svgWrapper = document.getElementById('anime-svg-wrapper');
      if (svgWrapper) {
        buildHologramSVG(svgWrapper);
      }

      this.chassis = document.getElementById('anime-robot-chassis');
    }

    bindInteractions() {
      if (this.chassis) {
        this.chassis.addEventListener('click', (e) => {
          e.stopPropagation();
          this.petRobot();
        });
      }
    }

    petRobot() {
      playRobotBeep(800, 0.15);
      setTimeout(() => playRobotBeep(1200, 0.2), 150);
      applyStateAnimation('happy');

      const labelEl = document.getElementById('status-label');
      const sublabelEl = document.getElementById('status-sublabel');
      if (labelEl) {
        labelEl.textContent = '¡ACARICIADO!';
        labelEl.style.color = '#ffd700';
      }
      if (sublabelEl) {
        sublabelEl.textContent = '(*Wiggle de felicidad*)';
      }

      setTimeout(() => {
        this.activateState(this.currentState);
      }, 3500);
    }

    activateState(stateId, customMsg = '') {
      this.currentState = stateId;

      if (stateId === 'happy' || stateId === 'success') {
        playRobotBeep(800, 0.15);
      } else if (stateId === 'listening' || stateId === 'escuchando') {
        playRobotBeep(950, 0.18, 'sine');
      } else if (stateId === 'speaking' || stateId === 'talking' || stateId === 'hablando' || stateId === 'thinking' || stateId === 'procesando') {
        playRobotBeep(700, 0.1);
      } else if (stateId === 'sad' || stateId === 'error') {
        playSadWhine();
      }

      applyStateAnimation(stateId);
    }
  }

  const engine = new AnimeAvatarEngine();
  window.animeAvatarEngine = engine;
  window.setAnimeTheme = setTheme;

})();

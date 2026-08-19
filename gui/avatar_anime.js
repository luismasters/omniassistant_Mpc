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

        <!-- HUD Pantalla: Aviso animado PROCESANDO (reemplaza ojos al procesar) -->
        <g id="processing-hud" opacity="0" transform-origin="120 100">
          <!-- Tarjeta de fondo estilo terminal cibernética -->
          <rect class="proc-bg-card" x="25" y="52" width="190" height="96" rx="14" fill="#040b17" fill-opacity="0.92" stroke="var(--theme-color)" stroke-width="1.8" filter="url(#emo-glow)" />
          
          <!-- Líneas sutiles de escaneo / cuadrícula HUD -->
          <line x1="30" y1="67" x2="210" y2="67" stroke="var(--theme-color)" stroke-width="0.8" stroke-opacity="0.3" stroke-dasharray="3 3" />
          <line x1="30" y1="133" x2="210" y2="133" stroke="var(--theme-color)" stroke-width="0.8" stroke-opacity="0.3" stroke-dasharray="3 3" />

          <!-- Tech brackets / Esquineros -->
          <path class="proc-corner" d="M 32,60 L 32,55 L 40,55 M 208,60 L 208,55 L 200,55 M 32,140 L 32,145 L 40,145 M 208,140 L 208,145 L 200,145" fill="none" stroke="var(--theme-color)" stroke-width="2" stroke-linecap="round" />

          <!-- Cabecera Tech con indicador LIVE -->
          <g class="proc-header" transform="translate(36, 61)">
            <circle class="proc-live-dot" cx="4" cy="0" r="2.8" fill="var(--theme-color)" filter="url(#emo-glow)" />
            <text x="13" y="2.5" fill="var(--theme-color)" font-family="monospace" font-size="7.5" font-weight="bold" letter-spacing="1.2" opacity="0.85">NEURAL CORE // BUSY</text>
            <text x="166" y="2.5" fill="var(--theme-color)" font-family="monospace" font-size="7" font-weight="bold" text-anchor="end" opacity="0.7">ARGUS_AI</text>
          </g>

          <!-- Icono tecnológico central o radar con rotación -->
          <g id="proc-icon-center" transform="translate(120, 88)" transform-origin="120 88">
            <circle class="proc-icon-ring" cx="0" cy="0" r="8" fill="none" stroke="var(--theme-color)" stroke-width="1.2" stroke-dasharray="5 3" opacity="0.8" filter="url(#emo-glow)" />
            <circle class="proc-icon-core" cx="0" cy="0" r="3.5" fill="var(--theme-color)" opacity="0.9" filter="url(#emo-glow)" />
            <path d="M -11,0 L -8,0 M 11,0 L 8,0 M 0,-11 L 0,-8 M 0,11 L 0,8" stroke="var(--theme-color)" stroke-width="1.4" stroke-linecap="round" />
          </g>

          <!-- Texto principal animado PROCESANDO -->
          <text id="proc-main-text" x="120" y="110" fill="var(--theme-color)" font-family="system-ui, -apple-system, sans-serif" font-size="14.5" font-weight="900" text-anchor="middle" letter-spacing="2.8" filter="url(#emo-glow)">PROCESANDO</text>

          <!-- Indicador de actividad con puntos dinámicos en onda -->
          <g id="proc-dots-group" transform="translate(120, 121)">
            <circle class="proc-dot proc-dot-1" cx="-20" cy="0" r="2" fill="var(--theme-color)" filter="url(#emo-glow)" />
            <circle class="proc-dot proc-dot-2" cx="-10" cy="0" r="2" fill="var(--theme-color)" filter="url(#emo-glow)" />
            <circle class="proc-dot proc-dot-3" cx="0" cy="0" r="2.2" fill="var(--theme-color)" filter="url(#emo-glow)" />
            <circle class="proc-dot proc-dot-4" cx="10" cy="0" r="2" fill="var(--theme-color)" filter="url(#emo-glow)" />
            <circle class="proc-dot proc-dot-5" cx="20" cy="0" r="2" fill="var(--theme-color)" filter="url(#emo-glow)" />
          </g>

          <!-- Barra de carga / flujo de datos inferior -->
          <g transform="translate(40, 131)">
            <rect x="0" y="0" width="160" height="4" rx="2" fill="#081326" stroke="var(--theme-color)" stroke-width="0.7" stroke-opacity="0.35" />
            <rect id="proc-progress-fill" x="0" y="0" width="36" height="4" rx="2" fill="var(--theme-color)" filter="url(#emo-glow)" />
          </g>
        </g>

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

        <!-- HUD Pantalla: Aviso animado ATENCIÓN / AVISO (reemplaza ojos en advertencia) -->
        <g id="warning-hud" opacity="0" transform-origin="120 100">
          <!-- Tarjeta de fondo estilo alerta cibernética -->
          <rect class="warn-bg-card" x="25" y="52" width="190" height="96" rx="14" fill="#140802" fill-opacity="0.94" stroke="#ff6b00" stroke-width="1.8" filter="url(#emo-glow)" />
          
          <!-- Líneas de peligro / scanline HUD -->
          <line x1="30" y1="67" x2="210" y2="67" stroke="#ff6b00" stroke-width="0.8" stroke-opacity="0.3" stroke-dasharray="3 3" />
          <line x1="30" y1="133" x2="210" y2="133" stroke="#ff6b00" stroke-width="0.8" stroke-opacity="0.3" stroke-dasharray="3 3" />

          <!-- Tech brackets / Esquineros de alerta -->
          <path class="warn-corner" d="M 32,60 L 32,55 L 40,55 M 208,60 L 208,55 L 200,55 M 32,140 L 32,145 L 40,145 M 208,140 L 208,145 L 200,145" fill="none" stroke="#ff6b00" stroke-width="2" stroke-linecap="round" />

          <!-- Cabecera Tech con indicador de peligro -->
          <g class="warn-header" transform="translate(36, 61)">
            <circle class="warn-live-dot" cx="4" cy="0" r="2.8" fill="#ff6b00" filter="url(#emo-glow)" />
            <text x="13" y="2.5" fill="#ff6b00" font-family="monospace" font-size="7.5" font-weight="bold" letter-spacing="1.2" opacity="0.9">SYSTEM ALERT // AVISO</text>
            <text x="166" y="2.5" fill="#ff6b00" font-family="monospace" font-size="7" font-weight="bold" text-anchor="end" opacity="0.75">PRIORITY_1</text>
          </g>

          <!-- Triángulo de advertencia central animado -->
          <g id="warn-triangle-group" transform="translate(120, 85)" transform-origin="120 85">
            <polygon class="warn-triangle" points="0,-12 -13,10 13,10" fill="#ff6b00" fill-opacity="0.18" stroke="#ff6b00" stroke-width="2" stroke-linejoin="round" filter="url(#emo-glow)" />
            <text x="0" y="7.5" fill="#ff6b00" font-family="sans-serif" font-weight="900" font-size="13" text-anchor="middle" filter="url(#emo-glow)">!</text>
          </g>

          <!-- Texto principal animado ATENCIÓN -->
          <text id="warn-main-text" x="120" y="110" fill="#ff6b00" font-family="system-ui, -apple-system, sans-serif" font-size="14.5" font-weight="900" text-anchor="middle" letter-spacing="2.8" filter="url(#emo-glow)">ATENCIÓN</text>

          <!-- Indicador de pulsos de alerta laterales -->
          <g id="warn-chevrons-group" transform="translate(120, 121)">
            <path class="warn-chev warn-chev-left" d="M -26,-3 L -32,0 L -26,3 M -18,-3 L -24,0 L -18,3" fill="none" stroke="#ff6b00" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" filter="url(#emo-glow)" />
            <circle class="warn-center-dot" cx="0" cy="0" r="2.2" fill="#ff6b00" filter="url(#emo-glow)" />
            <path class="warn-chev warn-chev-right" d="M 26,-3 L 32,0 L 26,3 M 18,-3 L 24,0 L 18,3" fill="none" stroke="#ff6b00" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" filter="url(#emo-glow)" />
          </g>

          <!-- Barra de alerta / hazard bar inferior -->
          <g transform="translate(40, 131)">
            <rect x="0" y="0" width="160" height="4" rx="2" fill="#260f04" stroke="#ff6b00" stroke-width="0.7" stroke-opacity="0.35" />
            <rect id="warn-progress-fill" x="0" y="0" width="36" height="4" rx="2" fill="#ff6b00" filter="url(#emo-glow)" />
          </g>
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



          <path id="emo-mouth" d="M 112,143 C 114,146 126,146 128,143 C 126,147 114,147 112,143 Z" fill="var(--theme-color)" stroke="var(--theme-color)" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" filter="url(#emo-glow)" transform-origin="120 143" />

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
    anime.set('.zzz-letter', { opacity: 0, translateY: 0, translateX: 0, scale: 1 });
    anime.set('.ear-wave', { opacity: 0, translateX: 0 });
    anime.set('#processing-hud', { opacity: 0, scale: 0.95 });
    anime.set('#laser-scan-line', { opacity: 0, translateY: 0 });
    anime.set('#error-x-group', { opacity: 0 });
    anime.set('#mentor-hud', { opacity: 0 });
    anime.set('#gaming-hud', { opacity: 0 });

    anime.set('#warning-hud', { opacity: 0, scale: 0.95 });
    anime.set('#success-stars', { opacity: 0, scale: 1 });
    anime.set('#understood-sparkle', { opacity: 0, scale: 1 });
    anime.set('#emo-sad-tear', { opacity: 0, translateY: 0 });
    anime.set('#emo-left-eye, #emo-right-eye', { rx: 18, ry: 18, width: 60, height: 60, scaleY: 1, scaleX: 1, scale: 1, opacity: 1, fill: 'var(--theme-color)' });
    anime.set('#emo-eyes-group', { rotate: 0, translateX: 0, translateY: 0, scale: 1, opacity: 1 });
    anime.set('.emo-head-casing', { rotate: 0, translateY: 0, rotateX: 0 });
    anime.set('#emo-mouth', { d: 'M 112,143 C 114,146 126,146 128,143 C 126,147 114,147 112,143 Z', opacity: 1, scale: 1 });

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
        // Ocultar completamente ojos, boca y elementos faciales
        anime.set('#emo-eyes-group', { opacity: 0 });
        anime.set('#emo-left-eye, #emo-right-eye', { opacity: 0 });
        anime.set('#emo-mouth', { opacity: 0 });

        // Mostrar HUD de aviso en pantalla PROCESANDO
        anime.set('#processing-hud', { opacity: 1, scale: 1 });
        document.querySelectorAll('.emo-headphone-cup').forEach(cup => cup.classList.add('glowing'));

        // Entrada suave del HUD de Procesamiento
        activeAnimations.push(
          anime({
            targets: '#processing-hud',
            scale: [0.93, 1],
            opacity: [0, 1],
            duration: 260 * speed,
            easing: 'easeOutCubic'
          })
        );

        // Pulso sutil de los bordes de la tarjeta
        activeAnimations.push(
          anime({
            targets: '.proc-bg-card',
            strokeOpacity: [0.5, 1, 0.5],
            duration: 1200 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutSine'
          })
        );

        // Rotación del icono/radar tecnológico central
        activeAnimations.push(
          anime({
            targets: '#proc-icon-center',
            rotate: '1turn',
            duration: 2200 * speed,
            loop: true,
            easing: 'linear'
          })
        );

        // Texto principal PROCESANDO: respiración y brillo rítmico
        activeAnimations.push(
          anime({
            targets: '#proc-main-text',
            opacity: [0.75, 1, 0.75],
            scale: [0.98, 1.02, 0.98],
            transformOrigin: '120px 110px',
            duration: 900 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );

        // Puntos de actividad en ola sincronizada
        activeAnimations.push(
          anime({
            targets: '.proc-dot',
            scale: [0.6, 1.35, 0.6],
            opacity: [0.3, 1, 0.3],
            delay: anime.stagger(120 * speed),
            duration: 750 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );

        // Barra de progreso escaneando/recorriendo fluidamente
        activeAnimations.push(
          anime({
            targets: '#proc-progress-fill',
            translateX: [0, 124],
            width: [24, 48, 24],
            duration: 1100 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutQuad'
          })
        );

        // Punto de estado LIVE parpadeando
        activeAnimations.push(
          anime({
            targets: '.proc-live-dot',
            opacity: [0.2, 1],
            scale: [0.8, 1.25],
            duration: 450 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutQuad'
          })
        );

        // Leve balanceo/flotación pensante de la cabeza
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            translateY: [-3, 3],
            rotate: [-1.2, 1.2],
            duration: 1800 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutSine'
          })
        );
        break;

      case 'speaking':
      case 'talking':
      case 'hablando':
        setTheme('cyan');

        // Animación dinámica de la boca al hablar inspirada en Eilik:
        // Alterna fluidamente entre boca 'O' redonda (Foto 2), semióvalo sonriente relleno (Foto 1), y aperturas silábicas
        activeAnimations.push(
          anime({
            targets: '#emo-mouth',
            d: [
              { value: 'M 114,143 C 114,136 126,136 126,143 C 126,150 114,150 114,143 Z', duration: 150 * speed }, // 'O' redonda de asombro/habla (Foto 2)
              { value: 'M 104,137 C 112,138 128,138 136,137 C 138,154 102,154 104,137 Z', duration: 180 * speed }, // Semióvalo amplio sonrisa abierta (Foto 1)
              { value: 'M 109,140 C 113,138 127,138 131,140 C 133,149 107,149 109,140 Z', duration: 140 * speed }, // Óvalo intermedio
              { value: 'M 116,143 C 116,138 124,138 124,143 C 124,148 116,148 116,143 Z', duration: 130 * speed }, // Círculo pequeño
              { value: 'M 106,138 C 112,139 128,139 134,138 C 136,151 104,151 106,138 Z', duration: 170 * speed }, // Semióvalo medio sonriente (Foto 1)
              { value: 'M 112,143 C 115,144 125,144 128,143 C 125,145 115,145 112,143 Z', duration: 120 * speed }  // Pausa fonética suave
            ],
            loop: true,
            easing: 'easeInOutSine'
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
      case 'atencion':
      case 'atención':
      case 'aviso':
      case 'alerta':
      case 'alert':
      case 'confirm':
        setTheme('orange');
        // Ocultar completamente ojos, boca y elementos faciales
        anime.set('#emo-eyes-group', { opacity: 0 });
        anime.set('#emo-left-eye, #emo-right-eye', { opacity: 0 });
        anime.set('#emo-mouth', { opacity: 0 });

        // Mostrar HUD de aviso en pantalla ATENCIÓN
        anime.set('#warning-hud', { opacity: 1, scale: 1 });
        document.querySelectorAll('.emo-headphone-cup').forEach(cup => cup.classList.add('glowing'));

        // Entrada suave del HUD de Advertencia
        activeAnimations.push(
          anime({
            targets: '#warning-hud',
            scale: [0.93, 1],
            opacity: [0, 1],
            duration: 260 * speed,
            easing: 'easeOutCubic'
          })
        );

        // Pulso sutil de los bordes de la tarjeta
        activeAnimations.push(
          anime({
            targets: '.warn-bg-card',
            strokeOpacity: [0.5, 1, 0.5],
            duration: 900 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutSine'
          })
        );

        // Pulso rítmico del triángulo de advertencia
        activeAnimations.push(
          anime({
            targets: '#warn-triangle-group',
            scale: [0.92, 1.12, 0.92],
            duration: 750 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );

        // Texto principal ATENCIÓN: respiración y brillo rítmico
        activeAnimations.push(
          anime({
            targets: '#warn-main-text',
            opacity: [0.75, 1, 0.75],
            scale: [0.98, 1.02, 0.98],
            transformOrigin: '120px 110px',
            duration: 750 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );

        // Chevrons laterales de alerta en pulso
        activeAnimations.push(
          anime({
            targets: '.warn-chev-left',
            translateX: [2, -3, 2],
            opacity: [0.35, 1, 0.35],
            duration: 650 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );
        activeAnimations.push(
          anime({
            targets: '.warn-chev-right',
            translateX: [-2, 3, -2],
            opacity: [0.35, 1, 0.35],
            duration: 650 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );

        // Barra de progreso de alerta escaneando
        activeAnimations.push(
          anime({
            targets: '#warn-progress-fill',
            translateX: [0, 124],
            width: [24, 48, 24],
            duration: 950 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutQuad'
          })
        );

        // Punto de estado LIVE parpadeando rápido
        activeAnimations.push(
          anime({
            targets: '.warn-live-dot',
            opacity: [0.2, 1],
            scale: [0.8, 1.3],
            duration: 380 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutQuad'
          })
        );

        // Leve movimiento de alerta de la cabeza
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            translateY: [-2.5, 2.5],
            rotate: [-1.2, 1.2],
            duration: 1400 * speed,
            direction: 'alternate',
            loop: true,
            easing: 'easeInOutSine'
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
          d: [{ value: 'M 104,137 C 112,138 128,138 136,137 C 138,154 102,154 104,137 Z' }],
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
            d: [{ value: 'M 108,148 C 114,142 126,142 132,148 C 126,146 114,146 108,148 Z' }],
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

      case 'sleep':
      case 'sleeping':
      case 'dormir':
        setTheme('cyan');
        anime.set('#emo-sad-tear', { opacity: 0 });
        anime.set('#emo-left-eye, #emo-right-eye', { rx: 18, ry: 4, width: 60, height: 60, scaleY: 0.12, opacity: 0.85 });
        anime.set('#emo-mouth', { d: 'M 114,144 C 116,146 124,146 126,144 C 124,146 116,146 114,144 Z', opacity: 0.8 });

        // Letras Zzz subiendo escalonadas y desvaneciéndose
        activeAnimations.push(
          anime({
            targets: '.zzz-letter',
            translateY: [12, -26],
            translateX: [-4, 14],
            scale: [0.65, 1.25],
            opacity: [0, 0.95, 0],
            delay: anime.stagger(650 * speed),
            duration: 2100 * speed,
            loop: true,
            easing: 'easeOutSine'
          })
        );

        // Respiración suave y profunda de la cabeza
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            translateY: [0, 4.5, 0],
            rotate: [-0.6, 0.6, -0.6],
            duration: 3400 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );

        // Leve respiración de los ojos cerrados
        activeTimeline = anime.timeline({ loop: true, direction: 'alternate' });
        activeTimeline.add({
          targets: '#emo-left-eye, #emo-right-eye',
          scaleY: [0.12, 0.05, 0.12],
          duration: 3400 * speed,
          easing: 'easeInOutSine'
        });
        break;

      case 'cool':
      case 'sunglasses':
      case 'lentes':
        setTheme('cyan');
        anime.set('#emo-left-eye, #emo-right-eye', { scaleY: 0.8, opacity: 0.9 });
        anime.set('#emo-mouth', { d: 'M 110,143 C 114,141 127,143 131,140 C 127,147 114,147 110,143 Z', opacity: 1 });

        // Gafas de sol bajando deslizándose con rebote elástico
        activeAnimations.push(
          anime({
            targets: '#emo-sunglasses',
            translateY: [-70, 0],
            opacity: [0, 1],
            duration: 750 * speed,
            easing: 'easeOutBack'
          })
        );

        // Movimiento canchero / cabeceo confiado
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            rotate: [-3.5, 3.5, -2, 2, 0],
            translateY: [0, -3, 0, -1.5, 0],
            duration: 2200 * speed,
            loop: true,
            direction: 'alternate',
            easing: 'easeInOutSine'
          })
        );
        break;

      case 'curious':
      case 'curious_look':
        setTheme('cyan');
        anime.set('#emo-mouth', { d: 'M 115,143 C 115,140 125,140 125,143 C 125,146 115,146 115,143 Z', opacity: 0.9 });

        // Mirada curiosa a los costados
        activeAnimations.push(
          anime({
            targets: '#emo-eyes-group',
            translateX: [0, -14, 0, 14, 0],
            translateY: [0, -3, 0, -3, 0],
            duration: 2800 * speed,
            loop: true,
            easing: 'easeInOutSine'
          })
        );

        // Inclinación de cabeza inquisitiva
        activeAnimations.push(
          anime({
            targets: '.emo-head-casing',
            rotate: [-4.5, 4.5, 0],
            translateY: [-2, 2, 0],
            duration: 2800 * speed,
            loop: true,
            direction: 'alternate',
            easing: 'easeInOutSine'
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
      this.idleHeartbeat = null;
      this.idleActionTimer = null;
      this.isPerformingIdleAction = false;
      this.idleSeconds = 0;
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

    clearIdleTimers() {
      if (this.idleHeartbeat) {
        clearInterval(this.idleHeartbeat);
        this.idleHeartbeat = null;
      }
      if (this.idleActionTimer) {
        clearTimeout(this.idleActionTimer);
        this.idleActionTimer = null;
      }
      this.isPerformingIdleAction = false;
      this.idleSeconds = 0;
    }

    startIdleTracker() {
      this.clearIdleTimers();
      this.idleSeconds = 0;

      // Monitoreo de inactividad cada segundo en estado de reposo
      this.idleHeartbeat = setInterval(() => {
        if (this.currentState !== 'idle' && this.currentState !== 'reposo') {
          this.clearIdleTimers();
          return;
        }

        if (this.isPerformingIdleAction) return;

        this.idleSeconds += 1;

        // A los 16 segundos de inactividad: acción ociosa espontánea (cool con gafas o mirada curiosa)
        if (this.idleSeconds === 16) {
          const action = Math.random() < 0.65 ? 'cool' : 'curious';
          this.triggerTemporaryIdleAction(action, action === 'cool' ? 6500 : 4000);
        }
        // A los 40 segundos de inactividad: entra en modo sueño profundo Zzz
        else if (this.idleSeconds >= 40 && !this.isPerformingIdleAction) {
          this.triggerSleepAction();
        }
      }, 1000);
    }

    triggerTemporaryIdleAction(actionName, durationMs = 6000) {
      if (this.currentState !== 'idle' && this.currentState !== 'reposo') return;
      this.isPerformingIdleAction = true;

      applyStateAnimation(actionName);

      const labelEl = document.getElementById('status-label');
      const sublabelEl = document.getElementById('status-sublabel');

      if (actionName === 'cool') {
        playRobotBeep(850, 0.12);
        setTimeout(() => playRobotBeep(1100, 0.15), 120);
        if (labelEl) { labelEl.textContent = 'MODO COOL'; labelEl.style.color = '#38bdf8'; }
        if (sublabelEl) { sublabelEl.textContent = 'Gafas de sol equipadas 😎'; }
      } else if (actionName === 'curious') {
        playRobotBeep(920, 0.08);
        if (labelEl) { labelEl.textContent = 'OBSERVANDO'; labelEl.style.color = '#00f0ff'; }
        if (sublabelEl) { sublabelEl.textContent = 'Inspeccionando entorno...'; }
      }

      this.idleActionTimer = setTimeout(() => {
        if (this.currentState === 'idle' || this.currentState === 'reposo') {
          this.isPerformingIdleAction = false;
          applyStateAnimation('idle');
          const lbl = document.getElementById('status-label');
          const sub = document.getElementById('status-sublabel');
          if (lbl) { lbl.textContent = 'REPOSO'; lbl.style.color = 'var(--theme-color)'; }
          if (sub) { sub.textContent = 'Vigilancia Pasiva'; }
        }
      }, durationMs);
    }

    triggerSleepAction() {
      if (this.currentState !== 'idle' && this.currentState !== 'reposo') return;
      this.isPerformingIdleAction = true;

      applyStateAnimation('sleep');

      const labelEl = document.getElementById('status-label');
      const sublabelEl = document.getElementById('status-sublabel');
      if (labelEl) { labelEl.textContent = 'EN REPOSO'; labelEl.style.color = '#38bdf8'; }
      if (sublabelEl) { sublabelEl.textContent = 'Zzz... Modo Ahorro'; }
    }

    petRobot() {
      this.clearIdleTimers();
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
      this.clearIdleTimers();

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

      // Iniciar temporizador de reposo para acciones espontáneas
      if (stateId === 'idle' || stateId === 'reposo') {
        this.startIdleTracker();
      }
    }
  }

  const engine = new AnimeAvatarEngine();
  window.animeAvatarEngine = engine;
  window.setAnimeTheme = setTheme;

})();

/**
 * Argus HUD Controller — Premium Chat Edition
 * Claude/ChatGPT-style interface with full markdown support & bulletproof error handling
 */

document.addEventListener('DOMContentLoaded', () => {

  // ─── DOM REFS ──────────────────────────────────────────────────────────
  const body                = document.body;
  const btnChat             = document.getElementById('btnModeChat');
  const btnMentor           = document.getElementById('btnModeMentor');
  const btnGamer            = document.getElementById('btnModeGamer');
  const lblGamerMode        = document.getElementById('lblGamerMode');
  const lblGamepadStatus    = document.getElementById('lblGamepadStatus');
  const headerTitle         = document.getElementById('headerModeTitle');
  const headerSubtitle      = document.getElementById('headerModeSubtitle');
  const chatMessages        = document.getElementById('chatMessages');
  const promptInput         = document.getElementById('promptInput');
  const btnSend             = document.getElementById('btnSend');
  const btnVoice            = document.getElementById('btnVoice');
  const btnClearChat        = document.getElementById('btnClearChat');
  const modelSelect         = document.getElementById('modelSelect');
  const mentorProfileSelect = document.getElementById('mentorProfileSelect');
  const visualModeSelect    = document.getElementById('visualModeSelect');
  const gamepadSelect       = document.getElementById('gamepadSelect');
  const btnWorkspace        = document.getElementById('btnWorkspace');
  const lblWorkspace        = document.getElementById('lblWorkspace');
  const btnUpdateMemoria    = document.getElementById('btnUpdateMemoria');
  const btnClearContext     = document.getElementById('btnClearContext');

  let pyApi           = null;
  let isListening     = false;
  let typingRowEl     = null;
  let archivosAdjuntos = []; // rutas de archivos pendientes de adjuntar

  // Attach menu refs
  const btnAttach      = document.getElementById('btnAttach');
  const attachMenu     = document.getElementById('attachMenu');
  const btnAttachFile  = document.getElementById('btnAttachFile');
  const btnAttachImage = document.getElementById('btnAttachImage');
  const btnAttachProject = document.getElementById('btnAttachProject');

  // ─── PYWEBVIEW BRIDGE ─────────────────────────────────────────────────
  function checkBridgeReady() {
    if (window.pywebview && window.pywebview.api) {
      pyApi = window.pywebview.api;
      console.log('✅ PyWebView Bridge listo.');
      inicializarEstado();
      actualizarMandosGamepad();
      setInterval(actualizarMandosGamepad, 4000);
    }
  }

  window.addEventListener('pywebviewready', checkBridgeReady);
  setTimeout(checkBridgeReady, 100);
  setTimeout(checkBridgeReady, 500);

  // Mensaje de bienvenida inicial
  agregarMensajeSistema('¡Hola, Luis! Soy <strong>Argus</strong> — tu asistente IA. Presiona <strong>F8</strong> o <strong>L3+R3</strong> en tu mando para hablar.');

  // ─── NATIVE HTML5 GAMEPAD CONTROLLER LOGIC (SIN PYGAME / ZERO BLANCO) ──────
  let gamepadComboActivoJS = false;

  async function actualizarMandosGamepad() {
    if (!pyApi || typeof pyApi.listar_mandos_gamepad !== 'function') return;
    try {
      const res = await pyApi.listar_mandos_gamepad();
      if (res && res.exito) {
        if (gamepadSelect) {
          gamepadSelect.innerHTML = '';
          if (!res.mandos || res.mandos.length === 0) {
            const opt = document.createElement('option');
            opt.value = '-1'; opt.innerText = '🎮 No se detectó mando';
            gamepadSelect.appendChild(opt);
          } else {
            const optAll = document.createElement('option');
            optAll.value = '-1';
            optAll.innerText = `🎮 Todos los mandos (${res.mandos.length})`;
            gamepadSelect.appendChild(optAll);

            res.mandos.forEach(m => {
              const opt = document.createElement('option');
              opt.value = m.indice;
              const nombreCorto = m.nombre.length > 25 ? m.nombre.slice(0, 23) + '…' : m.nombre;
              opt.innerText = `🎮 ${nombreCorto}`;
              gamepadSelect.appendChild(opt);
            });
          }
        }
        actualizarBadgeGamepad(res.estado);
      }
    } catch (e) {
      console.error('Error listando mandos:', e);
    }
  }

  window.actualizarMandosGamepad = actualizarMandosGamepad;


  function actualizarBadgeGamepad(estadoGp) {
    if (!lblGamepadStatus) return;
    if (estadoGp && estadoGp.conectado) {
      const nombreCorto = estadoGp.nombre.length > 20 ? estadoGp.nombre.slice(0, 18) + '…' : estadoGp.nombre;
      lblGamepadStatus.innerText = `${nombreCorto}`;
      lblGamepadStatus.style.color = '#00ff9d';
    } else {
      lblGamepadStatus.innerText = 'Sin mando detectado';
      lblGamepadStatus.style.color = '';
    }
  }


  window.addEventListener('gamepadconnected', () => {
    actualizarMandosGamepad();
  });
  window.addEventListener('gamepaddisconnected', () => {
    actualizarMandosGamepad();
  });

  // Bucle de lectura a 60 FPS sin cargar CPU ni Pygame
  function loopGamepadHTML5() {
    const gamepads = (navigator.getGamepads ? navigator.getGamepads() : []);
    let comboPressed = false;

    for (let i = 0; i < gamepads.length; i++) {
      const gp = gamepads[i];
      if (!gp || !gp.buttons) continue;

      // Botones L3 y R3 en HTML5 Standard: 10 y 11 (o 7 y 8 en algunos gamepads)
      const bL3 = (gp.buttons[10] && gp.buttons[10].pressed) || (gp.buttons[7] && gp.buttons[7].pressed);
      const bR3 = (gp.buttons[11] && gp.buttons[11].pressed) || (gp.buttons[8] && gp.buttons[8].pressed);

      if (bL3 && bR3) {
        comboPressed = true;
        break;
      }
    }

    if (pyApi && typeof pyApi.actualizar_estado_gamepad_js === 'function') {
      pyApi.actualizar_estado_gamepad_js(comboPressed);
    }

    if (comboPressed && !gamepadComboActivoJS) {
      gamepadComboActivoJS = true;
      // ⚠️ La activación de voz por L3+R3 la maneja EXCLUSIVAMENTE
      // el subproceso Python (gamepad_service.py vía XInput).
      // El JS solo notifica el estado para que Python sepa cuándo
      // soltó el combo. Si se llamara también desde acá, se dispararían
      // DOS grabaciones simultáneas (duplicando Whisper en RAM/VRAM).
      if (window.iniciarEscuchaVozUI) window.iniciarEscuchaVozUI();
    } else if (!comboPressed && gamepadComboActivoJS) {
      gamepadComboActivoJS = false;
    }

    requestAnimationFrame(loopGamepadHTML5);
  }

  requestAnimationFrame(loopGamepadHTML5);
  actualizarMandosGamepad();

  // ─── INIT ──────────────────────────────────────────────────────────────
  async function inicializarEstado() {
    if (!pyApi) return;
    try {
      const estado = await pyApi.obtener_estado_inicial();
      if (estado) {
        aplicarModoInterfaz(estado.modo_actual || 'chat');
        if (estado.modelo_seleccionado && modelSelect) modelSelect.value = estado.modelo_seleccionado;
        if (estado.workspace_actual && lblWorkspace) {
          const partes = estado.workspace_actual.split(/[\\\/]/);
          lblWorkspace.innerText = partes[partes.length - 1] || 'Proyecto Anclado';
        }
        cargarPerfilesMentor(estado.lista_perfiles || []);
        if (estado.modelo_real) actualizarModeloLabel(estado.modelo_real);
      }
    } catch (e) { console.error('Error init:', e); }
    // Cargar clima al iniciar y luego cada 10 minutos
    actualizarClima();
    setInterval(actualizarClima, 10 * 60 * 1000);
  }

  // ─── WIDGET DE CLIMA ───────────────────────────────────────────────────
  async function actualizarClima() {
    if (!pyApi) return;
    try {
      const clima = await pyApi.obtener_clima();
      if (clima && clima.exito) {
        const wIcon = document.getElementById('weatherIcon');
        const wTemp = document.getElementById('weatherTemp');
        const wDesc = document.getElementById('weatherDesc');
        const wHum  = document.getElementById('weatherHumidity');
        const wWind = document.getElementById('weatherWind');
        if (wIcon) wIcon.textContent = clima.icono;
        if (wTemp) wTemp.textContent = `${clima.temp}°`;
        if (wDesc) wDesc.textContent = clima.descripcion;
        if (wHum)  wHum.textContent  = `💧 ${clima.humedad}%`;
        if (wWind) wWind.textContent = `💨 ${clima.viento} km/h`;
        if (window.emoFace && window.emoFace.setClima) {
          window.emoFace.setClima(clima.condicion);
        }
      }
    } catch (e) { console.warn('[Clima] Error actualizando widget:', e); }
  }

  function actualizarModeloLabel(modeloReal) {
    if (!modelSelect) return;
    const defaultOpt = modelSelect.querySelector('option[value="Por Defecto"]');
    if (!defaultOpt) return;
    if (modelSelect.value === 'Por Defecto' && modeloReal) {
      defaultOpt.innerText = `Default (${modeloReal})`;
    } else {
      defaultOpt.innerText = 'Default';
    }
  }

  function cargarPerfilesMentor(perfiles) {
    if (!mentorProfileSelect) return;
    mentorProfileSelect.innerHTML = '';
    if (!perfiles || !perfiles.length) {
      const opt = document.createElement('option');
      opt.value = 'General'; opt.innerText = 'General / Fullstack';
      mentorProfileSelect.appendChild(opt); return;
    }
    perfiles.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.tecnologia_objetivo || p.nombre || 'General';
      opt.innerText = `${p.tecnologia_objetivo || 'General'} (${p.nivel_actual || 'Junior'})`;
      mentorProfileSelect.appendChild(opt);
    });
  }

  // ─── MODO INTERFAZ ─────────────────────────────────────────────────────
  function aplicarModoInterfaz(modo) {
    modo = (modo || 'chat').toLowerCase();
    if (btnChat) btnChat.classList.remove('active');
    if (btnMentor) btnMentor.classList.remove('active');
    if (btnGamer) btnGamer.classList.remove('active');
    body.className = '';

    if (modo === 'mentor') {
      body.classList.add('theme-mentor');
      if (btnMentor) btnMentor.classList.add('active');
      if (headerTitle) headerTitle.innerText = '🎓 Modo Mentor';
      if (headerSubtitle) headerSubtitle.innerText = 'Orientación técnica, roadmap y preparación de arquitectura';
      if (window.emoFace) { window.emoFace.setAccentColor('#00ff9d'); window.emoFace.setEstado('idle'); }
    } else if (modo === 'gamer') {
      body.classList.add('theme-gamer');
      if (btnGamer) btnGamer.classList.add('active');
      if (headerTitle) headerTitle.innerText = '🎮 Modo Gamer';
      if (headerSubtitle) headerSubtitle.innerText = 'Modo arcade de alto rendimiento sin interrupciones';
      if (lblGamerMode) lblGamerMode.innerText = 'Modo Gaming · ON';
      if (window.emoFace) { window.emoFace.setAccentColor('#ff0055'); window.emoFace.setEstado('idle'); }
    } else {
      body.classList.add('theme-chat');
      if (btnChat) btnChat.classList.add('active');
      if (headerTitle) headerTitle.innerText = '💬 Chat General';
      if (headerSubtitle) headerSubtitle.innerText = 'Asistente IA multimodal con integración MCP activa';
      if (lblGamerMode) lblGamerMode.innerText = 'Modo Gaming';
      if (window.emoFace) { window.emoFace.setAccentColor('#00f3ff'); window.emoFace.setEstado('idle'); }
    }
  }

  // ─── BOTONES MODO ──────────────────────────────────────────────────────
  async function refrescarModeloLabel() {
    if (!pyApi) return;
    try {
      const res = await pyApi.obtener_modelo_real();
      if (res && res.exito) actualizarModeloLabel(res.modelo_real);
    } catch (e) { console.error('Error refreshing model label:', e); }
  }

  if (btnChat) {
    btnChat.addEventListener('click', async () => {
      if (pyApi) await pyApi.cambiar_modo_interfaz('chat');
      aplicarModoInterfaz('chat');
      refrescarModeloLabel();
    });
  }

  if (btnMentor) {
    btnMentor.addEventListener('click', async () => {
      if (pyApi) {
        const res = await pyApi.cambiar_modo_interfaz('mentor');
        if (!res.exito) { agregarMensajeSistema(`❌ ${res.error}`); return; }
      }
      aplicarModoInterfaz('mentor');
      refrescarModeloLabel();
    });
  }

  if (btnGamer) {
    btnGamer.addEventListener('click', async () => {
      const esGamer = body.classList.contains('theme-gamer');
      const nuevoModo = esGamer ? 'chat' : 'gamer';
      if (pyApi) await pyApi.cambiar_modo_interfaz(nuevoModo);
      aplicarModoInterfaz(nuevoModo);
      refrescarModeloLabel();
    });
  }

  // ─── SELECTOR MODELO ───────────────────────────────────────────────────
  if (modelSelect) {
    modelSelect.addEventListener('change', async e => {
      if (pyApi) {
        await pyApi.cambiar_modelo_seleccionado(e.target.value);
        agregarMensajeSistema(`🤖 Modelo cambiado a: <strong>${escapeHtml(e.target.value)}</strong>`);
        // Refrescar el label del modelo real (si seleccionó "Por Defecto" muestra el resuelto)
        refrescarModeloLabel();
      }
    });
  }

  // ─── ACCIONES SIDEBAR ──────────────────────────────────────────────────
  if (btnWorkspace) {
    btnWorkspace.addEventListener('click', async () => {
      if (pyApi) {
        const res = await pyApi.anclar_proyecto();
        if (res.exito && res.workspace) {
          const partes = res.workspace.split(/[\\\/]/);
          if (lblWorkspace) lblWorkspace.innerText = partes[partes.length - 1] || 'Proyecto Anclado';
          agregarMensajeSistema(`📁 Proyecto anclado: <code>${escapeHtml(res.workspace)}</code>`);
        }
      }
    });
  }

  if (btnUpdateMemoria) {
    btnUpdateMemoria.addEventListener('click', async () => {
      if (pyApi) {
        agregarMensajeSistema('🧠 Actualizando memoria de perfil...');
        const res = await pyApi.actualizar_memoria();
        if (res && res.exito === false && res.motivo === 'sin_mensajes') {
          agregarMensajeSistema('🧠 No hay mensajes en la conversación para analizar.');
        }
      }
    });
  }

  if (btnClearContext) {
    btnClearContext.addEventListener('click', async () => {
      if (pyApi) {
        await pyApi.limpiar_contexto();
        if (chatMessages) chatMessages.innerHTML = '';
        agregarMensajeSistema('🧹 Contexto de conversación reiniciado.');
      }
    });
  }

  if (mentorProfileSelect) {
    mentorProfileSelect.addEventListener('change', async e => {
      if (pyApi) {
        const res = await pyApi.seleccionar_perfil_mentor(e.target.value);
        if (res && res.exito) agregarMensajeSistema(`🧠 Perfil Mentor: <strong>${escapeHtml(e.target.value)}</strong>`);
      }
    });
  }

  if (visualModeSelect) {
    visualModeSelect.addEventListener('change', async e => {
      if (pyApi) {
        const res = await pyApi.cambiar_modo_visualizacion(e.target.value);
        if (res && res.exito) agregarMensajeSistema(`📺 Visualización: <strong>${escapeHtml(e.target.options[e.target.selectedIndex].text)}</strong>`);
      }
    });
  }

  // ─── ENVIAR MENSAJE ────────────────────────────────────────────────────
  async function enviarMensaje() {
    if (!promptInput) return;
    let texto = promptInput.value.trim();
    if (!texto && archivosAdjuntos.length === 0) return;

    // Incorporar adjuntos al mensaje
    if (archivosAdjuntos.length > 0) {
      const tags = archivosAdjuntos.map(r => `[adjunto: ${r}]`).join(' ');
      texto = texto ? `${texto} ${tags}` : tags;
      archivosAdjuntos = [];
      renderTagsAdjuntos();
    }

    promptInput.value = '';
    autoResizeTextarea();
    agregarMensajeUsuario(texto.replace(/\[adjunto:[^\]]+\]/gi, '').trim() || '📎 Adjunto enviado');


    if (window.emoFace) window.emoFace.setEstado('thinking');
    mostrarTyping();

    if (pyApi) {
      try {
        await pyApi.enviar_mensaje(texto);
      } catch (err) {
        console.error('Error enviando mensaje:', err);
        ocultarTyping();
        if (window.emoFace) window.emoFace.setEstado('idle');
      }
    }
  }

  if (btnSend) btnSend.addEventListener('click', enviarMensaje);
  if (promptInput) {
    promptInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviarMensaje(); }
    });
    promptInput.addEventListener('input', autoResizeTextarea);
  }

  function autoResizeTextarea() {
    if (!promptInput) return;
    promptInput.style.height = 'auto';
    promptInput.style.height = Math.min(promptInput.scrollHeight, 150) + 'px';
  }

  // ─── MICRÓFONO & LIMPIAR ───────────────────────────────────────────────
  if (btnVoice) {
    btnVoice.addEventListener('click', async () => {
      if (isListening) return;
      iniciarEscuchaVozUI();
      if (pyApi) await pyApi.iniciar_escucha_voz();
    });
  }

  // ─── ATTACH MENU ──────────────────────────────────────────────────────
  function toggleAttachMenu(e) {
    e.stopPropagation();
    if (attachMenu) attachMenu.classList.toggle('open');
  }

  function closeAttachMenu() {
    if (attachMenu) attachMenu.classList.remove('open');
  }

  if (btnAttach) btnAttach.addEventListener('click', toggleAttachMenu);

  document.addEventListener('click', (e) => {
    if (attachMenu && !attachMenu.contains(e.target) && e.target !== btnAttach) {
      closeAttachMenu();
    }
  });

  function agregarTagAdjunto(ruta) {
    archivosAdjuntos.push(ruta);
    renderTagsAdjuntos();
  }

  function renderTagsAdjuntos() {
    let tagsBar = document.getElementById('attachTagsBar');
    const wrapper = document.getElementById('inputContainer')?.parentElement;
    if (!wrapper) return;
    if (!tagsBar) {
      tagsBar = document.createElement('div');
      tagsBar.id = 'attachTagsBar';
      tagsBar.className = 'attach-tags';
      wrapper.insertBefore(tagsBar, document.getElementById('inputContainer'));
    }
    tagsBar.innerHTML = '';
    archivosAdjuntos.forEach((ruta, idx) => {
      const nombre = ruta.split(/[\\/]/).pop();
      const tag = document.createElement('div');
      tag.className = 'attach-tag';
      tag.innerHTML = `<span>📎 ${escapeHtml(nombre)}</span>`;
      const removeBtn = document.createElement('button');
      removeBtn.className = 'attach-tag-remove';
      removeBtn.textContent = '×';
      removeBtn.title = 'Quitar adjunto';
      removeBtn.addEventListener('click', () => {
        archivosAdjuntos.splice(idx, 1);
        renderTagsAdjuntos();
      });
      tag.appendChild(removeBtn);
      tagsBar.appendChild(tag);
    });
    if (archivosAdjuntos.length === 0 && tagsBar) tagsBar.remove();
  }

  async function abrirDialogoAdjunto() {
    closeAttachMenu();
    if (!pyApi) return;
    const res = await pyApi.adjuntar_archivo();
    if (res && res.exito && res.rutas) {
      res.rutas.forEach(r => agregarTagAdjunto(r));
      agregarMensajeSistema(`📎 ${res.rutas.length} archivo(s) adjuntado(s) al contexto.`);
    }
  }

  if (btnAttachFile)  btnAttachFile.addEventListener('click', abrirDialogoAdjunto);
  if (btnAttachImage) btnAttachImage.addEventListener('click', abrirDialogoAdjunto);

  if (btnAttachProject) {
    btnAttachProject.addEventListener('click', async () => {
      closeAttachMenu();
      if (pyApi) {
        const res = await pyApi.anclar_proyecto();
        if (res.exito && res.workspace) {
          const partes = res.workspace.split(/[\\/]/);
          if (lblWorkspace) lblWorkspace.innerText = partes[partes.length - 1] || 'Proyecto Anclado';
          agregarMensajeSistema(`📁 Proyecto anclado: <code>${escapeHtml(res.workspace)}</code>`);
        }
      }
    });
  }

  // ─── BOTÓN RE-ESCANEAR MANDOS ─────────────────────────────────────
  const btnRescanGamepad = document.getElementById('btnRescanGamepad');
  if (btnRescanGamepad) {
    btnRescanGamepad.addEventListener('click', async () => {
      if (!pyApi || typeof pyApi.reintentar_escaneo_gamepad !== 'function') return;
      agregarMensajeSistema('🔄 Re-escanenado mandos...');
      try {
        const res = await pyApi.reintentar_escaneo_gamepad();
        if (res && res.exito) {
          await actualizarMandosGamepad();
          if (res.mandos && res.mandos.length > 0) {
            agregarMensajeSistema(`✅ ${res.mandos.length} mando(s) detectado(s).`);
          } else {
            agregarMensajeSistema('❌ No se detectaron mandos. ¿Están encendidos y conectados?');
          }
        } else {
          agregarMensajeSistema(`❌ Error: ${res?.error || 'Falló el re-escaneo'}`);
        }
      } catch (e) {
        console.error('Error re-escanenado mandos:', e);
        agregarMensajeSistema('❌ Error al re-escanear mandos.');
      }
    });
  }

  if (btnClearChat) {
    btnClearChat.addEventListener('click', () => {
      if (chatMessages) chatMessages.innerHTML = '';
      currentAiBodyDiv = null;
      currentAiRow = null;
      currentAiRawText = '';
      agregarMensajeSistema('🧹 Conversación de pantalla limpiada.');
    });
  }

  // ─── MINI EMO FACE AVATAR GENERATOR ────────────────────────────────────
  function normalizarEmocion(emo) {
    if (!emo) return 'idle';
    const e = emo.toLowerCase().trim();
    if (['happy', 'joy', 'excited', 'smile', 'content'].includes(e)) return 'happy';
    if (['sad', 'cry', 'depressed', 'sorrow'].includes(e)) return 'sad';
    if (['angry', 'mad', 'furious', 'annoyed'].includes(e)) return 'angry';
    if (['thinking', 'thoughtful', 'curious', 'pondering'].includes(e)) return 'thinking';
    if (['error', 'fail', 'failed'].includes(e)) return 'error';
    if (['confirm', 'wink', 'success'].includes(e)) return 'confirm';
    return e;
  }

  function extraerEmocionYTexto(texto) {
    if (!texto || typeof texto !== 'string') return { emocion: null, textoLimpio: texto || '' };
    const match = texto.match(/\[EMOTION:\s*(\w+)\]/i);
    if (match) {
      const emocion = normalizarEmocion(match[1]);
      const textoLimpio = texto.replace(/\[EMOTION:\s*\w+\]/gi, '').trim();
      return { emocion: emocion, textoLimpio: textoLimpio };
    }
    return { emocion: null, textoLimpio: texto };
  }

  function generarMiniEmoAvatarSVG(emocion = 'idle') {
    let color = '#00f0ff'; // Cyan EMO
    const body = document.body;
    if (body.classList.contains('theme-gamer')) color = '#ff0055';
    else if (body.classList.contains('theme-mentor')) color = '#bd00ff';

    const emo = (emocion || 'idle').toLowerCase();

    if (emo === 'happy' || emo === 'joy') {
      color = '#00ffcc';
      return `<svg width="32" height="26" viewBox="0 0 34 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="34" height="28" rx="7" fill="#090a10"/>
        <path d="M 7 17 Q 12 9 16 17" stroke="${color}" stroke-width="2.6" stroke-linecap="round" fill="none"/>
        <path d="M 18 17 Q 22 9 27 17" stroke="${color}" stroke-width="2.6" stroke-linecap="round" fill="none"/>
      </svg>`;
    }

    if (emo === 'sad') {
      color = '#3b82f6';
      return `<svg width="32" height="26" viewBox="0 0 34 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="34" height="28" rx="7" fill="#090a10"/>
        <rect x="7" y="13" width="8" height="7.5" rx="2" fill="${color}"/>
        <rect x="19" y="13" width="8" height="7.5" rx="2" fill="${color}"/>
        <circle cx="26" cy="22" r="1.5" fill="#60a5fa"/>
      </svg>`;
    }

    if (emo === 'angry') {
      color = '#ff5500';
      return `<svg width="32" height="26" viewBox="0 0 34 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="34" height="28" rx="7" fill="#090a10"/>
        <path d="M 6 11 L 15 15" stroke="${color}" stroke-width="2.2" stroke-linecap="round"/>
        <path d="M 28 11 L 19 15" stroke="${color}" stroke-width="2.2" stroke-linecap="round"/>
        <rect x="7" y="15" width="7.5" height="7.5" rx="2" fill="${color}"/>
        <rect x="19.5" y="15" width="7.5" height="7.5" rx="2" fill="${color}"/>
      </svg>`;
    }

    if (emo === 'thinking') {
      color = '#bd00ff';
      return `<svg width="32" height="26" viewBox="0 0 34 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="34" height="28" rx="7" fill="#090a10"/>
        <rect x="6" y="9" width="7.5" height="8" rx="2" fill="${color}"/>
        <rect x="18" y="9" width="7.5" height="8" rx="2" fill="${color}"/>
      </svg>`;
    }

    if (emo === 'confirm' || emo === 'wink') {
      color = '#39ff14';
      return `<svg width="32" height="26" viewBox="0 0 34 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="34" height="28" rx="7" fill="#090a10"/>
        <path d="M 7 17 Q 12 9 16 17" stroke="${color}" stroke-width="2.5" stroke-linecap="round" fill="none"/>
        <line x1="19" y1="15" x2="27" y2="15" stroke="${color}" stroke-width="2.5" stroke-linecap="round"/>
      </svg>`;
    }

    if (emo === 'error') {
      color = '#ff0033';
      return `<svg width="32" height="26" viewBox="0 0 34 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="34" height="28" rx="7" fill="#090a10"/>
        <path d="M 8 11 L 15 19 M 15 11 L 8 19" stroke="${color}" stroke-width="2.2" stroke-linecap="round"/>
        <path d="M 19 11 L 26 19 M 26 11 L 19 19" stroke="${color}" stroke-width="2.2" stroke-linecap="round"/>
      </svg>`;
    }

    // Default / Talking / Idle EMO face
    return `<svg width="32" height="26" viewBox="0 0 34 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="34" height="28" rx="7" fill="#090a10"/>
      <rect x="7" y="9.5" width="7.5" height="10.5" rx="2.5" fill="${color}"/>
      <circle cx="9" cy="11.5" r="1" fill="#ffffff"/>
      <rect x="19.5" y="9.5" width="7.5" height="10.5" rx="2.5" fill="${color}"/>
      <circle cx="21.5" cy="11.5" r="1" fill="#ffffff"/>
    </svg>`;
  }

  // ─── TYPING INDICATOR ──────────────────────────────────────────────────
  function mostrarTyping() {
    if (typingRowEl || !chatMessages) return;
    typingRowEl = document.createElement('div');
    typingRowEl.className = 'typing-row';
    typingRowEl.innerHTML = `
      <div class="msg-avatar">${generarMiniEmoAvatarSVG('thinking')}</div>
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>`;
    chatMessages.appendChild(typingRowEl);
    scrollBottom();
  }

  function ocultarTyping() {
    if (typingRowEl) { typingRowEl.remove(); typingRowEl = null; }
  }

  function scrollBottom() {
    if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function nowTime() {
    return new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' });
  }

  // ─── RENDER MARKDOWN CON DOM POST-PROCESSING ──────────────────────────
  function renderMarkdown(mdText) {
    if (!mdText) return '';
    let rawHtml = '';

    if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
      try {
        rawHtml = marked.parse(mdText);
      } catch (e) {
        console.warn('Error en marked.parse:', e);
        rawHtml = escapeHtml(mdText).replace(/\n/g, '<br>');
      }
    } else {
      rawHtml = escapeHtml(mdText)
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
    }

    const container = document.createElement('div');
    container.innerHTML = rawHtml;

    // Procesar bloques de código para agregar header con botón de copiado de forma limpia
    container.querySelectorAll('pre code').forEach(codeEl => {
      const preEl = codeEl.parentElement;
      if (preEl && preEl.tagName.toLowerCase() === 'pre') {
        const langClass = Array.from(codeEl.classList).find(c => c.startsWith('language-')) || '';
        const lang = langClass.replace('language-', '') || 'código';

        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';

        const header = document.createElement('div');
        header.className = 'code-header';

        const langSpan = document.createElement('span');
        langSpan.className = 'code-lang';
        langSpan.textContent = lang;

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.innerHTML = '<span>⎘</span><span>Copiar</span>';
        copyBtn.addEventListener('click', () => {
          const codeText = codeEl.innerText || codeEl.textContent;
          navigator.clipboard.writeText(codeText).then(() => {
            copyBtn.classList.add('copied');
            copyBtn.innerHTML = '<span>✓</span><span>Copiado</span>';
            setTimeout(() => {
              copyBtn.classList.remove('copied');
              copyBtn.innerHTML = '<span>⎘</span><span>Copiar</span>';
            }, 2000);
          });
        });

        header.appendChild(langSpan);
        header.appendChild(copyBtn);

        preEl.parentNode.insertBefore(wrapper, preEl);
        wrapper.appendChild(header);
        wrapper.appendChild(preEl);
      }
    });

    return container.innerHTML;
  }

  // ─── AGREGAR MENSAJES ──────────────────────────────────────────────────
  function agregarMensajeUsuario(texto) {
    if (!chatMessages) return;

    // Reiniciar el estado de streaming para forzar una nueva burbuja de IA
    currentAiBodyDiv = null;
    currentAiRow = null;
    currentAiRawText = '';

    const row = document.createElement('div');
    row.className = 'msg-row user-row';

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.textContent = '👤';

    const content = document.createElement('div');
    content.className = 'msg-content';

    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    meta.innerHTML = `<span class="msg-sender">Tú</span><span class="msg-time">${nowTime()}</span>`;

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';

    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'msg-body';
    bodyDiv.textContent = texto; // seguro contra XSS

    bubble.appendChild(bodyDiv);

    const actions = document.createElement('div');
    actions.className = 'msg-actions';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'msg-action-btn';
    copyBtn.textContent = '⎘ Copiar';
    copyBtn.addEventListener('click', () => copyTextBtn(copyBtn, texto));

    actions.appendChild(copyBtn);

    content.appendChild(meta);
    content.appendChild(bubble);
    content.appendChild(actions);

    row.appendChild(avatar);
    row.appendChild(content);

    chatMessages.appendChild(row);
    scrollBottom();
  }

  function agregarMensajeArgus(textoMarkdown, remitente, retornarBody = false) {
    if (!chatMessages) return;
    ocultarTyping();

    const { emocion, textoLimpio } = extraerEmocionYTexto(textoMarkdown);
    if (emocion && window.emoFace) {
      window.emoFace.setEstado(emocion);
    }

    const row = document.createElement('div');
    row.className = 'msg-row ai-row';

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerHTML = generarMiniEmoAvatarSVG(emocion || 'talking');

    const content = document.createElement('div');
    content.className = 'msg-content';

    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    meta.innerHTML = `<span class="msg-sender">${escapeHtml(remitente || 'Argus Copilot')}</span><span class="msg-time">${nowTime()}</span>`;

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';

    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'msg-body';
    bodyDiv.innerHTML = renderMarkdown(textoLimpio);

    bubble.appendChild(bodyDiv);

    const actions = document.createElement('div');
    actions.className = 'msg-actions';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'msg-action-btn';
    copyBtn.textContent = '⎘ Copiar';
    copyBtn.addEventListener('click', () => {
      const textToCopy = row.dataset.rawText || textoLimpio;
      copyTextBtn(copyBtn, textToCopy);
    });

    actions.appendChild(copyBtn);

    content.appendChild(meta);
    content.appendChild(bubble);
    content.appendChild(actions);

    row.appendChild(avatar);
    row.appendChild(content);

    row.dataset.rawText = textoLimpio;
    row.dataset.emocion = emocion || 'idle';

    chatMessages.appendChild(row);

    // Highlight.js sintaxis
    if (typeof hljs !== 'undefined') {
      row.querySelectorAll('pre code').forEach(b => {
        try { hljs.highlightElement(b); } catch (e) {}
      });
    }

    scrollBottom();

    if (retornarBody) {
      return { row: row, bodyDiv: bodyDiv, avatarDiv: avatar };
    }
  }

  function agregarMensajeSistema(htmlTexto) {
    if (!chatMessages) return;
    const row = document.createElement('div');
    row.className = 'msg-row system-row';

    const content = document.createElement('div');
    content.className = 'msg-content';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';

    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'msg-body';
    bodyDiv.innerHTML = htmlTexto;

    bubble.appendChild(bodyDiv);
    content.appendChild(bubble);
    row.appendChild(content);

    chatMessages.appendChild(row);
    scrollBottom();
  }

  function copyTextBtn(btn, text) {
    navigator.clipboard.writeText(text).then(() => {
      const orig = btn.textContent;
      btn.textContent = '✓ Copiado';
      btn.style.color = '#00ff9d';
      btn.style.borderColor = '#00ff9d';
      setTimeout(() => {
        btn.textContent = orig;
        btn.style.color = '';
        btn.style.borderColor = '';
      }, 2000);
    }).catch(err => console.error('Copy error:', err));
  }

  function escapeHtml(str) {
    if (typeof str !== 'string') str = String(str || '');
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ─── EXPOSED TO PYTHON (evaluate_js) ──────────────────────────────────
  let currentAiBodyDiv = null;
  let currentAiRow = null;
  let currentAiAvatarDiv = null;
  let currentAiRawText = '';

  let emoFaceTimer = null;
  function resetEmoFaceTimer(delayMs = 6000) {
    if (emoFaceTimer) clearTimeout(emoFaceTimer);
    emoFaceTimer = setTimeout(() => {
      if (window.emoFace) window.emoFace.setEstado('idle');
    }, delayMs);
  }

  window.agregarRespuestaArgus = function(textoMarkdown, remitente, esContinuacion) {
    if (remitente === "⚙️ Sistema") {
      agregarMensajeSistema(textoMarkdown);
      currentAiBodyDiv = null; // rompe la continuación
      return;
    }

    if (esContinuacion && currentAiBodyDiv) {
      currentAiRawText += textoMarkdown;
      const { emocion, textoLimpio } = extraerEmocionYTexto(currentAiRawText);
      currentAiBodyDiv.innerHTML = renderMarkdown(textoLimpio);

      if (currentAiRow) {
        currentAiRow.dataset.rawText = textoLimpio;
        if (emocion && currentAiAvatarDiv) {
          currentAiAvatarDiv.innerHTML = generarMiniEmoAvatarSVG(emocion);
          if (window.emoFace) window.emoFace.setEstado(emocion);
        } else if (!emocion && window.emoFace) {
          window.emoFace.setEstado('talking');
        }

        if (typeof hljs !== 'undefined') {
          currentAiRow.querySelectorAll('pre code:not(.hljs)').forEach(b => {
            try { hljs.highlightElement(b); } catch (e) {}
          });
        }
      }
      scrollBottom();
      resetEmoFaceTimer(6000);
    } else {
      currentAiRawText = textoMarkdown || '';
      const result = agregarMensajeArgus(currentAiRawText, remitente || 'Argus Copilot', true);
      if (result) {
        currentAiBodyDiv = result.bodyDiv;
        currentAiRow = result.row;
        currentAiAvatarDiv = result.avatarDiv;
      }
      resetEmoFaceTimer(6000);
    }
  };

  window.agregarMensajeUsuario = function(texto) { agregarMensajeUsuario(texto); };
  window.agregarMensajeSistema = function(html) { agregarMensajeSistema(html); };

  window.iniciarEscuchaVozUI = function() {
    isListening = true;
    if (btnVoice) btnVoice.classList.add('listening');
    if (window.emoFace) window.emoFace.setEstado('listening');
  };

  window.detenerEscuchaVozUI = function() {
    isListening = false;
    if (btnVoice) btnVoice.classList.remove('listening');
    ocultarTyping();
    if (window.emoFace) window.emoFace.setEstado('idle');
  };

  window.actualizarEstadoGamepad = function(conectado) {
    if (lblGamepadStatus)
      lblGamepadStatus.innerText = conectado ? '🎮 Mando: conectado' : '🎮 Mando: inactivo';
  };

  window.mostrarTypingIndicator = function() { mostrarTyping(); };
  window.ocultarTypingIndicator = function() { ocultarTyping(); };

  // ─── EMO SPEECH CLOUD BUBBLE & MODAL RECORDATORIOS LOGIC ───────────────
  const emoCloudBubble = document.getElementById('emoCloudBubble');
  const cloudBadge     = document.getElementById('cloudBadge');
  const cloudTime      = document.getElementById('cloudTime');
  const cloudMessage   = document.getElementById('cloudMessage');
  const btnEmoCloudOk  = document.getElementById('btnEmoCloudOk');

  const btnReminders     = document.getElementById('btnReminders');
  const modalRecordatorios = document.getElementById('modalRecordatorios');
  const btnCloseModalRec = document.getElementById('btnCloseModalRec');
  const tabRecActivos    = document.getElementById('tabRecActivos');
  const tabRecNuevo      = document.getElementById('tabRecNuevo');
  const contentRecActivos = document.getElementById('contentRecActivos');
  const contentRecNuevo   = document.getElementById('contentRecNuevo');
  const recListContainer = document.getElementById('recListContainer');
  const formNuevoRec     = document.getElementById('formNuevoRec');

  // Función invocada por Python cuando expira/dispara un recordatorio
  window.mostrarNubeRecordatorioEmo = function(data) {
    if (!data) return;
    const msg = data.mensaje || 'Sin título';
    const hora = data.expiracion_iso ? data.expiracion_iso.split(' ')[1] || '' : '';
    const esPrevio = data.es_aviso_previo || false;

    if (cloudBadge) cloudBadge.innerText = esPrevio ? '📌 AVISO PARA MAÑANA' : '⏰ RECORDATORIO';
    if (cloudTime) cloudTime.innerText = hora;
    if (cloudMessage) cloudMessage.innerText = msg;

    if (emoCloudBubble) {
      emoCloudBubble.classList.remove('hidden');
    }

    if (window.emoFace) {
      window.emoFace.setEstado('confirm', esPrevio ? 'MAÑANA' : 'AVISO');
    }
  };

  if (btnEmoCloudOk) {
    btnEmoCloudOk.addEventListener('click', () => {
      if (emoCloudBubble) emoCloudBubble.classList.add('hidden');
      if (window.emoFace) window.emoFace.setEstado('idle');
    });
  }

  // Modal Recordatorios Handlers
  if (btnReminders) {
    btnReminders.addEventListener('click', () => {
      if (modalRecordatorios) modalRecordatorios.classList.remove('hidden');
      cargarListaRecordatorios();
    });
  }

  if (btnCloseModalRec) {
    btnCloseModalRec.addEventListener('click', () => {
      if (modalRecordatorios) modalRecordatorios.classList.add('hidden');
    });
  }

  if (modalRecordatorios) {
    modalRecordatorios.addEventListener('click', (e) => {
      if (e.target === modalRecordatorios) {
        modalRecordatorios.classList.add('hidden');
      }
    });
  }

  if (tabRecActivos && tabRecNuevo) {
    tabRecActivos.addEventListener('click', () => {
      tabRecActivos.classList.add('active');
      tabRecNuevo.classList.remove('active');
      contentRecActivos.classList.remove('hidden');
      contentRecNuevo.classList.add('hidden');
      cargarListaRecordatorios();
    });

    tabRecNuevo.addEventListener('click', () => {
      tabRecNuevo.classList.add('active');
      tabRecActivos.classList.remove('active');
      contentRecNuevo.classList.remove('hidden');
      contentRecActivos.classList.add('hidden');
    });
  }

  async function cargarListaRecordatorios() {
    if (!pyApi || typeof pyApi.obtener_recordatorios !== 'function') return;
    try {
      if (recListContainer) recListContainer.innerHTML = '<div class="rec-empty-state">Cargando...</div>';
      const res = await pyApi.obtener_recordatorios();
      if (res && res.exito) {
        renderizarListaRecordatorios(res.recordatorios || []);
      } else {
        if (recListContainer) recListContainer.innerHTML = `<div class="rec-empty-state">Error: ${res.error || 'No disponible'}</div>`;
      }
    } catch (e) {
      console.error('Error cargando recordatorios:', e);
      if (recListContainer) recListContainer.innerHTML = `<div class="rec-empty-state">Error al conectar con el motor.</div>`;
    }
  }

  function renderizarListaRecordatorios(lista) {
    if (!recListContainer) return;
    if (lista.length === 0) {
      recListContainer.innerHTML = '<div class="rec-empty-state">No tienes recordatorios pendientes. 🎉</div>';
      return;
    }

    recListContainer.innerHTML = '';
    lista.forEach(r => {
      const item = document.createElement('div');
      item.className = 'rec-item';

      const tagTipo = r.tipo === 'recurrente' ? '🔄 Recurrente' : (r.sin_hora_especifica ? '☀️ Día Completo' : '⏱️ Puntual');

      item.innerHTML = `
        <div class="rec-item-info">
          <div class="rec-item-title">${escapeHtml(r.mensaje)}</div>
          <div class="rec-item-meta">
            <span class="rec-badge">${tagTipo}</span>
            <span>📅 ${escapeHtml(r.expiracion_iso)}</span>
          </div>
        </div>
        <button class="rec-btn-del" data-id="${r.id}" title="Eliminar recordatorio">🗑️ Borrar</button>
      `;

      const btnDel = item.querySelector('.rec-btn-del');
      if (btnDel) {
        btnDel.addEventListener('click', async () => {
          const id = btnDel.dataset.id;
          if (pyApi && typeof pyApi.cancelar_recordatorio_manual === 'function') {
            await pyApi.cancelar_recordatorio_manual(id);
            cargarListaRecordatorios();
          }
        });
      }

      recListContainer.appendChild(item);
    });
  }

  if (formNuevoRec) {
    formNuevoRec.addEventListener('submit', async (e) => {
      e.preventDefault();
      const msgInput = document.getElementById('recMensaje');
      const tiempoInput = document.getElementById('recTiempo');
      const opcSelect = document.getElementById('recOpciones');

      if (!msgInput || !tiempoInput) return;

      const mensaje = msgInput.value.trim();
      const tiempo = tiempoInput.value.trim();
      const opciones = opcSelect ? opcSelect.value : '';

      if (!mensaje || !tiempo) return;

      if (pyApi && typeof pyApi.crear_recordatorio_manual === 'function') {
        const res = await pyApi.crear_recordatorio_manual(mensaje, tiempo, opciones);
        if (res && res.exito) {
          msgInput.value = '';
          tiempoInput.value = '';
          if (opcSelect) opcSelect.value = '';
          if (tabRecActivos) tabRecActivos.click();
        } else {
          alert('Error creando recordatorio: ' + (res.error || 'desconocido'));
        }
      }
    });
  }

});

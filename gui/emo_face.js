/**
 * EMO Canvas Face — Web HUD (60 FPS)
 * Replica 1:1 del EmoBezelFace de main_gui.py + mejoras:
 *  - Sistema de deriva flotante: EMO se mueve organicamente dentro del recuadro
 *  - Labels de estado en espanol
 *  - Estados climaticos: hot, cold, rainy, stormy, windy, cloudy
 *  - Sistema de particulas: lluvia, escarcha, viento, calor, rayos
 *  - Metodo setClima() — solo actua en idle para no interrumpir respuestas de IA
 */

class EmoCanvasFace {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.CANVAS_W = 230;
    this.CANVAS_H = 150;
    this.ancho    = 180;
    this.alto     = 120;

    this.izq_cx = 73;  this.der_cx = 107;
    this.izq_cy = 52;  this.der_cy = 52;
    this.boca_cx = 90; this.boca_cy = 82;
    this.base_rx = 13.5; this.base_ry = 15.0;
    this.corner_radius = 6;

    this.estado  = 'idle';
    this.tiempo  = 0.0;
    this.tiempo_lagrima = 0.0;
    this.msg_confirmacion = 'HECHO';

    this.cur_zoom_x_izq = 1.0; this.tgt_zoom_x_izq = 1.0;
    this.cur_zoom_y_izq = 1.0; this.tgt_zoom_y_izq = 1.0;
    this.cur_zoom_x_der = 1.0; this.tgt_zoom_x_der = 1.0;
    this.cur_zoom_y_der = 1.0; this.tgt_zoom_y_der = 1.0;

    this.cur_look_x = 0.0; this.tgt_look_x = 0.0;
    this.cur_look_y = 0.0; this.tgt_look_y = 0.0;

    this.colores = {
      idle:'#00f0ff', listening:'#00f0ff', thinking:'#bd00ff',
      talking:'#39ff14', happy:'#00ffcc', angry:'#ff5500',
      sad:'#3b82f6', error:'#ff0033', confirm:'#39ff14',
      hot:'#ff6600', cold:'#88ccff', rainy:'#4488cc',
      stormy:'#cc44ff', windy:'#aaddff', cloudy:'#778899',
    };

    this._idle_action = 'none';

    // Deriva flotante
    this._drift_px = Math.random() * Math.PI * 2;
    this._drift_py = Math.random() * Math.PI * 2;
    this.drift_x   = 24;
    this.drift_y   = 14;

    // Sistema climatico
    this.clima = null;
    this._particulas = [];
    this._calor_shimmer = [];
    this._lightning_timer = 0;
    this._lightning_flash = 0;

    // Labels espanol
    this._labels = {
      idle:'REPOSO', listening:'ESCUCHANDO', thinking:'PENSANDO',
      talking:'HABLANDO', happy:'FELIZ', angry:'ENOJADO',
      sad:'TRISTE', error:'ERROR', confirm:'CONFIRMADO',
      hot:'CALOR', cold:'FRIO', rainy:'LLUVIA',
      stormy:'TORMENTA', windy:'VIENTO', cloudy:'NUBLADO',
    };

    this._startLoops();
  }

  setAccentColor(color) {
    this.colores.idle      = color;
    this.colores.listening = color;
  }

  setEstado(nuevo_estado, msg = '') {
    if (this.estado === nuevo_estado && !msg) return;
    this.estado = nuevo_estado;
    this.tiempo = 0.0;
    this.tiempo_lagrima = 0.0;
    this.tgt_look_x = 0.0;
    this.tgt_look_y = 0.0;
    if (msg) this.msg_confirmacion = msg;

    if (nuevo_estado === 'idle') {
      this.tgt_zoom_x_izq = 1.0; this.tgt_zoom_y_izq = 1.0;
      this.tgt_zoom_x_der = 1.0; this.tgt_zoom_y_der = 1.0;
    } else if (nuevo_estado === 'listening') {
      this.tgt_zoom_x_izq = 1.12; this.tgt_zoom_y_izq = 1.12;
      this.tgt_zoom_x_der = 1.12; this.tgt_zoom_y_der = 1.12;
    } else if (nuevo_estado === 'thinking') {
      this.tgt_zoom_x_izq = 0.95; this.tgt_zoom_y_izq = 0.85;
      this.tgt_zoom_x_der = 0.95; this.tgt_zoom_y_der = 0.85;
      this.tgt_look_x = -4.0; this.tgt_look_y = -3.0;
    } else if (nuevo_estado === 'talking') {
      this.tgt_zoom_x_izq = 1.0; this.tgt_zoom_y_izq = 1.0;
      this.tgt_zoom_x_der = 1.0; this.tgt_zoom_y_der = 1.0;
    } else if (nuevo_estado === 'happy') {
      this.tgt_zoom_x_izq = 1.0; this.tgt_zoom_y_izq = 1.0;
      this.tgt_zoom_x_der = 1.0; this.tgt_zoom_y_der = 1.0;
    } else if (nuevo_estado === 'angry') {
      this.tgt_zoom_x_izq = 1.0; this.tgt_zoom_y_izq = 0.8;
      this.tgt_zoom_x_der = 1.0; this.tgt_zoom_y_der = 0.8;
    } else if (nuevo_estado === 'sad') {
      this.tgt_zoom_x_izq = 0.95; this.tgt_zoom_y_izq = 0.85;
      this.tgt_zoom_x_der = 0.95; this.tgt_zoom_y_der = 0.85;
      this.tgt_look_y = 2.0;
    } else if (nuevo_estado === 'error') {
      this.tgt_zoom_x_izq = 0.85; this.tgt_zoom_y_izq = 0.85;
      this.tgt_zoom_x_der = 0.85; this.tgt_zoom_y_der = 0.85;
    } else if (nuevo_estado === 'confirm') {
      this.tgt_zoom_x_izq = 1.1; this.tgt_zoom_y_izq = 1.1;
      this.tgt_zoom_x_der = 1.1; this.tgt_zoom_y_der = 1.1;
    } else if (nuevo_estado === 'hot') {
      this.tgt_zoom_x_izq = 1.1; this.tgt_zoom_y_izq = 0.60;
      this.tgt_zoom_x_der = 1.1; this.tgt_zoom_y_der = 0.60;
      this.tgt_look_y = 2.5;
    } else if (nuevo_estado === 'cold') {
      this.tgt_zoom_x_izq = 0.88; this.tgt_zoom_y_izq = 0.72;
      this.tgt_zoom_x_der = 0.88; this.tgt_zoom_y_der = 0.72;
    } else if (nuevo_estado === 'rainy') {
      this.tgt_zoom_x_izq = 0.95; this.tgt_zoom_y_izq = 0.88;
      this.tgt_zoom_x_der = 0.95; this.tgt_zoom_y_der = 0.88;
      this.tgt_look_y = 1.5;
    } else if (nuevo_estado === 'stormy') {
      this.tgt_zoom_x_izq = 1.06; this.tgt_zoom_y_izq = 1.06;
      this.tgt_zoom_x_der = 1.06; this.tgt_zoom_y_der = 1.06;
    } else if (nuevo_estado === 'windy') {
      this.tgt_zoom_x_izq = 1.0; this.tgt_zoom_y_izq = 0.88;
      this.tgt_zoom_x_der = 1.0; this.tgt_zoom_y_der = 0.88;
      this.tgt_look_x = -7.0;
    } else if (nuevo_estado === 'cloudy') {
      this.tgt_zoom_x_izq = 1.0; this.tgt_zoom_y_izq = 0.95;
      this.tgt_zoom_x_der = 1.0; this.tgt_zoom_y_der = 0.95;
    }

    const tagText = document.getElementById('emoStatusText');
    if (tagText) tagText.innerText = this._labels[nuevo_estado] || nuevo_estado.toUpperCase();
  }

  setClima(condicion) {
    this.clima = condicion;
    this._init_particulas(condicion);
    const climaStates = new Set(['hot','cold','rainy','stormy','windy','cloudy']);
    if (this.estado === 'idle' || climaStates.has(this.estado)) {
      const mapa = { rainy:'rainy', stormy:'stormy', cold:'cold', hot:'hot', windy:'windy', cloudy:'cloudy', clear:'idle' };
      const nuevo = mapa[condicion] || 'idle';
      this.setEstado(nuevo);
    }
  }

  _init_particulas(condicion) {
    this._particulas = [];
    this._calor_shimmer = [];
    this._lightning_timer = 0;
    this._lightning_flash = 0;

    if (condicion === 'rainy' || condicion === 'stormy') {
      const angulo = condicion === 'stormy' ? 0.3 : 0.08;
      for (let i = 0; i < 24; i++) {
        this._particulas.push({
          tipo:'rain', x:Math.random()*this.CANVAS_W, y:Math.random()*this.CANVAS_H,
          speed:3.5+Math.random()*3.5, len:7+Math.random()*9,
          opacity:0.3+Math.random()*0.4, angulo,
        });
      }
      if (condicion === 'stormy') this._lightning_timer = 80 + Math.floor(Math.random()*120);
    }

    if (condicion === 'windy') {
      for (let i = 0; i < 11; i++) {
        this._particulas.push({
          tipo:'wind', x:Math.random()*this.CANVAS_W, y:12+Math.random()*126,
          speed:5+Math.random()*6, len:18+Math.random()*32,
          opacity:0.18+Math.random()*0.25, width:0.8+Math.random()*0.7,
        });
      }
    }

    if (condicion === 'cold') {
      for (let i = 0; i < 16; i++) {
        let x, y;
        const s = i%4;
        if      (s===0){ x=Math.random()*45;              y=Math.random()*this.CANVAS_H; }
        else if (s===1){ x=this.CANVAS_W-Math.random()*45; y=Math.random()*this.CANVAS_H; }
        else if (s===2){ x=Math.random()*this.CANVAS_W;   y=Math.random()*38; }
        else            { x=Math.random()*this.CANVAS_W;   y=this.CANVAS_H-Math.random()*38; }
        this._particulas.push({ tipo:'frost', x, y, size:2.5+Math.random()*3.5, opacity:0.3+Math.random()*0.45, rotation:Math.random()*Math.PI*2 });
      }
    }

    if (condicion === 'hot') {
      for (let i = 0; i < 5; i++) {
        this._calor_shimmer.push({ x:25+Math.random()*180, phase:Math.random()*Math.PI*2, speed:0.7+Math.random()*0.9, width:28+Math.random()*45 });
      }
    }
  }

  _dibujar_particulas() {
    if (!this.clima || this.clima === 'clear') return;
    const ctx = this.ctx;

    for (const p of this._particulas) {
      if (p.tipo === 'rain') {
        p.x += Math.sin(p.angulo)*p.speed*0.6;
        p.y += p.speed;
        if (p.y > this.CANVAS_H+12) { p.y=-12; p.x=Math.random()*this.CANVAS_W; }
        ctx.save();
        ctx.globalAlpha = p.opacity;
        ctx.strokeStyle = '#88aadd';
        ctx.lineWidth   = 1;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x + Math.sin(p.angulo)*p.len*0.5, p.y - p.len);
        ctx.stroke();
        ctx.restore();

      } else if (p.tipo === 'wind') {
        p.x += p.speed;
        if (p.x > this.CANVAS_W+p.len) { p.x=-p.len; p.y=12+Math.random()*126; }
        ctx.save();
        ctx.globalAlpha = p.opacity;
        ctx.strokeStyle = '#aaccee';
        ctx.lineWidth   = p.width;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x+p.len, p.y);
        ctx.stroke();
        ctx.restore();

      } else if (p.tipo === 'frost') {
        ctx.save();
        ctx.globalAlpha = p.opacity*(0.7+0.3*Math.sin(this.tiempo*1.5+p.rotation));
        ctx.strokeStyle = '#aaddff';
        ctx.lineWidth   = 0.8;
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rotation + this.tiempo*0.018);
        for (let a=0; a<6; a++) {
          ctx.beginPath();
          ctx.moveTo(0,0); ctx.lineTo(0,p.size);
          ctx.moveTo(0,p.size*0.5); ctx.lineTo(p.size*0.33,p.size*0.67);
          ctx.moveTo(0,p.size*0.5); ctx.lineTo(-p.size*0.33,p.size*0.67);
          ctx.stroke();
          ctx.rotate(Math.PI/3);
        }
        ctx.restore();
      }
    }

    for (const s of this._calor_shimmer) {
      s.phase += s.speed*0.04;
      const by = 55+22*Math.sin(s.phase);
      ctx.save();
      ctx.globalAlpha = 0.055+0.03*Math.sin(s.phase*1.4);
      ctx.strokeStyle = '#ff8800';
      ctx.lineWidth   = 1.5;
      ctx.beginPath();
      ctx.moveTo(s.x, by);
      for (let dx=1; dx<s.width; dx+=4) {
        ctx.lineTo(s.x+dx, by+3.5*Math.sin((dx/s.width+s.phase)*Math.PI*3));
      }
      ctx.stroke();
      ctx.restore();
    }

    if (this.clima === 'stormy') {
      if (this._lightning_flash > 0) {
        ctx.save();
        ctx.globalAlpha = this._lightning_flash*0.14;
        ctx.fillStyle   = '#ffffff';
        ctx.fillRect(0,0,this.CANVAS_W,this.CANVAS_H);
        ctx.restore();
        this._lightning_flash -= 0.055;
      }
      this._lightning_timer--;
      if (this._lightning_timer <= 0) {
        this._lightning_flash = 0.9+Math.random()*0.5;
        this._lightning_timer = 90+Math.floor(Math.random()*160);
        const lx = 30+Math.random()*170;
        ctx.save();
        ctx.strokeStyle = '#ccaaff';
        ctx.lineWidth   = 1.5;
        ctx.globalAlpha = 0.65;
        ctx.beginPath();
        ctx.moveTo(lx, 0);
        let cy_l=0, cx_l=lx;
        while (cy_l < this.CANVAS_H) {
          cx_l += (Math.random()-0.5)*28;
          cy_l += 12+Math.random()*18;
          ctx.lineTo(cx_l, Math.min(cy_l, this.CANVAS_H));
        }
        ctx.stroke();
        ctx.restore();
      }
    }
  }

  dibujar_contorno_gris_emo() {
    const ctx = this.ctx;
    const x1=30, y1=12, x2=150, y2=108, r=18;
    const drawPath = (radius) => {
      ctx.beginPath();
      ctx.moveTo(x1+radius, y1);
      ctx.arcTo(x2,y1, x2,y2, radius);
      ctx.arcTo(x2,y2, x1,y2, radius);
      ctx.arcTo(x1,y2, x1,y1, radius);
      ctx.arcTo(x1,y1, x2,y1, radius);
      ctx.closePath();
    };
    ctx.save(); ctx.strokeStyle='#5a5a63'; ctx.lineWidth=4; drawPath(r); ctx.stroke(); ctx.restore();
    ctx.save(); ctx.strokeStyle='#9ca3af'; ctx.lineWidth=1.5; drawPath(r); ctx.stroke(); ctx.restore();
  }

  dibujar_ojo_intellar(cx, cy, rx, ry, color, izquierdo=true) {
    const ctx = this.ctx;
    if (rx<=0 || ry<=0) return;

    const isWink = (this.estado==='confirm') || (this.estado==='idle' && this._idle_action==='wink');
    if ((isWink && izquierdo) || this.estado==='happy') {
      ctx.save();
      ctx.strokeStyle=color; ctx.lineWidth=5.0;
      ctx.shadowColor=color; ctx.shadowBlur=10;
      ctx.beginPath(); ctx.arc(cx, cy+6, rx, Math.PI*0.17, Math.PI*0.83); ctx.stroke();
      ctx.shadowBlur=0; ctx.strokeStyle='#ffffff'; ctx.lineWidth=1.5;
      ctx.beginPath(); ctx.arc(cx, cy+6, rx, Math.PI*0.19, Math.PI*0.81); ctx.stroke();
      ctx.restore();
      return;
    }

    const x1=cx-rx, y1=cy-ry, w=rx*2, h=ry*2, rr=Math.min(this.corner_radius,rx,ry);
    ctx.save();
    ctx.shadowColor=color; ctx.shadowBlur=14; ctx.fillStyle=color;
    ctx.beginPath();
    ctx.moveTo(x1+rr, y1);
    ctx.arcTo(x1+w,y1, x1+w,y1+h, rr);
    ctx.arcTo(x1+w,y1+h, x1,y1+h, rr);
    ctx.arcTo(x1,y1+h, x1,y1, rr);
    ctx.arcTo(x1,y1, x1+w,y1, rr);
    ctx.closePath(); ctx.fill(); ctx.restore();

    if (ry>7) {
      ctx.save(); ctx.fillStyle='rgba(255,255,255,0.45)';
      ctx.beginPath();
      ctx.ellipse(cx-rx*0.35, cy-ry*0.4, rx*0.3, ry*0.22, -0.4, 0, Math.PI*2);
      ctx.fill(); ctx.restore();
    }

    if (this.estado==='angry') {
      const dc=izquierdo?1:-1;
      ctx.save(); ctx.fillStyle='#000000'; ctx.beginPath();
      ctx.moveTo(cx-rx-5, cy-ry-5+(6*dc)); ctx.lineTo(cx+rx+5, cy-ry-5-(6*dc));
      ctx.lineTo(cx+rx+5, cy-ry+2);        ctx.lineTo(cx-rx-5, cy-ry+2);
      ctx.closePath(); ctx.fill(); ctx.restore();
    } else if (this.estado==='sad'||this.estado==='error'||this.estado==='rainy') {
      const dc=izquierdo?1:-1;
      ctx.save(); ctx.fillStyle='#000000'; ctx.beginPath();
      ctx.moveTo(cx-rx-5, cy-ry-5-(5*dc)); ctx.lineTo(cx+rx+5, cy-ry-5+(5*dc));
      ctx.lineTo(cx+rx+5, cy-ry+4);        ctx.lineTo(cx-rx-5, cy-ry+4);
      ctx.closePath(); ctx.fill(); ctx.restore();
      if (this.estado==='sad') {
        const tx=izquierdo?cx-rx*0.5:cx+rx*0.5;
        const ty=cy+ry*0.8+this.tiempo_lagrima*0.5;
        ctx.save(); ctx.fillStyle='#3b82f6';
        ctx.beginPath(); ctx.ellipse(tx,ty+3,2,3,0,0,Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.moveTo(tx-2,ty+2); ctx.lineTo(tx,ty-1); ctx.lineTo(tx+2,ty+2);
        ctx.closePath(); ctx.fill(); ctx.restore();
      }
      if (this.estado==='rainy'&&izquierdo) {
        const ty=cy+ry+((this.tiempo*14)%18);
        ctx.save(); ctx.fillStyle='#4488cc'; ctx.globalAlpha=0.65;
        ctx.beginPath(); ctx.ellipse(cx,ty+2,1.5,2.5,0,0,Math.PI*2); ctx.fill(); ctx.restore();
      }
    } else if (this.estado==='cold') {
      ctx.save(); ctx.fillStyle='#000000'; ctx.beginPath();
      ctx.moveTo(cx-rx-3,cy-ry-4); ctx.lineTo(cx+rx+3,cy-ry-4);
      ctx.lineTo(cx+rx+3,cy-ry+2); ctx.lineTo(cx-rx-3,cy-ry+2);
      ctx.closePath(); ctx.fill();
      ctx.strokeStyle=color; ctx.lineWidth=1.8;
      ctx.beginPath(); ctx.moveTo(cx-rx+3,cy-ry-1.5); ctx.lineTo(cx+rx-3,cy-ry-1.5); ctx.stroke();
      ctx.restore();
    }
  }

  dibujar_boca_eilik(cx, cy, color) {
    const ctx=this.ctx; const t=this.tiempo;
    ctx.save(); ctx.fillStyle=color; ctx.strokeStyle=color;

    if (this.estado==='idle'&&this._idle_action==='yawn') {
      ctx.beginPath(); ctx.ellipse(cx,cy,3,5,0,0,Math.PI*2); ctx.fill();
    } else if (this.estado==='happy'||this.estado==='confirm'||(this.estado==='idle'&&this._idle_action==='wink')) {
      ctx.beginPath(); ctx.arc(cx,cy-3,10,0,Math.PI); ctx.fill();
      ctx.strokeStyle='#ffffff'; ctx.lineWidth=1.5; ctx.lineCap='round';
      ctx.beginPath(); ctx.moveTo(cx-10,cy-3); ctx.lineTo(cx+10,cy-3); ctx.stroke();
    } else if (this.estado==='sad'||this.estado==='angry'||(this.estado==='idle'&&this._idle_action==='sigh')) {
      ctx.lineWidth=2.5; ctx.beginPath(); ctx.arc(cx,cy+5,8,0,Math.PI); ctx.stroke();
    } else if (this.estado==='listening') {
      const rd=2.5+1.0*Math.sin(t*3.5);
      ctx.beginPath(); ctx.arc(cx,cy,rd,0,Math.PI*2); ctx.fill();
    } else if (this.estado==='talking') {
      ctx.lineWidth=3.0; ctx.lineCap='round';
      for (let i=-2;i<=2;i++) {
        const fase=Math.abs(i); const h=2.5+10.0*Math.abs(Math.sin(t*15-fase*0.7)); const x=cx+i*5;
        ctx.beginPath(); ctx.moveTo(x,cy-h/2); ctx.lineTo(x,cy+h/2); ctx.stroke();
      }
    } else if (this.estado==='error') {
      ctx.lineWidth=2.5; ctx.lineCap='round';
      ctx.beginPath(); ctx.moveTo(cx-9,cy); ctx.lineTo(cx-4,cy-2); ctx.lineTo(cx,cy+2);
      ctx.lineTo(cx+4,cy-2); ctx.lineTo(cx+9,cy); ctx.stroke();
    } else if (this.estado==='hot') {
      ctx.beginPath(); ctx.ellipse(cx,cy,5,3.5,0,0,Math.PI*2); ctx.fill();
    } else if (this.estado==='cold') {
      ctx.lineWidth=2; ctx.lineCap='round';
      const tr=Math.sin(t*28)*1.3;
      ctx.beginPath(); ctx.moveTo(cx-7+tr,cy); ctx.lineTo(cx+7+tr,cy); ctx.stroke();
    } else if (this.estado==='rainy') {
      ctx.lineWidth=2.0;
      ctx.beginPath(); ctx.arc(cx,cy+7,6,0.08,Math.PI-0.08); ctx.stroke();
    } else if (this.estado==='stormy') {
      ctx.lineWidth=2.5; ctx.lineCap='round';
      const jt=(Math.random()-0.5)*1.5;
      ctx.beginPath(); ctx.moveTo(cx-8,cy+jt); ctx.lineTo(cx-3,cy-1+jt);
      ctx.lineTo(cx+3,cy+1+jt); ctx.lineTo(cx+8,cy+jt); ctx.stroke();
    } else if (this.estado==='windy') {
      ctx.lineWidth=2.5;
      ctx.beginPath(); ctx.arc(cx+3,cy,7,-0.3,Math.PI*0.8); ctx.stroke();
    } else if (this.estado==='cloudy') {
      ctx.lineWidth=2.0; ctx.lineCap='round';
      ctx.beginPath(); ctx.moveTo(cx-6,cy); ctx.quadraticCurveTo(cx,cy+2.5,cx+6,cy); ctx.stroke();
    } else {
      ctx.lineWidth=2.5; ctx.lineCap='round';
      ctx.beginPath(); ctx.moveTo(cx-7,cy); ctx.lineTo(cx+7,cy); ctx.stroke();
    }
    ctx.restore();
  }

  loop_render() {
    const ctx = this.ctx;
    ctx.clearRect(0,0,this.CANVAS_W,this.CANVAS_H);

    this.tiempo += 0.04;
    this.tiempo_lagrima = (this.tiempo_lagrima+0.3)%20.0;

    // Deriva flotante — Lissajous suave
    this._drift_px += 0.003;
    this._drift_py += 0.00195;
    const raw_x = 17*Math.sin(this._drift_px) + 6*Math.sin(this._drift_px*2.6+1.1);
    const raw_y = 10*Math.sin(this._drift_py) + 3*Math.sin(this._drift_py*1.85+0.8);
    this.drift_x = Math.max(0, Math.min(50, 24+raw_x));
    this.drift_y = Math.max(0, Math.min(28, 13+raw_y));

    // Interpolaciones (k=0.20)
    this.cur_zoom_x_izq += (this.tgt_zoom_x_izq-this.cur_zoom_x_izq)*0.20;
    this.cur_zoom_y_izq += (this.tgt_zoom_y_izq-this.cur_zoom_y_izq)*0.20;
    this.cur_zoom_x_der += (this.tgt_zoom_x_der-this.cur_zoom_x_der)*0.20;
    this.cur_zoom_y_der += (this.tgt_zoom_y_der-this.cur_zoom_y_der)*0.20;
    this.cur_look_x += (this.tgt_look_x-this.cur_look_x)*0.20;
    this.cur_look_y += (this.tgt_look_y-this.cur_look_y)*0.20;

    let zx_i=this.cur_zoom_x_izq, zy_i=this.cur_zoom_y_izq;
    let zx_d=this.cur_zoom_x_der, zy_d=this.cur_zoom_y_der;

    let err_x=0, err_y=0;
    if      (this.estado==='error')   { err_x=(Math.random()-0.5)*2.2; err_y=(Math.random()-0.5)*2.2; }
    else if (this.estado==='confirm') { err_y=1.5*Math.sin(this.tiempo*20); }
    else if (this.estado==='cold')    { err_x=(Math.random()-0.5)*0.9; }
    else if (this.estado==='stormy')  { err_x=(Math.random()-0.5)*1.3; err_y=(Math.random()-0.5)*0.9; }

    let cy_i=this.izq_cy+err_y, cy_d=this.der_cy+err_y;

    if (['idle','cloudy','rainy'].includes(this.estado)) {
      const resp=1.0+0.02*Math.sin(this.tiempo*2);
      zx_i*=resp; zy_i*=resp; zx_d*=resp; zy_d*=resp;
      if (this._idle_action==='yawn')  { zy_i*=0.45; zy_d*=0.45; zx_i*=1.15; zx_d*=1.15; }
      else if (this._idle_action==='sigh') { zy_i*=0.75; zy_d*=0.75; }
    } else if (this.estado==='talking') {
      const onda=0.95+0.06*Math.abs(Math.sin(this.tiempo*15));
      zy_i*=onda; zy_d*=onda;
    } else if (this.estado==='listening') {
      const flot=2.0*Math.sin(this.tiempo*3);
      cy_i+=flot; cy_d+=flot;
    } else if (this.estado==='hot') {
      zy_i*=0.60+0.05*Math.sin(this.tiempo*1.2);
      zy_d*=0.60+0.05*Math.sin(this.tiempo*1.2);
    } else if (this.estado==='windy') {
      err_x+=0.65*Math.sin(this.tiempo*8.5);
    }

    const cx_izq=this.izq_cx+this.cur_look_x+err_x;
    const cx_der=this.der_cx+this.cur_look_x+err_x;
    const color=this.colores[this.estado]||'#00f0ff';

    // Dibujar EMO con offset de deriva
    ctx.save();
    ctx.translate(this.drift_x, this.drift_y);

    ctx.fillStyle='#000000';
    ctx.fillRect(0,0,this.ancho,this.alto);

    this.dibujar_contorno_gris_emo();
    this.dibujar_ojo_intellar(cx_izq, cy_i, this.base_rx*zx_i, this.base_ry*zy_i, color, true);
    this.dibujar_ojo_intellar(cx_der, cy_d, this.base_rx*zx_d, this.base_ry*zy_d, color, false);

    const boca_x=this.boca_cx+this.cur_look_x*0.7+err_x;
    const boca_y=this.boca_cy+this.cur_look_y*0.5+err_y;
    this.dibujar_boca_eilik(boca_x, boca_y, color);

    if (this.estado==='confirm'&&this.msg_confirmacion) {
      let md=this.msg_confirmacion.toUpperCase();
      if (md.length>28) md=md.slice(0,25)+'...';
      ctx.save();
      ctx.fillStyle=color; ctx.font='bold 7px Consolas,monospace'; ctx.textAlign='center';
      ctx.fillText(md, this.ancho/2, 106);
      ctx.restore();
    }

    if (this.estado==='error'&&Math.random()<0.12) {
      ctx.fillStyle='#000000'; ctx.fillRect(0,0,this.ancho,this.alto);
    }

    ctx.restore();

    // Particulas climaticas (espacio absoluto)
    this._dibujar_particulas();
  }

  _startLoops() {
    const renderLoop = () => { this.loop_render(); requestAnimationFrame(renderLoop); };
    requestAnimationFrame(renderLoop);

    const parpadeable = ['idle','listening','talking','happy','confirm','cloudy','rainy','windy','cold','hot'];
    const loopParpadeo = () => {
      if (parpadeable.includes(this.estado)&&this._idle_action==='none') {
        const ay=this.tgt_zoom_y_izq, ad=this.tgt_zoom_y_der;
        this.tgt_zoom_y_izq=0.01; this.tgt_zoom_y_der=0.01;
        setTimeout(()=>{ if(parpadeable.includes(this.estado)){ this.tgt_zoom_y_izq=ay; this.tgt_zoom_y_der=ad; } }, 90);
      }
      setTimeout(loopParpadeo, 2500+Math.random()*3500);
    };
    setTimeout(loopParpadeo, 1500);

    const loopSaccades = () => {
      if (['idle','listening','cloudy'].includes(this.estado)&&this._idle_action==='none') {
        if (Math.random()<0.65) { this.tgt_look_x=(Math.random()-0.5)*12.0; this.tgt_look_y=(Math.random()-0.5)*6.0; }
        else { this.tgt_look_x=0.0; this.tgt_look_y=0.0; }
      }
      setTimeout(loopSaccades, 1200+Math.random()*2300);
    };
    setTimeout(loopSaccades, 2000);

    const loopIdleActions = () => {
      if (this.estado==='idle'&&this._idle_action==='none') {
        const acciones=['wink','sigh','curious','yawn'];
        const accion=acciones[Math.floor(Math.random()*acciones.length)];
        this._idle_action=accion;
        let dur=2000;
        if      (accion==='wink')    { dur=1000; this.tgt_zoom_y_izq=0.01; }
        else if (accion==='yawn')    { dur=2500; }
        else if (accion==='sigh')    { this.tgt_look_y=4.0; }
        else if (accion==='curious') { this.tgt_look_x=-4.0; this.tgt_look_y=-3.0; this.tgt_zoom_y_izq=0.7; }
        setTimeout(()=>{
          this._idle_action='none';
          if (this.estado==='idle') {
            this.tgt_zoom_x_izq=1.0; this.tgt_zoom_y_izq=1.0;
            this.tgt_zoom_x_der=1.0; this.tgt_zoom_y_der=1.0;
            this.tgt_look_x=0.0; this.tgt_look_y=0.0;
          }
        }, dur);
      }
      setTimeout(loopIdleActions, 12000+Math.random()*10000);
    };
    setTimeout(loopIdleActions, 5000);
  }
}

window.emoFace = null;
document.addEventListener('DOMContentLoaded', () => {
  window.emoFace = new EmoCanvasFace('emoCanvas');
});

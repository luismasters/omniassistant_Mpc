"""
Gestor de Recordatorios para Argus (OmniAssistant).
Maneja programación, persistencia en JSON, planificador en segundo plano
y soporte para eventos puntuales, recurrentes, sin hora fija y cumpleaños.
"""

import os
import json
import time
import uuid
import re
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from modulos.logger import logger

RUTA_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RUTA_JSON = os.path.join(RUTA_DATA, "recordatorios.json")


class Recordatorio:
    def __init__(
        self,
        mensaje: str,
        timestamp_expiracion: float,
        id_rec: Optional[str] = None,
        creado_en: Optional[float] = None,
        estado: str = "pendiente",
        tipo: str = "puntual",
        patron_recurrencia: Optional[str] = None,
        sin_hora_especifica: bool = False,
        aviso_previo_dias: int = 0,
        notificado_previo: bool = False,
        origen: str = "ia"
    ):
        self.id = id_rec or f"rec_{uuid.uuid4().hex[:8]}"
        self.mensaje = mensaje
        self.timestamp_expiracion = float(timestamp_expiracion)
        self.creado_en = creado_en or time.time()
        self.estado = estado
        self.tipo = tipo
        self.patron_recurrencia = patron_recurrencia
        self.sin_hora_especifica = sin_hora_especifica
        self.aviso_previo_dias = int(aviso_previo_dias)
        self.notificado_previo = bool(notificado_previo)
        self.origen = origen

    def to_dict(self) -> dict:
        dt_exp = datetime.fromtimestamp(self.timestamp_expiracion)
        dt_creado = datetime.fromtimestamp(self.creado_en)
        ahora = datetime.now()

        diff_sec = self.timestamp_expiracion - ahora.timestamp()
        if self.estado != "pendiente":
            restante_str = "Completado" if self.estado == "completado" else "Cancelado"
        elif diff_sec <= 0:
            restante_str = "¡Vence ahora!"
        else:
            dias = int(diff_sec // 86400)
            horas = int((diff_sec % 86400) // 3600)
            mins = int((diff_sec % 3600) // 60)
            if dias > 0:
                restante_str = f"Faltan {dias}d {horas}h"
            elif horas > 0:
                restante_str = f"Faltan {horas}h {mins}m"
            else:
                restante_str = f"Faltan {mins} min"

        return {
            "id": self.id,
            "mensaje": self.mensaje,
            "timestamp_expiracion": self.timestamp_expiracion,
            "expiracion_iso": dt_exp.strftime("%Y-%m-%d %H:%M:%S"),
            "expiracion_bonita": dt_exp.strftime("%d/%m/%Y %H:%M"),
            "creado_en": self.creado_en,
            "creado_en_iso": dt_creado.strftime("%Y-%m-%d %H:%M:%S"),
            "estado": self.estado,
            "tipo": self.tipo,
            "patron_recurrencia": self.patron_recurrencia,
            "sin_hora_especifica": self.sin_hora_especifica,
            "aviso_previo_dias": self.aviso_previo_dias,
            "notificado_previo": self.notificado_previo,
            "origen": self.origen,
            "tiempo_restante_str": restante_str
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Recordatorio':
        return cls(
            id_rec=data.get("id"),
            mensaje=data.get("mensaje", ""),
            timestamp_expiracion=data.get("timestamp_expiracion", time.time()),
            creado_en=data.get("creado_en"),
            estado=data.get("estado", "pendiente"),
            tipo=data.get("tipo", "puntual"),
            patron_recurrencia=data.get("patron_recurrencia"),
            sin_hora_especifica=data.get("sin_hora_especifica", False),
            aviso_previo_dias=data.get("aviso_previo_dias", 0),
            notificado_previo=data.get("notificado_previo", False),
            origen=data.get("origen", "ia")
        )


class GestorRecordatorios:
    def __init__(self):
        self.recordatorios: Dict[str, Recordatorio] = {}
        self.callbacks: List[Callable[[dict], None]] = []
        # RLock es NECESARIO aquí porque _guardar_recordatorios()
        # y marcar_completado() adquieren el mismo lock internamente
        # mientras ya están dentro de otro with self._lock:
        # (ej. crear_recordatorio -> _guardar_recordatorios).
        # Con threading.Lock() normal se produce un DEADLOCK y el
        # recordatorio NUNCA se guarda, aunque el log de creación
        # aparece. RLock permite que el mismo hilo readquiera el lock.
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._ultima_fecha_interaccion: Optional[str] = None

        os.makedirs(RUTA_DATA, exist_ok=True)
        self._cargar_recordatorios()
        self.iniciar_scheduler()

    def suscribir_callback_aviso(self, callback: Callable[[dict], None]):
        """Registra una función callback para notificar cuando expira un recordatorio."""
        if callback not in self.callbacks:
            self.callbacks.append(callback)
            logger.debug("[RECORDATORIOS] Callback registrado en GestorRecordatorios.")

    def _notificar_subscriptores(self, rec: Recordatorio, es_previo: bool = False):
        data = rec.to_dict()
        data["es_aviso_previo"] = es_previo
        logger.info(f"[RECORDATORIOS] NOTIFICACION DISPARADA! ID={rec.id} | Mensaje='{rec.mensaje}'")
        for cb in list(self.callbacks):
            try:
                cb(data)
            except Exception as e:
                logger.exception(f"[RECORDATORIOS] Error ejecutando callback de recordatorio: {e}")

    def _cargar_recordatorios(self):
        with self._lock:
            if not os.path.exists(RUTA_JSON):
                return
            try:
                with open(RUTA_JSON, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
                    for item in datos:
                        rec = Recordatorio.from_dict(item)
                        self.recordatorios[rec.id] = rec
                logger.info(f"[RECORDATORIOS] {len(self.recordatorios)} recordatorios cargados desde JSON.")
            except Exception as e:
                logger.exception(f"[RECORDATORIOS] Error leyendo {RUTA_JSON}: {e}")

    def _guardar_recordatorios(self):
        with self._lock:
            try:
                datos = [rec.to_dict() for rec in self.recordatorios.values()]
                with open(RUTA_JSON, 'w', encoding='utf-8') as f:
                    json.dump(datos, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.exception(f"[RECORDATORIOS] Error guardando recordatorios en JSON: {e}")

    def parsear_tiempo(self, tiempo_str: str) -> tuple[float, bool, bool, int]:
        """
        Convierte expresiones de tiempo o formatos ISO/locales a (timestamp_epoch, sin_hora, es_cumple, aviso_dias).
        Ejemplos:
          - "en 13 días" -> time.time() + 13 días
          - "en 2 semanas" -> time.time() + 14 días
          - "2026-08-12T15:30" -> timestamp exacto de HTML datetime-local
          - "mañana a las 15:00" -> mañana a esa hora
          - "25 de agosto" -> timestamp 2026-08-25 09:00 (sin_hora=True)
        """
        ahora = datetime.now()
        t_str = tiempo_str.lower().strip()

        sin_hora = False
        es_cumple = False
        aviso_dias = 0

        # --- 0. Formato ISO o Datetime local (HTML input datetime-local) ---
        match_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})(?:[ tT](\d{2}):(\d{2})(?::(\d{2}))?)?', t_str)
        if match_iso:
            y, m, d = int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3))
            hh = int(match_iso.group(4)) if match_iso.group(4) else 9
            mm = int(match_iso.group(5)) if match_iso.group(5) else 0
            ss = int(match_iso.group(6)) if match_iso.group(6) else 0
            if not match_iso.group(4):
                sin_hora = True
            exp_dt = datetime(y, m, d, hh, mm, ss)
            return exp_dt.timestamp(), sin_hora, False, 0

        # Formato DD/MM/YYYY [HH:MM]
        match_slash = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?', t_str)
        if match_slash:
            d, m, y = int(match_slash.group(1)), int(match_slash.group(2)), int(match_slash.group(3))
            hh = int(match_slash.group(4)) if match_slash.group(4) else 9
            mm = int(match_slash.group(5)) if match_slash.group(5) else 0
            if not match_slash.group(4):
                sin_hora = True
            exp_dt = datetime(y, m, d, hh, mm, 0)
            return exp_dt.timestamp(), sin_hora, False, 0

        # Extraer hora específica si existe ("a las 15:30", "a las 3pm", "15:30")
        extra_h, extra_m = None, None
        match_hora = re.search(r'(?:a las\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)|(?:\b(\d{1,2}):(\d{2})\s*(am|pm)?\b)', t_str)
        if match_hora:
            if match_hora.group(1) is not None:
                h_val = int(match_hora.group(1))
                m_val = int(match_hora.group(2)) if match_hora.group(2) else 0
                ampm = match_hora.group(3)
            else:
                h_val = int(match_hora.group(4))
                m_val = int(match_hora.group(5))
                ampm = match_hora.group(6)

            if ampm == 'pm' and h_val < 12:
                h_val += 12
            elif ampm == 'am' and h_val == 12:
                h_val = 0
            extra_h, extra_m = h_val, m_val

        # --- 1. Expresiones Palabras Clave: "pasado mañana", "mañana", "hoy" ---
        if "pasado mañana" in t_str or "pasado manana" in t_str:
            base_dt = ahora + timedelta(days=2)
            hh = extra_h if extra_h is not None else 9
            mm = extra_m if extra_m is not None else 0
            s_hora = extra_h is None
            exp_dt = base_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
            return exp_dt.timestamp(), s_hora, False, 0

        if "mañana" in t_str or "manana" in t_str:
            base_dt = ahora + timedelta(days=1)
            hh = extra_h if extra_h is not None else 9
            mm = extra_m if extra_m is not None else 0
            s_hora = extra_h is None
            exp_dt = base_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
            return exp_dt.timestamp(), s_hora, False, 0

        # --- 2. Tiempos Relativos (días, semanas, meses, años, horas, minutos, segundos) ---
        match_rel = re.search(
            r'\ben\s+(\d+)\s*(segundos?|seg|segs|s|minutos?|min|mins|horas?|h|hrs?|días?|dias?|d|semanas?|sems?|sem|meses|mes|años?|anios?)\b',
            t_str
        )
        if match_rel:
            cant = int(match_rel.group(1))
            unidad = match_rel.group(2)

            if unidad in ['segundo', 'segundos', 'seg', 'segs', 's']:
                delta = timedelta(seconds=cant)
                exp_dt = ahora + delta
                return exp_dt.timestamp(), False, False, 0
            elif unidad in ['minuto', 'minutos', 'min', 'mins']:
                delta = timedelta(minutes=cant)
                exp_dt = ahora + delta
                return exp_dt.timestamp(), False, False, 0
            elif unidad in ['hora', 'horas', 'h', 'hr', 'hrs']:
                delta = timedelta(hours=cant)
                exp_dt = ahora + delta
                return exp_dt.timestamp(), False, False, 0
            elif unidad in ['día', 'días', 'dia', 'dias', 'd']:
                target_dt = ahora + timedelta(days=cant)
                if extra_h is not None:
                    exp_dt = target_dt.replace(hour=extra_h, minute=extra_m, second=0, microsecond=0)
                    return exp_dt.timestamp(), False, False, 0
                else:
                    exp_dt = target_dt.replace(hour=9, minute=0, second=0, microsecond=0)
                    return exp_dt.timestamp(), True, False, 0
            elif unidad in ['semana', 'semanas', 'sem', 'sems']:
                target_dt = ahora + timedelta(days=cant * 7)
                if extra_h is not None:
                    exp_dt = target_dt.replace(hour=extra_h, minute=extra_m, second=0, microsecond=0)
                    return exp_dt.timestamp(), False, False, 0
                else:
                    exp_dt = target_dt.replace(hour=9, minute=0, second=0, microsecond=0)
                    return exp_dt.timestamp(), True, False, 0
            elif unidad in ['mes', 'meses']:
                target_dt = ahora + timedelta(days=cant * 30)
                if extra_h is not None:
                    exp_dt = target_dt.replace(hour=extra_h, minute=extra_m, second=0, microsecond=0)
                    return exp_dt.timestamp(), False, False, 0
                else:
                    exp_dt = target_dt.replace(hour=9, minute=0, second=0, microsecond=0)
                    return exp_dt.timestamp(), True, False, 0
            elif unidad in ['año', 'años', 'anio', 'anios']:
                target_dt = ahora + timedelta(days=cant * 365)
                if extra_h is not None:
                    exp_dt = target_dt.replace(hour=extra_h, minute=extra_m, second=0, microsecond=0)
                    return exp_dt.timestamp(), False, False, 0
                else:
                    exp_dt = target_dt.replace(hour=9, minute=0, second=0, microsecond=0)
                    return exp_dt.timestamp(), True, False, 0

        # --- 3. Meses y Fechas ("25 de agosto", "6 de diciembre") ---
        meses = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
            "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
        }
        match_fecha = re.search(r'(\d{1,2})\s+de\s+([a-z]+)', t_str)
        if match_fecha:
            dia = int(match_fecha.group(1))
            nombre_mes = match_fecha.group(2)
            mes = meses.get(nombre_mes, ahora.month)
            anio = ahora.year
            hh = extra_h if extra_h is not None else 9
            mm = extra_m if extra_m is not None else 0
            s_hora = extra_h is None
            exp_dt = datetime(anio, mes, dia, hh, mm, 0)
            if exp_dt <= ahora:
                exp_dt = datetime(anio + 1, mes, dia, hh, mm, 0)

            if 'cumple' in t_str:
                es_cumple = True
                aviso_dias = 1

            return exp_dt.timestamp(), s_hora, es_cumple, aviso_dias

        # --- 4. Horas fijas ("a las 21:00", "a las 9pm", "10:30") ---
        if extra_h is not None:
            exp_dt = ahora.replace(hour=extra_h, minute=extra_m, second=0, microsecond=0)
            if exp_dt <= ahora:
                exp_dt += timedelta(days=1)
            return exp_dt.timestamp(), False, False, 0

        # --- Fallback: 10 minutos ---
        return (ahora + timedelta(minutes=10)).timestamp(), False, False, 0

    def crear_recordatorio(
        self,
        mensaje: str,
        tiempo_str: str,
        opciones: str = "",
        origen: str = "ia"
    ) -> dict:
        """Crea y programa un nuevo recordatorio."""
        ts_exp, sin_hora, es_cumple, aviso_dias = self.parsear_tiempo(tiempo_str)

        tipo = "puntual"
        patron = None
        opc_lower = opciones.lower() if opciones else ""

        if "diario" in opc_lower or "recurrente" in opc_lower:
            tipo = "recurrente"
            patron = "diario"

        if "sin_hora" in opc_lower:
            sin_hora = True

        if "cumple" in opc_lower or es_cumple:
            aviso_dias = 1
            sin_hora = True

        rec = Recordatorio(
            mensaje=mensaje,
            timestamp_expiracion=ts_exp,
            tipo=tipo,
            patron_recurrencia=patron,
            sin_hora_especifica=sin_hora,
            aviso_previo_dias=aviso_dias,
            origen=origen
        )

        with self._lock:
            self.recordatorios[rec.id] = rec

        self._guardar_recordatorios()
        logger.info(f"[RECORDATORIOS] Recordatorio creado: '{mensaje}' para {rec.to_dict()['expiracion_iso']}")
        return rec.to_dict()

    def editar_recordatorio(
        self,
        id_rec: str,
        mensaje: Optional[str] = None,
        tiempo_str: Optional[str] = None,
        opciones: Optional[str] = None
    ) -> Optional[dict]:
        """Edita un recordatorio existente."""
        with self._lock:
            if id_rec not in self.recordatorios:
                return None
            rec = self.recordatorios[id_rec]
            if mensaje:
                rec.mensaje = mensaje.strip()
            if tiempo_str and tiempo_str.strip():
                ts_exp, sin_hora, es_cumple, aviso_dias = self.parsear_tiempo(tiempo_str)
                rec.timestamp_expiracion = ts_exp
                rec.sin_hora_especifica = sin_hora
                if es_cumple:
                    rec.aviso_previo_dias = 1
            if opciones is not None:
                opc_lower = opciones.lower()
                if "diario" in opc_lower or "recurrente" in opc_lower:
                    rec.tipo = "recurrente"
                    rec.patron_recurrencia = "diario"
                elif "puntual" in opc_lower or opc_lower == "":
                    rec.tipo = "puntual"
                    rec.patron_recurrencia = None

                if "sin_hora" in opc_lower:
                    rec.sin_hora_especifica = True
                if "cumple" in opc_lower:
                    rec.aviso_previo_dias = 1
                    rec.sin_hora_especifica = True

            self._guardar_recordatorios()
            logger.info(f"[RECORDATORIOS] Recordatorio {id_rec} editado: '{rec.mensaje}' ({rec.to_dict()['expiracion_iso']})")
            return rec.to_dict()

    def cambiar_estado(self, id_rec: str, nuevo_estado: str) -> bool:
        """Cambia el estado de un recordatorio ('pendiente', 'completado', 'cancelado')."""
        with self._lock:
            if id_rec in self.recordatorios:
                self.recordatorios[id_rec].estado = nuevo_estado
                self._guardar_recordatorios()
                logger.info(f"[RECORDATORIOS] Estado de {id_rec} cambiado a '{nuevo_estado}'")
                return True
            return False

    def listar_recordatorios(self, incluir_completados: bool = False) -> List[dict]:
        with self._lock:
            res = []
            for rec in self.recordatorios.values():
                if incluir_completados or rec.estado == "pendiente":
                    res.append(rec.to_dict())
            res.sort(key=lambda x: x["timestamp_expiracion"])
            return res

    def cancelar_recordatorio(self, id_o_texto: str) -> bool:
        with self._lock:
            encontrado = None
            if id_o_texto in self.recordatorios:
                encontrado = id_o_texto
            else:
                for rec_id, rec in self.recordatorios.items():
                    if rec.estado == "pendiente" and id_o_texto.lower() in rec.mensaje.lower():
                        encontrado = rec_id
                        break
            if encontrado:
                self.recordatorios[encontrado].estado = "cancelado"
                self._guardar_recordatorios()
                logger.info(f"[RECORDATORIOS] Recordatorio cancelado: ID={encontrado}")
                return True
            return False

    def marcar_completado(self, id_rec: str):
        with self._lock:
            if id_rec in self.recordatorios:
                rec = self.recordatorios[id_rec]
                if rec.tipo == "recurrente" and rec.patron_recurrencia == "diario":
                    # Recalcular próximo disparo para mañana a la misma hora
                    dt_actual = datetime.fromtimestamp(rec.timestamp_expiracion)
                    dt_manana = dt_actual + timedelta(days=1)
                    rec.timestamp_expiracion = dt_manana.timestamp()
                    rec.estado = "pendiente"
                    rec.notificado_previo = False
                    logger.info(f"[RECORDATORIOS] Recordatorio diario {id_rec} reprogramado para {dt_manana}")
                else:
                    rec.estado = "completado"
                self._guardar_recordatorios()

    def comprobar_primera_interaccion_dia(self):
        """Dispara los recordatorios del día sin hora específica o avisos previos de cumpleaños."""
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        if self._ultima_fecha_interaccion == hoy_str:
            return

        self._ultima_fecha_interaccion = hoy_str
        logger.info(f"[RECORDATORIOS] Comprobando recordatorios del dia ({hoy_str}) para primera interaccion...")

        ahora_dt = datetime.now()
        hoy_fecha = ahora_dt.date()

        with self._lock:
            for rec in list(self.recordatorios.values()):
                if rec.estado != "pendiente":
                    continue

                dt_exp = datetime.fromtimestamp(rec.timestamp_expiracion)
                fecha_exp = dt_exp.date()

                # 1. Caso Cumpleaños / Aviso previo (Día anterior)
                if rec.aviso_previo_dias > 0 and not rec.notificado_previo:
                    fecha_aviso = fecha_exp - timedelta(days=rec.aviso_previo_dias)
                    if hoy_fecha == fecha_aviso:
                        rec.notificado_previo = True
                        self._guardar_recordatorios()
                        self._notificar_subscriptores(rec, es_previo=True)

                # 2. Caso Día de hoy (Sin hora específica o cumpleaños hoy)
                if rec.sin_hora_especifica and hoy_fecha == fecha_exp:
                    self.marcar_completado(rec.id)
                    self._notificar_subscriptores(rec, es_previo=False)

    def _scheduler_loop(self):
        while self._running:
            try:
                ahora = time.time()
                with self._lock:
                    pendientes = [r for r in self.recordatorios.values() if r.estado == "pendiente"]

                for rec in pendientes:
                    # Si no es sin_hora y el timestamp actual ya alcanzó/superó el vencimiento
                    if not rec.sin_hora_especifica and ahora >= rec.timestamp_expiracion:
                        self.marcar_completado(rec.id)
                        self._notificar_subscriptores(rec, es_previo=False)

            except Exception as e:
                logger.exception(f"[RECORDATORIOS] Error en scheduler loop de recordatorios: {e}")
            time.sleep(2)

    def iniciar_scheduler(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._thread.start()
            logger.info("[RECORDATORIOS] Hilo background scheduler de recordatorios iniciado.")

    def detener_scheduler(self):
        self._running = False


# Instancia global del Gestor
gestor_recordatorios = GestorRecordatorios()

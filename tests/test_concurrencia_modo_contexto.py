# -*- coding: utf-8 -*-
"""
H.2 — Serialización del cambio de modo / limpieza con los turnos.

`cambiar_modo`, `limpiar_contexto`, `limpiar_memoria` y
`reemplazar_contexto_chat` adquieren el MISMO `config.RLOCK_CONTEXTO` que usa
un turno (alias `_RLOCK_PROC` en `modulos.ia`). Así un cambio de modo o un
limpiado NUNCA se intercalan con un turno en curso:

  - los mensajes finales del turno quedan en el contexto del modo ANTERIOR;
  - el contexto/perfil del modo NUEVO no se contamina;
  - un limpiado no corta un streaming a mitad de sílaba.

Estos tests validan el bloqueo determinista (hilo que sostiene el lock) y la
semántica normal de aislamiento por modo (que debe preservarse).
"""

import threading
import time

from config import EstadoGlobal, RLOCK_CONTEXTO


def _estado_nuevo():
    return EstadoGlobal()


def _poseedor_lock(adquirido, soltar):
    with RLOCK_CONTEXTO:
        adquirido.set()
        soltar.wait()


def _lanzar_bloqueado(accion):
    """
    Lanza `accion` en un hilo mientras otro hilo sostiene RLOCK_CONTEXTO.
    Devuelve (t_lock, t_accion, soltar) con la garantía de que `t_accion`
    arrancó y quedó BLOQUEADO esperando el lock (determinista, sin sleeps).
    """
    adquirido = threading.Event()
    soltar = threading.Event()
    t_lock = threading.Thread(target=_poseedor_lock, args=(adquirido, soltar))
    t_lock.start()
    assert adquirido.wait(5), "el hilo poseedor del lock no arrancó"

    t_accion = threading.Thread(target=accion)
    t_accion.start()
    for _ in range(5000):
        if t_accion.is_alive():
            break
        time.sleep(0.001)
    assert t_accion.is_alive(), (
        "la acción terminó pese a que el lock está tomado: "
        "perdió la serialización con el turno"
    )
    return t_lock, t_accion, soltar


# ─── 1. El cambio de modo espera si hay un turno en curso ───────────────────

def test_cambio_modo_espera_si_hay_turno_en_curso():
    estado = _estado_nuevo()
    estado.agregar_mensaje_chat({"role": "user", "parts": ["solo"]})

    t_lock, t_accion, soltar = _lanzar_bloqueado(
        lambda: estado.cambiar_modo("mentor")
    )

    # Mientras el "turno" sostiene el lock, el modo NO debe cambiar aún.
    assert estado.modo_actual == "general"

    soltar.set()
    t_lock.join(5)
    t_accion.join(5)
    assert not t_accion.is_alive()
    assert estado.modo_actual == "mentor"
    assert estado._contextos_por_modo["general"] == [
        {"role": "user", "parts": ["solo"]}
    ]
    assert estado.obtener_contexto_copia() == []


# ─── 2. Mensajes finales del turno quedan en el modo anterior ───────────────

def test_mensajes_finales_del_turno_no_contaminan_modo_nuevo():
    estado = _estado_nuevo()
    seed = {"role": "user", "parts": ["seed"]}
    cierre_1 = {"role": "user", "parts": ["cierre 1"]}
    cierre_2 = {"role": "model", "parts": ["cierre 2"]}
    estado.agregar_mensaje_chat(seed)

    # "Turno" que escribe sus mensajes finales bajo el lock de turno...
    with RLOCK_CONTEXTO:
        estado.agregar_mensaje_chat(cierre_1)
        estado.agregar_mensaje_chat(cierre_2)

    # ...y el cambio de modo que ocurre después: la sesión quedó completa.
    estado.cambiar_modo("mentor")

    assert estado._contextos_por_modo["general"] == [seed, cierre_1, cierre_2]
    assert estado.obtener_contexto_copia() == []
    assert estado.modo_actual == "mentor"


# ─── 3. limpiar_contexto espera si hay un turno en curso ────────────────────

def test_limpiar_contexto_espera_si_hay_turno_en_curso():
    estado = _estado_nuevo()
    estado.agregar_mensaje_chat({"role": "user", "parts": ["quedate"]})
    estado.agregar_evidencia_web("[RESULTADOS]\nfactor")

    t_lock, t_accion, soltar = _lanzar_bloqueado(
        lambda: estado.limpiar_contexto()
    )

    assert estado.obtener_contexto_copia() == [
        {"role": "user", "parts": ["quedate"]}
    ]
    assert len(estado.obtener_evidencia_web()) == 1

    soltar.set()
    t_lock.join(5)
    t_accion.join(5)
    assert not t_accion.is_alive()
    assert estado.obtener_contexto_copia() == []
    assert estado.obtener_evidencia_web() == []


# ─── 4. limpiar_memoria espera si hay un turno en curso ─────────────────────

def test_limpiar_memoria_espera_si_hay_turno_en_curso():
    estado = _estado_nuevo()
    estado.agregar_mensaje_chat({"role": "user", "parts": ["x"]})
    estado.agregar_archivo_memoria("C:/proyecto/app.py")
    estado.documento_volatil = "doc"
    estado.agregar_evidencia_web("ev")

    t_lock, t_accion, soltar = _lanzar_bloqueado(
        lambda: estado.limpiar_memoria()
    )

    assert estado.obtener_contexto_copia() == [{"role": "user", "parts": ["x"]}]

    soltar.set()
    t_lock.join(5)
    t_accion.join(5)
    assert not t_accion.is_alive()
    assert estado.obtener_contexto_copia() == []
    assert estado.obtener_archivos_copia() == set()
    assert estado.documento_volatil == ""
    assert estado.obtener_evidencia_web() == []


# ─── 5. reemplazar_contexto_chat espera si hay un turno en curso ────────────

def test_reemplazar_contexto_espera_si_hay_turno_en_curso():
    estado = _estado_nuevo()
    estado.agregar_mensaje_chat({"role": "user", "parts": ["viejo"]})
    nuevo = [{"role": "user", "parts": ["nuevo"]}]

    t_lock, t_accion, soltar = _lanzar_bloqueado(
        lambda: estado.reemplazar_contexto_chat(nuevo)
    )

    assert estado.obtener_contexto_copia() == [
        {"role": "user", "parts": ["viejo"]}
    ]

    soltar.set()
    t_lock.join(5)
    t_accion.join(5)
    assert not t_accion.is_alive()
    assert estado.obtener_contexto_copia() == nuevo


# ─── 6. La semántica de aislamiento por modo se preserva ────────────────────

def test_aislamiento_contexto_por_modo_se_preserva():
    estado = _estado_nuevo()
    g1 = {"role": "user", "parts": ["general 1"]}
    g2 = {"role": "model", "parts": ["general 2"]}
    m1 = {"role": "user", "parts": ["mentor 1"]}
    estado.agregar_mensaje_chat(g1)
    estado.agregar_mensaje_chat(g2)

    estado.cambiar_modo("mentor")
    assert estado.obtener_contexto_copia() == []

    estado.agregar_mensaje_chat(m1)

    estado.cambiar_modo("general")
    assert estado.obtener_contexto_copia() == [g1, g2]

    estado.cambiar_modo("mentor")
    assert estado.obtener_contexto_copia() == [m1]
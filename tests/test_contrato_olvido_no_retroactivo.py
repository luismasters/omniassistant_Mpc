# -*- coding: utf-8 -*-
"""
Contrato de OLVIDO NO-RETROACTIVO (Opción E — hallazgo H.1 de la auditoría
de integración global).

Semántica formalizada: cuando el usuario olvida un dato desde el panel de
memoria, el olvido NO es retroactivo sobre el contexto activo:

  - La recuperación automática de memoria YA no puede reintroducirlo
    (tombstone en modulos.olvidos; filtro en modulos.recuperador_memoria).
  - La extracción / reescritor YA no pueden volver a persistirlo
    (filtro en modulos.perfil_usuario.rutear_hecho y consolidación).
  - `contexto_chat` NO se depura al olvidar: es el registro de la
    conversación (palabras del usuario + respuestas de Argus) y no conserva
    ningún vínculo a `origen_id` que permita identificar de forma segura qué
    mensaje histórico contiene un recuerdo olvidado.
  - `evidencia_web` NO se depura: contiene snippets de búsqueda web sin
    relación con las memorias de panel/bóveda (`origen_id`).

Motivo de la decisión (documentada en AGENTS.md): una purga retroactiva por
coincidencia textual sería imprecisa (borraría conversación legítima) e
inventaría la relación mensaje↔memoria que actualmente no existe. La
prioridad es preservar la integridad del contexto antes que conseguir una
purga aparentemente completa.

Estos tests FIJAN ese contrato: si alguien intenta "arreglar" el olvido con
una purga textual retroactiva, estos test tienen que revisarse a propósito
(no pasan "solos" con esa nueva semántica).
"""

import json
import sys
import threading
import types

import pytest

from config import EstadoGlobal
from modulos import olvidos
from modulos import perfil_usuario as pu
from modulos import resumen_memoria as rm
import modulos.recuperador_memoria as rec


HOY = "2026-01-01"

# Id bóveda válido con el formato del contrato `boveda:<slug>:<10hex>`.
_ID_BOVEDA = "boveda:memoria_ia:488f6c7c78"
_ID_BOVEDA_2 = "boveda:memoria_ia:aabbccddee"


# ─── Helpers ────────────────────────────────────────────────────────────────

def _escribir(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _perfil_con_vidas(*temas):
    return {
        "funcional": {
            "identidad": "Luis",
            "proyecto_actual": "OmniAssistant",
            "hardware_relevante": "",
            "preferencias_comunicacion": "Directo",
            "rutina_uso": "Noche",
        },
        "vida_personal": [
            {"tema": tema, "contenido": f"Con contenido de {tema}", "actualizado": HOY}
            for tema in temas
        ],
    }


def _mensaje(role, texto):
    return {"role": role, "parts": [texto]}


def _estado_nuevo():
    """Estado aislado para el test: nunca toca el singleton de producción."""
    return EstadoGlobal()


# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def olvidos_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(olvidos, "RUTA_OLVIDOS", str(tmp_path / "olvidos.json"))
    return olvidos


@pytest.fixture
def perfil_usuario_tmp(tmp_path, monkeypatch):
    ruta = tmp_path / "perfil_usuario.json"
    monkeypatch.setattr(pu, "RUTA_PERFIL", str(ruta))
    return ruta


@pytest.fixture
def memoria_fake(monkeypatch):
    """
    Inyecta en sys.modules un `modulos.memoria` falso para los caminos que lo
    importan por lazy import (olvido bóveda y recuperador). Evita cargar
    ChromaDB / SentenceTransformer en este test.
    """
    extendido = {"invalidar_por_origen", "obtener_resultado_anticipado_detalle"}

    class _MemoriaFake:
        _detalle = []
        _invalidados = []

        @classmethod
        def invalidar_por_origen(cls, origen_id):
            cls._invalidados.append(origen_id)
            return True

        @classmethod
        def obtener_resultado_anticipado_detalle(cls, consulta):
            return cls._detalle

        @classmethod
        def configurar_detalle(cls, detalle):
            cls._detalle = detalle

        @classmethod
        def invalidaciones(cls):
            return list(cls._invalidados)

    modulo = types.ModuleType("modulos.memoria")
    for nombre in extendido:
        setattr(modulo, nombre, getattr(_MemoriaFake, nombre))
    monkeypatch.setitem(sys.modules, "modulos.memoria", modulo)
    yield _MemoriaFake
    monkeypatch.delitem(sys.modules, "modulos.memoria", raising=False)


def _recuerdo(texto, distancia, origen_id=_ID_BOVEDA, etiqueta="Memoria_IA"):
    return {
        "documento": texto,
        "origen_id": origen_id,
        "origen_fuente": "memoria_manual",
        "etiqueta": etiqueta,
        "fecha_guardado": "2025-01-01 12:00:00",
        "distancia": distancia,
    }


# ─── 1. Olvidar memoria presente en contexto_chat ───────────────────────────

def test_olvidar_presente_en_contexto_no_purga_historial(
    olvidos_tmp, perfil_usuario_tmp
):
    _escribir(perfil_usuario_tmp, _perfil_con_vidas("salud"))
    estado = _estado_nuevo()
    mensajes = [
        _mensaje("user", "Hoy me duelen las rodillas al subir escaleras"),
        _mensaje("model", "Tranquilo, cuidate las rodillas."),
    ]
    for m in mensajes:
        estado.agregar_mensaje_chat(m)

    antes = estado.obtener_contexto_copia()

    resultado = rm.resolver_olvidar("vida:salud")

    assert resultado["exito"] is True
    assert olvidos.esta_olvidado("vida:salud") is True
    # El dato desaparece del perfil (fuente de verdad de memoria).
    perfil_tras = json.load(open(perfil_usuario_tmp, "r", encoding="utf-8"))
    assert perfil_tras["vida_personal"] == []
    # El contexto conversacional queda INTACTO (registro, no memoria).
    assert estado.obtener_contexto_copia() == antes


# ─── 2. Mensajes no relacionados permanecen intactos ────────────────────────

def test_mensajes_no_relacionados_intactos_al_olvidar(olvidos_tmp, perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_con_vidas("salud"))
    estado = _estado_nuevo()
    primero = _mensaje("user", "¿Cómo va el proyecto de FastAPI?")
    segundo = _mensaje("model", "Va bien, terminamos auth.")
    olvidado = _mensaje("user", "Mis rodillas me duelen constantemente")
    estado.agregar_mensaje_chat(primero)
    estado.agregar_mensaje_chat(segundo)
    estado.agregar_mensaje_chat(olvidado)

    rm.resolver_olvidar("vida:salud")

    contexto = estado.obtener_contexto_copia()
    assert contexto[0] == primero
    assert contexto[1] == segundo
    # El mensaje que mencionaba el dato sigue como registro de conversación.
    assert contexto[2] == olvidado
    assert len(contexto) == 3


# ─── 3. Olvidar memoria vigente que no está en el contexto ──────────────────

def test_olvidar_viviente_ausente_del_contexto_no_rompe_nada(
    olvidos_tmp, perfil_usuario_tmp
):
    _escribir(perfil_usuario_tmp, _perfil_con_vidas("deporte"))
    estado = _estado_nuevo()
    estado.agregar_mensaje_chat(_mensaje("user", "Hablemos de desarrollo"))
    antes = estado.obtener_contexto_copia()

    resultado = rm.resolver_olvidar("vida:deporte")

    assert resultado["exito"] is True
    assert olvidos.esta_olvidado("vida:deporte") is True
    assert estado.obtener_contexto_copia() == antes


# ─── 4. Evidencia web NO se depura ──────────────────────────────────────────

def test_evidencia_web_no_se_depura_al_olvidar(olvidos_tmp, perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_con_vidas("salud"))
    estado = _estado_nuevo()
    estado.agregar_evidencia_web("[RESULTADOS DE BÚSQUEDA]\ndominio.com sobre ranking\n")
    evidencias_antes = estado.obtener_evidencia_web()

    rm.resolver_olvidar("vida:salud")

    # La evidencia web es un almacén SEPARADO de snippets de búsqueda, sin
    # vínculo con las memorias de panel/bóveda (origen_id): queda fuera.
    assert estado.obtener_evidencia_web() == evidencias_antes


# ─── 5. _contextos_por_modo NO se alteran ───────────────────────────────────

def test_olvidar_no_afecta_ningun_contexto_por_modo(olvidos_tmp, perfil_usuario_tmp):
    _escribir(perfil_usuario_tmp, _perfil_con_vidas("salud"))
    estado = _estado_nuevo()
    estado.agregar_mensaje_chat(_mensaje("user", "Mensaje en modo general"))
    estado.cambiar_modo("mentor")
    estado.agregar_mensaje_chat(_mensaje("user", "Mensaje en modo mentor"))
    estado.cambiar_modo("general")

    mentor_antes = list(estado._contextos_por_modo["mentor"])
    general_antes = estado.obtener_contexto_copia()

    contador_antes = estado.mensajes_desde_ultima_extraccion
    rm.resolver_olvidar("vida:salud")

    assert estado._contextos_por_modo["mentor"] == mentor_antes
    assert estado.obtener_contexto_copia() == general_antes
    # El olvido NO toca el contador de mensajes pendientes de perfil
    # (lo reinician SOLO reemplazar_contexto_chat y cambiar_modo).
    assert estado.mensajes_desde_ultima_extraccion == contador_antes


# ─── 6. Tombstone sigue determinista ────────────────────────────────────────

def test_registro_de_tombstone_sigue_determinista(olvidos_tmp):
    assert olvidos.registrar_olvido("vida:salud") is True
    assert olvidos.esta_olvidado("vida:salud") is True
    assert olvidos.esta_olvidado("vida:otra") is False
    assert olvidos.quitar_olvido("vida:salud") is True
    assert olvidos.esta_olvidado("vida:salud") is False


# ─── 7. La memoria olvidada no reaparece por recuperación semántica ─────────

def test_olvidada_no_reaparece_por_recuperacion_semantica(olvidos_tmp, memoria_fake):
    olvidos.registrar_olvido(_ID_BOVEDA)
    memoria_fake.configurar_detalle([
        _recuerdo("Recuerdo olvidado", 0.47, origen_id=_ID_BOVEDA),
        _recuerdo("Recuerdo vigente", 0.47, origen_id=_ID_BOVEDA_2),
    ])

    memorias = rec.recuperar_memorias("algo")

    assert [m["origen_id"] for m in memorias] == [_ID_BOVEDA_2]
    assert not any(m["origen_id"] == _ID_BOVEDA for m in memorias)


# ─── 8. No se reintroduce mediante el perfil/reescritor ─────────────────────

def test_no_reintroduccion_por_reescritor(olvidos_tmp):
    olvidos.registrar_olvido("vida:salud")
    perfil = _perfil_con_vidas()
    perfil["vida_personal"] = []

    hecho = {
        "tipo": "perfil_vida",
        "clave_o_tema": "salud",
        "valor": "Le duele la rodilla derecha",
        "importancia": 0.9,
    }

    preguntas_antes = len(pu.rutear_hecho(hecho, perfil)["vida_personal"])
    assert preguntas_antes == 0


# ─── 9. Concurrencia básica: olvidar mientras otro flujo usa el contexto ────

def test_concurrencia_olvidar_vs_acceso_al_contexto(olvidos_tmp, memoria_fake):
    estado = _estado_nuevo()
    semilla = [_mensaje("user", f"mensaje semilla {i}") for i in range(4)]
    for m in semilla:
        estado.agregar_mensaje_chat(m)
    total_escritos = 0
    errores = []

    def _olvidar():
        try:
            for _ in range(5):
                # En bóveda, no toca perfiles JSON: evita escritura concurrente
                # sobre el archivo de perfil en este test.
                rm.resolver_olvidar(_ID_BOVEDA)
                olvidos.esta_olvidado(_ID_BOVEDA)
        except Exception as e:  # pragma: no cover - señal de falla
            errores.append(e)

    def _leer():
        try:
            for _ in range(5):
                estado.obtener_contexto_copia()
        except Exception as e:  # pragma: no cover - señal de falla
            errores.append(e)

    def _escribir():
        nonlocal total_escritos
        try:
            for i in range(3):
                estado.agregar_mensaje_chat(_mensaje("user", f"nuevo {i}"))
                total_escritos += 1
        except Exception as e:  # pragma: no cover - señal de falla
            errores.append(e)

    hilos = [
        threading.Thread(target=_olvidar),
        threading.Thread(target=_leer),
        threading.Thread(target=_escribir),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert errores == []
    # Cada intento de olvidar vuelve a invalidar por origen (contrato actual
    # de resolver_olvidar: no es idempotente respecto de la invalidación).
    assert memoria_fake.invalidaciones()
    assert all(i == _ID_BOVEDA for i in memoria_fake.invalidaciones())
    assert olvidos.esta_olvidado(_ID_BOVEDA) is True

    contexto = estado.obtener_contexto_copia()
    assert len(contexto) == len(semilla) + total_escritos
    assert all(isinstance(m.get("parts"), list) for m in contexto)
    assert all(m["role"] in ("user", "model") for m in contexto)
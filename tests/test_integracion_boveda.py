"""
Tests de integración reales de la Bóveda (persistencia + integridad).

=== ENTORNO: ChromaDB VERSUS Python 3.13 / protobuf ===
ChromaDB 1.5.9 + protobuf + opentelemetry-proto NO importan de forma
estándar en Python 3.13 del venv (error de descriptores de protobuf
"cannot be created directly"). La solución actualmente utilizada es
forzar la implementación en modo puro de protobuf ANTES de importar
chromadb:

    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

(NO es un cambio del proyecto: es una variable de entorno del proceso
de test. El entorno de producción `python main_web.py` usa Python 3.11,
donde chromadb 1.5.9 importa sin problemas.)

=== ALCANCE / CONTRATO ACEPTADO PROVISIONALMENTE (Fase 2) ===
Semántica actual de una familia `boveda:*` (NO se usó upsert todavía):
- `origen_id` identifica una FAMILIA LÓGICA determinista:
      boveda:<slug(etiqueta)>:<10 hex de sha256(contenido normalizado)>
- el `uuid4()` identifica el DOCUMENTO FÍSICO dentro de ChromaDB;
- una familia puede contener VARIOS documentos (el re-guardado con
  `add()` crea duplicados físicos: mismo origen_id, ids físicos distintos);
- `invalidar_por_origen()` borra TODA la familia (delete por where).

Estos tests usan ChromaDB REAL (PersistentClient sobre tmp_path) con una
embedding function DETERMINISTA sin modelo (offline, rápida, sin red ni
descarga). El módulo `modulos.memoria` se importa de verdad, solo que el
cliente se redirige a un directorio temporal.

No se incluye: backfill histórico, upsert/dedup, panel "Olvidar esto".
"""

import hashlib
import importlib
import os
import sys
import types

# IMPORTANTE: antes de importar chromadb (ver ENTORNO arriba).
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import numpy as np
import pytest

import chromadb
from chromadb.api.types import EmbeddingFunction

# Nombre de embedding function que queda persistido en la colección.
# ChromaDB valida que coincidan al reabrir; usamos el mismo que el real
# ("sentence_transformer") para que la persistencia no dependa del stub.
_NOMBRE_EF_PERSISTIDO = "sentence_transformer"


class EmbeddingDeterminista(EmbeddingFunction):
    """EF offline: vector determinista por sha256 del texto (sin modelo).

    ChromaDB 1.5 exige name() y __init__; el nombre coincide con el que
    ChromaDB persiste para que la validación al reabrir no falle.
    """

    def __init__(self):
        pass

    @classmethod
    def name(cls):
        return _NOMBRE_EF_PERSISTIDO

    def get_config(self):
        return {"name": self.name()}

    @classmethod
    def build_from_config(cls, config):
        return cls()

    def __call__(self, input):
        import hashlib

        import numpy as np

        vecs = []
        for texto in input:
            h = hashlib.sha256(str(texto).encode("utf-8")).digest()
            v = np.array(list(h), dtype=np.float32) / 255.0
            v = v - v.mean()
            n = np.linalg.norm(v)
            v = v / n if n else v
            vecs.append(v.tolist())
        return vecs


@pytest.fixture
def memoria_real_chromadb(monkeypatch, tmp_path):
    """
    Carga `modulos.memoria` con ChromaDB REAL persistente en tmp_path.

    Solo se sustituyen tres piezas de infraestructura (con monkeypatch,
    restauradas al terminar cada test):
    - config → stub (evita la dependencia de GEMINI_API_KEY);
    - chromadb.PersistentClient → redirige el path a tmp_path;
    - SentenceTransformerEmbeddingFunction → EmbeddingDeterminista.
    """
    sys.modules.pop("modulos.memoria", None)

    fake_config = types.ModuleType("config")
    fake_config.estado = types.SimpleNamespace()
    fake_config.MEMORIA_TOP_K = 3
    monkeypatch.setitem(sys.modules, "config", fake_config)

    # ── chromadb real, cliente redirigido a tmp_path ─────────────────
    cliente_real_chromadb = chromadb.PersistentClient

    def _cliente_redirigido(path=None, **kwargs):
        return cliente_real_chromadb(path=str(tmp_path), **kwargs)

    monkeypatch.setattr(chromadb, "PersistentClient", _cliente_redirigido)

    # ── embedding function determinista sin modelo ────────────────────
    from chromadb.utils import embedding_functions

    monkeypatch.setattr(
        embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        lambda **kwargs: EmbeddingDeterminista(),
    )

    modulo = importlib.import_module("modulos.memoria")
    yield modulo, str(tmp_path)

    # Liberar el cliente y módulo para no interferir con otros tests.
    cliente = getattr(modulo, "cliente", None)
    if cliente is not None and hasattr(cliente, "close"):
        try:
            cliente.close()
        except Exception:
            pass
    sys.modules.pop("modulos.memoria", None)


def _abrir_cliente_reabierto(path):
    """Abre un cliente ChromaDB nuevo sobre el mismo path (simula reanudación)."""
    return chromadb.PersistentClient(path=path)


def _origen_id_de(modulo, etiqueta, contenido):
    """Calcula el origen_id esperado con la lógica real del módulo."""
    return modulo._generar_origen_id_boveda(etiqueta, contenido)


# ─── 1. Generación y persistencia del origen_id ─────────────────────────────

def test_guardar_recuerdo_genera_origen_id_persistente(memoria_real_chromadb):
    modulo, path = memoria_real_chromadb
    etiqueta = "Memoria_IA"
    contenido = "El usuario migró su proyecto a FastAPI"

    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido, etiqueta_tema=etiqueta
    ) is True

    origen_esperado = _origen_id_de(modulo, etiqueta, contenido)
    assert origen_esperado.startswith("boveda:")
    assert len(origen_esperado.split(":")) == 3

    # El documento existe físicamente con ese origen_id.
    coleccion = modulo.coleccion_principal
    fila = coleccion.get(where={"origen_id": origen_esperado})
    assert len(fila["ids"]) == 1
    assert fila["metadatas"][0]["origen_id"] == origen_esperado
    assert fila["metadatas"][0]["etiqueta"] == etiqueta


def test_origen_id_persiste_tras_cerrar_y_reabrir_cliente(memoria_real_chromadb):
    modulo, path = memoria_real_chromadb
    etiqueta = "Extracción automática de perfil"
    contenido = "Dato que debe sobrevivir al cierre y reapertura"

    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido, etiqueta_tema=etiqueta
    ) is True
    origen_esperado = _origen_id_de(modulo, etiqueta, contenido)

    # Cerrar el cliente del módulo (simula fin de proceso).
    modulo.cliente.close()

    # Reabrir con un cliente nuevo sobre el mismo path físico.
    cliente2 = _abrir_cliente_reabierto(path)
    coleccion2 = cliente2.get_or_create_collection(
        "contexto_general", embedding_function=EmbeddingDeterminista()
    )
    fila = coleccion2.get(where={"origen_id": origen_esperado})
    assert len(fila["ids"]) == 1
    assert fila["metadatas"][0]["origen_id"] == origen_esperado
    assert fila["documents"][0] == contenido
    cliente2.close()


# ─── 2. Re-guardado: duplicados dentro de la familia ────────────────────────

def test_re_guardado_misma_familia_duplicados_fisicos(memoria_real_chromadb):
    modulo, path = memoria_real_chromadb
    etiqueta = "Memoria_IA"
    contenido = "El usuario prefiere tipo de letra grande"

    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido, etiqueta_tema=etiqueta
    ) is True
    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido, etiqueta_tema=etiqueta
    ) is True

    origen_esperado = _origen_id_de(modulo, etiqueta, contenido)
    coleccion = modulo.coleccion_principal
    fila = coleccion.get(where={"origen_id": origen_esperado})

    # Comparten origen_id (misma familia lógica)…
    assert len(fila["ids"]) == 2
    assert len(fila["metadatas"]) == 2
    assert all(m["origen_id"] == origen_esperado for m in fila["metadatas"])

    # … pero son documentos físicos distintos (uuid4 diferentes).
    assert len(set(fila["ids"])) == 2
    assert fila["ids"][0] != fila["ids"][1]


def test_contenido_diferente_genera_otra_familia(memoria_real_chromadb):
    modulo, path = memoria_real_chromadb
    etiqueta = "Memoria_IA"
    contenido_a = "Argus se ejecuta en Windows"
    contenido_b = "El usuario trabaja con Electron"

    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido_a, etiqueta_tema=etiqueta
    ) is True
    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido_b, etiqueta_tema=etiqueta
    ) is True

    origen_a = _origen_id_de(modulo, etiqueta, contenido_a)
    origen_b = _origen_id_de(modulo, etiqueta, contenido_b)
    assert origen_a != origen_b

    coleccion = modulo.coleccion_principal
    assert len(coleccion.get(where={"origen_id": origen_a})["ids"]) == 1
    assert len(coleccion.get(where={"origen_id": origen_b})["ids"]) == 1


# ─── 3. invalidar_por_origen: borra la familia completa ─────────────────────

def test_invalidar_por_origen_borra_toda_la_familia(memoria_real_chromadb):
    modulo, path = memoria_real_chromadb
    etiqueta = "Memoria_IA"
    contenido_a = "Recordatorio: configurar backups diarios"
    contenido_b = "Otra familia que debe sobrevivir"

    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido_a, etiqueta_tema=etiqueta
    ) is True
    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido_a, etiqueta_tema=etiqueta
    ) is True
    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido_b, etiqueta_tema=etiqueta
    ) is True

    origen_a = _origen_id_de(modulo, etiqueta, contenido_a)
    origen_b = _origen_id_de(modulo, etiqueta, contenido_b)
    coleccion = modulo.coleccion_principal

    assert len(coleccion.get(where={"origen_id": origen_a})["ids"]) == 2

    exito = modulo.invalidar_por_origen(origen_a)
    assert exito is True

    # La familia completa desaparece (los 2 duplicados)…
    assert len(coleccion.get(where={"origen_id": origen_a})["ids"]) == 0
    # … y la otra familia queda intacta.
    assert len(coleccion.get(where={"origen_id": origen_b})["ids"]) == 1


# ─── 4. invalidar_por_origen con familia inexistente (comportamiento actual) ─

def test_invalidar_familia_inexistente_comportamiento_actual(memoria_real_chromadb):
    """
    Documenta el comportamiento ACTUAL de invalidar_por_origen() ante una
    familia que no existe.

    ChromaDB no lanza excepción cuando el delete(where=...) no encuentra
    coincidencias: responde con éxito vacío. Por eso, en el código actual,
    invalidar_por_origen() devuelve `True` aunque no haya borrado nada.

    Decisión pendiente para Fase 3 (NO implementada aquí):
    - Opción A: mantener True → la operación delete se ejecutó correctamente
      (solo que con 0 coincidencias); simple, sin falso negativo.
    - Opción B: devolver False → informa "no existía esa familia", útil para
      que resolver_olvidar() no registre un tombstone inútil; requiere
      además saber si el delete borró 0 docs (contar antes/después).
    Este test fija el comportamiento vigente (opción A).
    """
    modulo, path = memoria_real_chromadb
    etiqueta = "Memoria_IA"

    assert modulo.guardar_recuerdo(
        texto_a_guardar="Familia que sí existe y debe conservarse",
        etiqueta_tema=etiqueta,
    ) is True

    origen_inexistente = _origen_id_de(
        modulo, etiqueta, "Este contenido jamás se guardó"
    )
    coleccion = modulo.coleccion_principal

    exito = modulo.invalidar_por_origen(origen_inexistente)

    # Comportamiento vigente documentado: True (el delete se "ejecutó bien").
    assert exito is True
    # Y no destruyó nada de la familia real.
    assert len(coleccion.get()["ids"]) == 1


# ─── 5. buscar_contexto_con_detalle (Fase 4) ────────────────────────────────

def test_buscar_contexto_con_detalle_devuelve_metadata(memoria_real_chromadb):
    modulo, path = memoria_real_chromadb
    etiqueta = "Memoria_IA"
    contenido = "El usuario prefiere trabajar de noche"

    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido, etiqueta_tema=etiqueta,
        origen_fuente="memoria_manual",
    ) is True

    detalle = modulo.buscar_contexto_con_detalle(contenido, cantidad_resultados=3)

    assert detalle, "debe recuperar al menos el documento guardado"
    primero = detalle[0]
    for clave in ("documento", "origen_id", "origen_fuente", "etiqueta", "fecha_guardado", "distancia"):
        assert clave in primero, f"falta la clave '{clave}'"
    assert primero["documento"] == contenido
    assert primero["origen_id"].startswith("boveda:")
    assert primero["origen_fuente"] == "memoria_manual"
    assert primero["etiqueta"] == etiqueta
    assert isinstance(primero["distancia"], float)


def test_buscar_contexto_con_detalle_sin_datos_devuelve_vacio(memoria_real_chromadb):
    modulo, path = memoria_real_chromadb
    assert modulo.buscar_contexto_con_detalle("consulta sin datos", cantidad_resultados=3) == []


def _esperar_detalle_anticipado(modulo, consulta, timeout=10.0):
    """Espera (con poll) a que el hilo de prefetch guarde el detalle."""
    import time

    limite = time.time() + timeout
    while time.time() < limite:
        with modulo._anticipado_lock:
            if (
                modulo._anticipado_consulta == consulta
                and modulo._resultado_anticipado_detalle is not None
            ):
                return modulo._resultado_anticipado_detalle
        time.sleep(0.05)
    return None


def test_prefetch_anticipada_guarda_detalle_y_texto(memoria_real_chromadb):
    modulo, path = memoria_real_chromadb
    etiqueta = "Memoria_IA"
    contenido = "El usuario migró el backend a FastAPI"

    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido, etiqueta_tema=etiqueta
    ) is True

    consulta = "backend FastAPI"
    modulo.iniciar_busqueda_anticipada(consulta)

    detalle = _esperar_detalle_anticipado(modulo, consulta)
    assert detalle is not None, "el hilo de prefetch no terminó a tiempo"
    assert any(d["documento"] == contenido for d in detalle)

    with modulo._anticipado_lock:
        texto = modulo._resultado_anticipado
    assert texto is not None
    assert len(texto) == 1
    assert contenido in texto[0]


def test_obtener_resultado_anticipado_detalle_cae_a_busqueda_directa(memoria_real_chromadb):
    modulo, path = memoria_real_chromadb
    etiqueta = "Memoria_IA"
    contenido = "Recuerdo de prueba para el fallback"

    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido, etiqueta_tema=etiqueta
    ) is True

    # Sin prefetch en curso (consulta distinta) → debe caer a la búsqueda directa.
    with modulo._anticipado_lock:
        modulo._anticipado_consulta = "otra consulta"
        modulo._resultado_anticipado_detalle = None

    detalle = modulo.obtener_resultado_anticipado_detalle(contenido)
    assert detalle
    assert any(d["documento"] == contenido for d in detalle)
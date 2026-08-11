# -*- coding: utf-8 -*-
"""
Fase 3C — Validación funcional del ciclo completo de "Olvidar esto".

Usa ChromaDB REAL persistente en tmp_path con embedding function determinista
sin modelo (mismo patrón de infraestructura que test_integracion_boveda.py):
el módulo `modulos.memoria` se importa de verdad, solo que el cliente se
redirige a un directorio temporal. El registro de olvidos (olvidos.json) se
monkeypatchea a tmp_path para NO tocar el archivo real de producción.

Cubre el ciclo end-to-end de una familia `boveda:*`:
  1. guardar_recuerdo() crea un recuerdo con origen_id boveda:*;
  2. se recupera su origen_id determinista;
  3. se confirma su existencia física en ChromaDB;
  4. resolver_olvidar(origen_id) despacha el borrado;
  5. invalidar_por_origen() elimina la familia completa (incl. duplicados);
  6. resolver_olvidar() registra el tombstone en olvidos.json;
  7. una familia distinta NO se ve afectada;
  8. re-llamar resolver_olvidar() sobre el mismo origen_id (comportamiento
     actual documentado);
  9. re-guardar el MISMO contenido después del olvido (comportamiento actual:
     SIN protección contra reaparición — ver test de decisión pendiente).

NO se toca la bóveda real (18 memorias). Tests destructivos solo sobre tmp_path.
"""

import hashlib
import importlib
import os
import sys
import types

# Antes de importar chromadb (ver ENTORNO en test_integracion_boveda.py).
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import numpy as np
import pytest

import chromadb
from chromadb.api.types import EmbeddingFunction

import modulos.olvidos as olvidos
from modulos.resumen_memoria import resolver_olvidar


# ─── Embedding function determinista offline (duplicada del test de integración) ──

_NOMBRE_EF_PERSISTIDO = "sentence_transformer"


class EmbeddingDeterminista(EmbeddingFunction):
    """EF offline: vector determinista por sha256 del texto (sin modelo)."""

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
def entorno_olvido(monkeypatch, tmp_path):
    """
    Carga `modulos.memoria` con ChromaDB REAL en tmp_path + embedding
    determinista, y apunta el registro de olvidos a tmp_path.

    Sustituye (con monkeypatch, restaurado al final de cada test):
    - config → stub (sin GEMINI_API_KEY);
    - chromadb.PersistentClient → redirigido a str(tmp_path / "boveda");
    - SentenceTransformerEmbeddingFunction → EmbeddingDeterminista;
    - modulos.olvidos.RUTA_OLVIDOS → str(tmp_path / "olvidos.json").

    Devuelve (modulo_memoria, ruta_boveda, ruta_olvidos_json).
    """
    sys.modules.pop("modulos.memoria", None)

    fake_config = types.ModuleType("config")
    fake_config.estado = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "config", fake_config)

    cliente_real_chromadb = chromadb.PersistentClient

    def _cliente_redirigido(path=None, **kwargs):
        return cliente_real_chromadb(path=str(tmp_path / "boveda"), **kwargs)

    monkeypatch.setattr(chromadb, "PersistentClient", _cliente_redirigido)

    from chromadb.utils import embedding_functions

    monkeypatch.setattr(
        embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        lambda **kwargs: EmbeddingDeterminista(),
    )

    monkeypatch.setattr(olvidos, "RUTA_OLVIDOS", str(tmp_path / "olvidos.json"))

    modulo = importlib.import_module("modulos.memoria")
    yield modulo, str(tmp_path / "boveda"), str(tmp_path / "olvidos.json")

    cliente = getattr(modulo, "cliente", None)
    if cliente is not None and hasattr(cliente, "close"):
        try:
            cliente.close()
        except Exception:
            pass
    sys.modules.pop("modulos.memoria", None)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _origen_id_de(modulo, etiqueta, contenido):
    """Calcula el origen_id esperado con la lógica real del módulo."""
    return modulo._generar_origen_id_boveda(etiqueta, contenido)


def _familia(coleccion, origen_id):
    """Devuelve la fila completa de una familia (ids/metadatas/documents)."""
    return coleccion.get(where={"origen_id": origen_id})


def _leer_olvidos(ruta):
    """Lee olvidos.json (dict {id: fecha})."""
    contenido = open(ruta, "r", encoding="utf-8").read()
    return __import__("json").loads(contenido)["olvidos"]


# ─── 1-3. Guardar → origen_id → existencia física ─────────────────────────────

def test_ciclo_guardar_origen_id_y_existencia_fisica(entorno_olvido):
    modulo, *_ = entorno_olvido
    etiqueta = "Memoria_IA"
    contenido = "El usuario quiere olvidar este recordatorio de prueba"

    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido, etiqueta_tema=etiqueta
    ) is True

    origen_id = _origen_id_de(modulo, etiqueta, contenido)
    assert origen_id.startswith("boveda:")
    assert len(origen_id.split(":")) == 3

    fila = _familia(modulo.coleccion_principal, origen_id)
    assert len(fila["ids"]) == 1
    assert fila["metadatas"][0]["origen_id"] == origen_id
    assert fila["documents"][0] == contenido


# ─── 4-5. resolver_olvidar elimina la familia completa ───────────────────────

def test_resolver_olvidar_elimina_toda_la_familia(entorno_olvido):
    modulo, *_ = entorno_olvido
    etiqueta = "Memoria_IA"
    contenido = "Recordatorio: borrar backups antiguos"

    # Familia con DOS duplicados físicos (mismo origen_id).
    assert modulo.guardar_recuerdo(texto_a_guardar=contenido, etiqueta_tema=etiqueta) is True
    assert modulo.guardar_recuerdo(texto_a_guardar=contenido, etiqueta_tema=etiqueta) is True

    origen_id = _origen_id_de(modulo, etiqueta, contenido)
    assert len(_familia(modulo.coleccion_principal, origen_id)["ids"]) == 2

    resultado = resolver_olvidar(origen_id)
    assert resultado["exito"] is True

    # La familia completa desapareció (ambos duplicados).
    assert len(_familia(modulo.coleccion_principal, origen_id)["ids"]) == 0


# ─── 6. Tombstone en olvidos.json ────────────────────────────────────────────

def test_resolver_olvidar_registra_tombstone(entorno_olvido, tmp_path):
    modulo, _, ruta_olvidos = entorno_olvido
    etiqueta = "Memoria_IA"
    contenido = "Dato que debe quedar vedado tras olvidarlo"
    origen_id = _origen_id_de(modulo, etiqueta, contenido)

    assert modulo.guardar_recuerdo(texto_a_guardar=contenido, etiqueta_tema=etiqueta) is True
    assert olvidos.esta_olvidado(origen_id) is False

    assert resolver_olvidar(origen_id)["exito"] is True

    # Tombstone registrado en disco (olvidos.json en tmp_path).
    registro = _leer_olvidos(ruta_olvidos)
    assert origen_id in registro
    assert olvidos.esta_olvidado(origen_id) is True


# ─── 7. Otra familia no afectada ─────────────────────────────────────────────

def test_familia_distinta_no_afectada(entorno_olvido):
    modulo, *_ = entorno_olvido
    etiqueta = "Extracción automática de perfil"
    contenido_a = "Olvidar este dato del perfil del proyecto"
    contenido_b = "Otro recuerdo del perfil que debe conservarse"

    origen_a = _origen_id_de(modulo, etiqueta, contenido_a)
    origen_b = _origen_id_de(modulo, etiqueta, contenido_b)
    assert origen_a != origen_b

    assert modulo.guardar_recuerdo(texto_a_guardar=contenido_a, etiqueta_tema=etiqueta) is True
    assert modulo.guardar_recuerdo(texto_a_guardar=contenido_b, etiqueta_tema=etiqueta) is True

    assert resolver_olvidar(origen_a)["exito"] is True

    coleccion = modulo.coleccion_principal
    assert len(_familia(coleccion, origen_a)["ids"]) == 0
    assert len(_familia(coleccion, origen_b)["ids"]) == 1
    assert olvidos.esta_olvidado(origen_a) is True
    assert olvidos.esta_olvidado(origen_b) is False


# ─── 8. Re-llamar resolver_olvidar sobre el mismo origen_id ──────────────────

def test_resolver_olvidar_repetido_mismo_origen_id(entorno_olvido, tmp_path):
    """
    Comportamiento ACTUAL documentado: invalidar_por_origen() devuelve True
    aunque el delete no encuentre coincidencias (familia ya borrada). Por lo
    tanto resolver_olvidar() vuelve a responder "éxito" y re-refresca el
    tombstone (registrar_olvido es idempotente: queda UNA entrada).
    """
    modulo, _, ruta_olvidos = entorno_olvido
    etiqueta = "Memoria_IA"
    contenido = "Convención al olvidar dos veces la misma familia"
    origen_id = _origen_id_de(modulo, etiqueta, contenido)

    assert modulo.guardar_recuerdo(texto_a_guardar=contenido, etiqueta_tema=etiqueta) is True
    assert resolver_olvidar(origen_id)["exito"] is True
    assert len(_familia(modulo.coleccion_principal, origen_id)["ids"]) == 0

    # Segunda llamada sobre el MISMO origen_id ya inexistente.
    segundo = resolver_olvidar(origen_id)

    # Comportamiento vigente: responde éxito (no lanza error, no borra nada).
    assert segundo["exito"] is True
    assert len(_familia(modulo.coleccion_principal, origen_id)["ids"]) == 0
    # Tombstone: una sola entrada, sigue olvidado.
    assert len(_leer_olvidos(ruta_olvidos)) == 1
    assert origen_id in _leer_olvidos(ruta_olvidos)
    assert olvidos.esta_olvidado(origen_id) is True


# ─── 9. Re-guardar el mismo contenido tras el olvido (DECISIÓN PENDIENTE) ────

def test_re_guardado_mismo_contenido_tras_olvido_reaparece(entorno_olvido, tmp_path):
    """
    DECISIÓN PENDIENTE (Fase 3C): guardar_recuerdo() NO consulta el registro
    de olvidos ni valida tombstones. Por lo tanto, re-guardar EXACTAMENTE el
    mismo contenido después de olvidarlo RE-CREA la familia en ChromaDB con el
    MISMO origen_id determinista, a pesar de que el tombstone siga activo.

    Este test fija el comportamiento ACTUAL (sin protección contra
    reaparición). La protección NO se implementó: es el hallazgo a decidir.
    """
    modulo, _, ruta_olvidos = entorno_olvido
    etiqueta = "Memoria_IA"
    contenido = "Este recuerdo reaparece si se vuelve a guardar"

    assert modulo.guardar_recuerdo(texto_a_guardar=contenido, etiqueta_tema=etiqueta) is True
    origen_id = _origen_id_de(modulo, etiqueta, contenido)
    assert len(_familia(modulo.coleccion_principal, origen_id)["ids"]) == 1

    assert resolver_olvidar(origen_id)["exito"] is True
    assert len(_familia(modulo.coleccion_principal, origen_id)["ids"]) == 0
    assert olvidos.esta_olvidado(origen_id) is True

    # Re-guardado idéntico DESPUÉS del olvido.
    assert modulo.guardar_recuerdo(texto_a_guardar=contenido, etiqueta_tema=etiqueta) is True

    fila = _familia(modulo.coleccion_principal, origen_id)
    # La familia REAPARECIÓ con el mismo origen_id (hallazgo).
    assert len(fila["ids"]) == 1
    assert fila["metadatas"][0]["origen_id"] == origen_id
    # El tombstone sigue activo: la reaparición no lo respeta.
    assert olvidos.esta_olvidado(origen_id) is True
    assert origen_id in _leer_olvidos(ruta_olvidos)


# ─── 10. Sección "Memoria" del panel (bóveda en preparar_secciones) ───────────

def test_panel_memoria_lista_y_olvida_recuerdo_boveda(entorno_olvido):
    """
    End-to-end del panel: guardar_recuerdo() → preparar_secciones() muestra
    la sección 'memoria' con el recuerdo (no_editable=True y id = origen_id)
    → resolver_olvidar() lo elimina → la sección deja de mostrarlo.
    """
    from modulos import resumen_memoria as rm

    modulo, *_ = entorno_olvido
    etiqueta = "Memoria_IA"
    contenido = "Recuerdo visible en el panel de memoria"

    assert modulo.guardar_recuerdo(texto_a_guardar=contenido, etiqueta_tema=etiqueta) is True
    origen_id = _origen_id_de(modulo, etiqueta, contenido)

    secciones = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    assert "memoria" in secciones
    ids_boveda = [e["id"] for e in secciones["memoria"]]
    assert origen_id in ids_boveda

    item = next(e for e in secciones["memoria"] if e["id"] == origen_id)
    assert item["no_editable"] is True
    assert item["texto"] == contenido

    # Olvidar desde el panel (mismo flujo que pyApi.olvidar_memoria).
    assert rm.resolver_olvidar(origen_id)["exito"] is True

    secciones_tras = {s["id"]: s["elementos"] for s in rm.preparar_secciones()["secciones"]}
    assert "memoria" not in secciones_tras or origen_id not in [
        e["id"] for e in secciones_tras["memoria"]
    ]
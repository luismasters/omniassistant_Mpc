"""
Tests del backfill de la bóveda (Fase 3B).

Usa ChromaDB REAL sobre tmp_path con una embedding function determinista sin
modelo (mismo patrón que test_integracion_boveda.py). El módulo
`modulos.backfill_boveda` se importa de verdad; sus imports pesados
(modulos.memoria / chromadb) son perezosos, así que aquí se le inyecta la
colección real creada por el fixture.

Cobertura exigida (las 11 reglas):
  - origen_id consistente con guardar_recuerdo()
  - idempotencia
  - solo migración de documentos sin origen_id
  - origen_fuente correcto
  - formato del origen_id
  - ambiguos excluidos y reportados
  - contenido idéntico / misma familia
  - preservación de estado y claves originales
  - dry-run sin escrituras
  - backup ANTES de la migración
  - backup omitido si no hay documentos migrables
"""

import hashlib
import importlib
import os
import re
import sys
import types

os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import numpy as np
import pytest

import chromadb
from chromadb.api.types import EmbeddingFunction

import modulos.backfill_boveda as bb

_NOMBRE_EF_PERSISTIDO = "sentence_transformer"


class EmbeddingDeterminista(EmbeddingFunction):
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
def memoria_real_chromadb(monkeypatch, tmp_path):
    sys.modules.pop("modulos.memoria", None)

    fake_config = types.ModuleType("config")
    fake_config.estado = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "config", fake_config)

    cliente_real_chromadb = chromadb.PersistentClient

    def _cliente_redirigido(path=None, **kwargs):
        return cliente_real_chromadb(path=str(tmp_path / "vault"), **kwargs)

    monkeypatch.setattr(chromadb, "PersistentClient", _cliente_redirigido)

    from chromadb.utils import embedding_functions

    monkeypatch.setattr(
        embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        lambda **kwargs: EmbeddingDeterminista(),
    )

    modulo = importlib.import_module("modulos.memoria")
    yield modulo, str(tmp_path)

    cliente = getattr(modulo, "cliente", None)
    if cliente is not None and hasattr(cliente, "close"):
        try:
            cliente.close()
        except Exception:
            pass
    sys.modules.pop("modulos.memoria", None)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _agregar_legacy(coleccion, contenido, etiqueta=None, id_="legacy-1", extra=None):
    """Inserta un documento legacy (SIN contrato origen_id) como se guardaba antes."""
    meta = {"fecha_guardado": "2024-01-01 10:00:00"}
    if etiqueta is not None:
        meta["etiqueta"] = etiqueta
    if extra:
        meta.update(extra)
    coleccion.add(documents=[contenido], metadatas=[meta], ids=[id_])
    return id_


def _meta_de(coleccion, id_):
    fila = coleccion.get(ids=[id_], include=["documents", "metadatas"])
    return (fila["documents"][0], fila["metadatas"][0])


def _bytes_marcador_en(prefijo, texto):
    """Devuelve la lista de archivos bajo `prefijo` que CONTIENEN `texto`."""
    hits = []
    for raiz, _, archs in os.walk(prefijo):
        for a in archs:
            r = os.path.join(raiz, a)
            with open(r, "rb") as f:
                if texto.encode("utf-8") in f.read():
                    hits.append(os.path.relpath(r, prefijo))
    return hits


# ─── fixture conjunto tmp_path + colección real ──────────────────────────────

@pytest.fixture
def escenario(memoria_real_chromadb, tmp_path):
    """(modulo, ruta_boveda, coleccion, dir_backups)."""
    modulo, ruta = memoria_real_chromadb
    ruta_boveda = str(tmp_path / "vault")
    return modulo, ruta_boveda, modulo.coleccion_principal, str(tmp_path / "backups")


# ─── 1. origen_id consistente con guardar_recuerdo() ─────────────────────────

def test_origen_id_consistente_con_guardar_recuerdo(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    contenido = "El usuario migró su proyecto a FastAPI"
    etiqueta = "Extracción automática de perfil"
    _agregar_legacy(coleccion, contenido, etiqueta=etiqueta, id_="legacy-consistente")

    res = bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)

    assert res["migrables"] == 1
    id_backfill = res["actualizados"][0]["origen_id"]

    # El id de la migración es idéntico al que genera guardar_recuerdo()
    # (que usa la misma función canónica _generar_origen_id_boveda).
    assert id_backfill == modulo._generar_origen_id_boveda(etiqueta, contenido)

    # Y coincide también con el que produce un guardado NUEVO real.
    assert modulo.guardar_recuerdo(
        texto_a_guardar=contenido, etiqueta_tema=etiqueta
    ) is True
    fila = coleccion.get(include=["metadatas"])
    id_guardado_nuevo = fila["metadatas"][-1]["origen_id"]
    assert id_guardado_nuevo == id_backfill


# ─── 2. Idempotencia ──────────────────────────────────────────────────────────

def test_idempotencia_segunda_pasada_sin_migrables(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    _agregar_legacy(coleccion, "Contenido A", etiqueta="Memoria_IA", id_="a")

    primera = bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)
    assert primera["migrables"] == 1

    segunda = bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)
    assert segunda["migrables"] == 0
    assert segunda["actualizados"] == []
    assert segunda["backup"] is None  # no volvió a crear backup


# ─── 3. Solo migra documentos SIN origen_id ──────────────────────────────────

def test_solo_migra_sin_origen_id(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    _agregar_legacy(coleccion, "Legacy a migrar", etiqueta="Memoria_IA", id_="legacy")
    _agregar_legacy(
        coleccion, "Ya migrado", etiqueta="Memoria_IA", id_="ya",
        extra={"origen_id": "boveda:memoria_ia:488f6c7c78"},
    )

    res = bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)

    ids_actualizados = {a["id"] for a in res["actualizados"]}
    assert ids_actualizados == {"legacy"}
    assert res["ya_migrados"] == 1

    # El documento ya migrado conserva su origen_id original.
    doc, meta = _meta_de(coleccion, "ya")
    assert meta["origen_id"] == "boveda:memoria_ia:488f6c7c78"
    assert meta.get("origen_fuente") is None  # no se pisó


# ─── 4. origen_fuente correcto ────────────────────────────────────────────────

def test_origen_fuente_perfil_proyecto(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    _agregar_legacy(coleccion, "Hecho de proyecto", etiqueta="Extracción automática de perfil", id_="p")

    bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)

    _, meta = _meta_de(coleccion, "p")
    assert meta["origen_fuente"] == "perfil_proyecto"


# ─── 5. Formato del origen_id ────────────────────────────────────────────────

def test_formato_origen_id(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    _agregar_legacy(coleccion, "Dato sobre el proyecto", etiqueta="Extracción automática de perfil", id_="f")

    res = bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)
    origen = res["actualizados"][0]["origen_id"]

    partes = origen.split(":")
    assert len(partes) == 3
    assert partes[0] == "boveda"
    # Slug tal como lo genera el contrato real (_slug_etiqueta de memoria.py):
    # [^a-zA-Z0-9]+ se reemplaza por "_", así que las tildes desaparecen.
    assert partes[1] == "extracci_n_autom_tica_de_perfil"
    assert len(partes[2]) == 10
    int(partes[2], 16)  # debe ser hex válido
    assert bool(re.fullmatch(r"boveda:[a-z0-9_]+:[0-9a-f]{10}", origen))


# ─── 6. Ambiguos excluidos y reportados ──────────────────────────────────────

def test_ambiguos_excluidos_y_reportados(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    # Sin etiqueta → ambiguo (no migrable).
    _agregar_legacy(coleccion, "No tiene etiqueta", etiqueta=None, id_="sin-etiqueta")

    audit = bb.auditar_boveda(ruta_boveda=ruta, coleccion=coleccion)
    assert audit["ambiguos"] == 1
    assert audit["migrables"] == 0

    res = bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)
    assert res["migrables"] == 0
    assert res["actualizados"] == []

    # Sigue sin origen_id tras la "ejecución".
    _, meta = _meta_de(coleccion, "sin-etiqueta")
    assert "origen_id" not in meta


# ─── 7. Contenido idéntico → misma familia ───────────────────────────────────

def test_contenido_identico_misma_familia(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    contenido = "El usuario trabaja con Streamlit Cloud"
    _agregar_legacy(coleccion, contenido, etiqueta="Extracción automática de perfil", id_="f1")
    _agregar_legacy(coleccion, contenido, etiqueta="Extracción automática de perfil", id_="f2")

    res = bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)

    assert len(res["actualizados"]) == 2
    origen_f1 = res["actualizados"][0]["origen_id"]
    origen_f2 = res["actualizados"][1]["origen_id"]
    assert origen_f1 == origen_f2  # misma familia lógica

    # El documento físico no se tocó.
    doc1, _ = _meta_de(coleccion, "f1")
    doc2, _ = _meta_de(coleccion, "f2")
    assert doc1 == contenido
    assert doc2 == contenido


# ─── 8. Preservación de estado y claves originales ───────────────────────────

def test_preserva_metadatos_y_contenido_original(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    contenido = "Preservar todo menos lo agregado"
    _agregar_legacy(
        coleccion, contenido, etiqueta="Memoria_IA", id_="preservar",
        extra={"canal": "extraccion", "custom_key": 42},
    )

    bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)

    doc, meta = _meta_de(coleccion, "preservar")
    assert doc == contenido
    assert meta["etiqueta"] == "Memoria_IA"
    assert meta["fecha_guardado"] == "2024-01-01 10:00:00"
    assert meta["canal"] == "extraccion"
    assert meta["custom_key"] == 42
    assert meta["origen_id"].startswith("boveda:")
    assert meta["origen_fuente"] == "perfil_proyecto"
    # No se inventaron claves fuera del contrato.
    assert set(meta.keys()) == {
        "fecha_guardado", "etiqueta", "canal", "custom_key", "origen_id", "origen_fuente",
    }


# ─── 9. Dry-run sin escrituras ───────────────────────────────────────────────

def test_dry_run_sin_escrituras(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    _agregar_legacy(coleccion, "No debe migrarse aún", etiqueta="Memoria_IA", id_="dry")

    audit = bb.auditar_boveda(ruta_boveda=ruta, coleccion=coleccion)
    assert audit["migrables"] == 1
    assert audit["ya_migrados"] == 0

    # El documento conserva su estado original (sin origen_id ni origen_fuente).
    _, meta = _meta_de(coleccion, "dry")
    assert "origen_id" not in meta
    assert "origen_fuente" not in meta


# ─── 10. Backup ANTES de la migración ────────────────────────────────────────

def test_backup_antes_de_migracion(escenario, monkeypatch):
    modulo, ruta, coleccion, bk_dir = escenario
    _agregar_legacy(coleccion, "Contenido a respaldar", etiqueta="Memoria_IA", id_="bk")

    # Marcador ÚNICO (ausente de todo el código fuente): la verificación física
    # no usa "perfil_proyecto" porque ese texto también vive en el docstring de
    # guardar_recuerdo (memoria.py) y ChromaDB lo persiste en el data_level0.bin
    # de cualquier índice → falsos positivos por carrera con el flush del .bin.
    marcador = "fuente_backfill_" + hashlib.sha256(os.urandom(8)).hexdigest()[:12]
    monkeypatch.setattr(bb, "ORIGEN_FUENTE_BACKFILL", marcador)

    res = bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)

    backup = res["backup"]
    assert backup is not None
    assert os.path.isdir(backup)
    assert os.path.isfile(os.path.join(backup, "chroma.sqlite3"))

    # El backup contiene la bóveda completa: sqlite + el directorio de segmento.
    contenido_backup = os.listdir(backup)
    assert "chroma.sqlite3" in contenido_backup
    segmentos = [e for e in contenido_backup if not e.endswith(".sqlite3")]
    assert len(segmentos) >= 1

    # Verificación FÍSICA pre-migración: el backup (snapshot tomado ANTES de
    # escribir) no debe contener el marcador run-time de la migración.
    # (ChromaDB cachea la colección por nombre en el mismo proceso; por eso la
    # verificación se hace sobre los bytes del backup y no re-abriendo el cliente.)
    assert _bytes_marcador_en(backup, marcador) == []

    # Y el marcador SÍ está en la bóveda de origen (post-migración).
    assert _bytes_marcador_en(ruta, marcador) != []


# ─── 11. Backup omitido si no hay documentos migrables ───────────────────────

def test_backup_omitido_sin_migrables(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    _agregar_legacy(
        coleccion, "Ya migrado", etiqueta="Memoria_IA", id_="y",
        extra={"origen_id": "boveda:memoria_ia:488f6c7c78"},
    )

    res = bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)

    assert res["migrables"] == 0
    assert res["backup"] is None
    # No se creó el directorio de backups.
    assert not os.path.exists(bk_dir)


# ─── Garantía: guardar_recuerdo / invalidar_por_origen intactos ──────────────

def test_guardar_recuerdo_e_invalidar_intactos(escenario):
    modulo, ruta, coleccion, bk_dir = escenario
    _agregar_legacy(coleccion, "Recuerdo migrado", etiqueta="Memoria_IA", id_="m")
    bb.ejecutar_backfill(ruta_boveda=ruta, destino_backups=bk_dir, coleccion=coleccion)

    _, meta = _meta_de(coleccion, "m")
    origen = meta["origen_id"]

    # invalidar_por_origen() borra la familia completa migrada.
    assert modulo.invalidar_por_origen(origen) is True
    fila = coleccion.get(where={"origen_id": origen})
    assert fila["ids"] == []

    # guardar_recuerdo() sigue funcionando tras la migración.
    assert modulo.guardar_recuerdo(
        texto_a_guardar="Post-migración", etiqueta_tema="Memoria_IA"
    ) is True
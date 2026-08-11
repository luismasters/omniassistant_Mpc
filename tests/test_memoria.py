"""
Tests de blindaje de la capa de memoria (ChromaDB).

Cubren `modulos.memoria.guardar_recuerdo` e `invalidar_por_origen` SIN
ChromaDB real ni modelos de embeddings: se inyecta un `coleccion_principal`
falso en `sys.modules` para que el import del módulo jamás descargue el
SentenceTransformer ni abra una bóveda persistente.

Además hay un test de contrato que fija explícitamente el estado actual:
ningún flujo de escritura a ChromaDB establece `origen_id`. Si en el futuro
alguien agrega `origen_id=` a una llamada, este test falla a propósito como
recordatorio de que esa decisión debe pasar por diseño de contrato.

Offline y rápido: no hay API keys, ni red, ni ChromaDB real.
"""

import ast
import importlib
import os
import sys
import types

import pytest


# ─── Fake de la colección ChromaDB ────────────────────────────────────────────

class _ColeccionFalsa:
    """Reemplaza `coleccion_principal` grabando las llamadas, sin persistir nada."""

    def __init__(self):
        self.llamadas_add = []
        self.llamadas_delete = []

    def add(self, documents=None, metadatas=None, ids=None):
        self.llamadas_add.append({
            "documents": documents,
            "metadatas": metadatas,
            "ids": ids,
        })

    def delete(self, where=None):
        self.llamadas_delete.append({"where": where})


def _id_recuerdo_de_add(llamada) -> str:
    """Devuelve el id generado por guardar_recuerdo en esa llamada add."""
    ids = llamada.get("ids") or []
    return ids[0]


# ─── Fixture: importa el módulo REAL con ChromaDB falso ──────────────────────

@pytest.fixture
def memoria_modulo(monkeypatch):
    """
    Carga `modulos.memoria` con stubs en sys.modules para chromadb,
    embedding_functions y config. Devuelve (módulo, colección_falsa).
    El watchdog real está instalado en el venv y se importa sin problema;
    ninguna función del radar se ejecuta en estos tests.
    """
    sys.modules.pop("modulos.memoria", None)

    coleccion_falsa = _ColeccionFalsa()

    # --- chromadb falso: PersistentClient devuelve la colección falsa ---
    fake_chromadb = types.ModuleType("chromadb")

    class _ClienteFalso:
        def __init__(self, path):
            self.path = path

        def get_or_create_collection(self, name, embedding_function=None):
            return coleccion_falsa

    fake_chromadb.PersistentClient = _ClienteFalso

    utils = types.ModuleType("chromadb.utils")
    embedding_functions = types.ModuleType("chromadb.utils.embedding_functions")
    embedding_functions.SentenceTransformerEmbeddingFunction = lambda **k: "modelo-stub"
    utils.embedding_functions = embedding_functions
    fake_chromadb.utils = utils

    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)
    monkeypatch.setitem(sys.modules, "chromadb.utils", utils)
    monkeypatch.setitem(sys.modules, "chromadb.utils.embedding_functions", embedding_functions)

    # --- config falso (evita la dependencia de GEMINI_API_KEY) ---
    fake_config = types.ModuleType("config")
    fake_config.estado = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "config", fake_config)

    modulo = importlib.import_module("modulos.memoria")
    yield modulo, coleccion_falsa

    sys.modules.pop("modulos.memoria", None)


# ─── guardar_recuerdo ─────────────────────────────────────────────────────────

def test_guardar_recuerdo_guarda_etiqueta_y_fecha(memoria_modulo):
    modulo, coleccion = memoria_modulo
    exito = modulo.guardar_recuerdo(
        texto_a_guardar="El usuario está migrando a FastAPI",
        etiqueta_tema="Memoria_IA",
    )
    assert exito is True
    assert len(coleccion.llamadas_add) == 1

    llamada = coleccion.llamadas_add[0]
    assert llamada["documents"] == ["El usuario está migrando a FastAPI"]
    assert len(_id_recuerdo_de_add(llamada)) > 0  # uuid4 generado por el módulo

    meta = llamada["metadatas"][0]
    assert meta["etiqueta"] == "Memoria_IA"
    assert "fecha_guardado" in meta
    assert meta["fecha_guardado"]

    # Contrato boveda:*: origen_id se genera siempre (aunque no se pase).
    assert meta["origen_id"].startswith("boveda:")
    assert meta["origen_id"] == "boveda:memoria_ia:488f6c7c78"
    # Sin origen_fuente: no se debe inventar.
    assert "origen_fuente" not in meta


def test_guardar_recuerdo_con_origen_id_y_fuente_en_metadatas(memoria_modulo):
    modulo, coleccion = memoria_modulo
    exito = modulo.guardar_recuerdo(
        texto_a_guardar="Hecho de proyecto",
        etiqueta_tema="Extracción automática de perfil",
        origen_id="proyecto:ejemplo",
        origen_fuente="perfil_proyecto",
    )
    assert exito is True

    meta = coleccion.llamadas_add[0]["metadatas"][0]
    assert meta["origen_id"] == "proyecto:ejemplo"
    assert meta["origen_fuente"] == "perfil_proyecto"
    assert meta["etiqueta"] == "Extracción automática de perfil"
    assert "fecha_guardado" in meta


def test_guardar_recuerdo_metadatos_extra_acumulan_sin_pisar_origen(memoria_modulo):
    """Los metadatos_extra se suman y no reemplazan origen_id/origen_fuente."""
    modulo, coleccion = memoria_modulo
    exito = modulo.guardar_recuerdo(
        texto_a_guardar="dato",
        etiqueta_tema="Memoria_MCP",
        origen_id="vida:salud",
        metadatos_extra={"canal": "mcp"},
    )
    assert exito is True
    meta = coleccion.llamadas_add[0]["metadatas"][0]
    assert meta["origen_id"] == "vida:salud"
    assert meta["canal"] == "mcp"
    assert meta["etiqueta"] == "Memoria_MCP"


# ─── invalidar_por_origen ─────────────────────────────────────────────────────

def test_invalidar_por_origen_borra_con_where_correcto(memoria_modulo):
    modulo, coleccion = memoria_modulo
    exito = modulo.invalidar_por_origen("vida:salud")
    assert exito is True
    assert len(coleccion.llamadas_delete) == 1
    assert coleccion.llamadas_delete[0]["where"] == {"origen_id": "vida:salud"}


def test_invalidar_por_origen_none_no_borra(memoria_modulo):
    modulo, coleccion = memoria_modulo
    exito = modulo.invalidar_por_origen(None)
    assert exito is False
    assert coleccion.llamadas_delete == []


def test_invalidar_por_origen_vacio_no_borra(memoria_modulo):
    modulo, coleccion = memoria_modulo
    exito = modulo.invalidar_por_origen("")
    assert exito is False
    assert coleccion.llamadas_delete == []


# ─── Contrato: ningún flujo actual establece origen_id ────────────────────────

# Archivos con llamadas a guardar_recuerdo() (escrituras reales a ChromaDB).
# main_gui.py está deprecado pero sigue teniendo una escritura; se audita igual.
ARCHIVOS_CON_GUARDADO = [
    "modulos/ia.py",
    "modulos/perfil_usuario.py",
    "modulos/servidor_sistema_mcp.py",
    "main_gui.py",
]


def test_contrato_ningun_flujo_establece_origen_id():
    """
    Fija el contrato actual de la memoria: ninguna escritura a ChromaDB
    establece `origen_id`, porque todavía no existe un mapeo inequívoco
    con los id canónicos del panel (funcional:/vida:/mentor:/gamer:).

    Si este test falla es porque alguien agregó `origen_id=` a un guardado
    sin pasar por diseño de contrato. La asociación ChromaDB→tombstones
    es una decisión de fase posterior y NO debe introducirse por ahora.
    """
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ofensores = []

    for rel in ARCHIVOS_CON_GUARDADO:
        ruta = os.path.join(raiz, *rel.split("/"))
        with open(ruta, "r", encoding="utf-8") as f:
            arbol = ast.parse(f.read(), filename=rel)

        for nodo in ast.walk(arbol):
            if not (isinstance(nodo, ast.Call)
                    and isinstance(nodo.func, ast.Name)
                    and nodo.func.id == "guardar_recuerdo"):
                continue
            # origen_id es el 4º parámetro posicional: un tercer argumento
            # posicional (índice 3) también lo setearía.
            if len(nodo.args) > 3:
                ofensores.append(f"{rel}:{nodo.lineno} (argumento posicional)")
            for kw in nodo.keywords or []:
                if kw.arg == "origen_id":
                    ofensores.append(f"{rel}:{nodo.lineno} (origen_id keyword)")

    assert ofensores == [], (
        "Se violaría el contrato de memoria (origen_id sin diseño previo): "
        + "; ".join(ofensores)
    )


# ─── Contrato boveda:*: determinismo y formato del origen_id ─────────────────

def test_boveda_mismo_contenido_mismo_origen_id(memoria_modulo):
    modulo, coleccion = memoria_modulo
    modulo.guardar_recuerdo(texto_a_guardar="El usuario migra a FastAPI", etiqueta_tema="Memoria_IA")
    primer_id = coleccion.llamadas_add[0]["metadatas"][0]["origen_id"]

    modulo.guardar_recuerdo(texto_a_guardar="El usuario migra a FastAPI", etiqueta_tema="Memoria_IA")
    segundo_id = coleccion.llamadas_add[1]["metadatas"][0]["origen_id"]

    assert primer_id == segundo_id


def test_boveda_whitespace_no_cambia_origen_id(memoria_modulo):
    modulo, coleccion = memoria_modulo
    modulo.guardar_recuerdo(texto_a_guardar="  El usuario    migra a   FastAPI ", etiqueta_tema="Memoria_IA")
    primer_id = coleccion.llamadas_add[0]["metadatas"][0]["origen_id"]

    # Mismo contenido con saltos de línea / tabs → misma normalización.
    modulo.guardar_recuerdo(texto_a_guardar="El usuario\n\tmigra\na\nFastAPI", etiqueta_tema="Memoria_IA")
    segundo_id = coleccion.llamadas_add[1]["metadatas"][0]["origen_id"]

    assert primer_id == segundo_id


def test_boveda_contenido_diferente_origen_id_diferente(memoria_modulo):
    modulo, coleccion = memoria_modulo
    modulo.guardar_recuerdo(texto_a_guardar="El usuario migra a FastAPI", etiqueta_tema="Memoria_IA")
    primer_id = coleccion.llamadas_add[0]["metadatas"][0]["origen_id"]

    # Cambio mínimo de contenido → hash diferente.
    modulo.guardar_recuerdo(texto_a_guardar="El usuario migra a FastAPI.", etiqueta_tema="Memoria_IA")
    segundo_id = coleccion.llamadas_add[1]["metadatas"][0]["origen_id"]

    assert primer_id != segundo_id


def test_boveda_etiqueta_diferente_origen_id_diferente(memoria_modulo):
    modulo, coleccion = memoria_modulo
    modulo.guardar_recuerdo(texto_a_guardar="mismo contenido", etiqueta_tema="Memoria_IA")
    primer_id = coleccion.llamadas_add[0]["metadatas"][0]["origen_id"]

    modulo.guardar_recuerdo(texto_a_guardar="mismo contenido", etiqueta_tema="Memoria_MCP")
    segundo_id = coleccion.llamadas_add[1]["metadatas"][0]["origen_id"]

    assert primer_id != segundo_id


def test_boveda_formato_correcto(memoria_modulo):
    """Formato boveda:<slug(etiqueta)>:<10hex sha256>."""
    modulo, coleccion = memoria_modulo
    modulo.guardar_recuerdo(texto_a_guardar="dato", etiqueta_tema="Memoria_IA")
    origen_id = coleccion.llamadas_add[0]["metadatas"][0]["origen_id"]

    partes = origen_id.split(":")
    assert len(partes) == 3
    assert partes[0] == "boveda"
    assert partes[1] == "memoria_ia"          # slug de la etiqueta
    assert len(partes[2]) == 10               # 10 hex de sha256
    int(partes[2], 16)                        # debe ser hex válido


def test_boveda_origen_id_explicito_se_respeta(memoria_modulo):
    modulo, coleccion = memoria_modulo
    exito = modulo.guardar_recuerdo(
        texto_a_guardar="dato",
        etiqueta_tema="Memoria_IA",
        origen_id="vida:salud",
    )
    assert exito is True
    meta = coleccion.llamadas_add[0]["metadatas"][0]
    assert meta["origen_id"] == "vida:salud"  # NO se reemplaza con boveda:*
    assert not meta["origen_id"].startswith("boveda:")


def test_boveda_origen_fuente_llega_a_chromadb(memoria_modulo):
    modulo, coleccion = memoria_modulo
    modulo.guardar_recuerdo(
        texto_a_guardar="dato",
        etiqueta_tema="Memoria_IA",
        origen_fuente="pedido_explicito",
    )
    meta = coleccion.llamadas_add[0]["metadatas"][0]
    assert meta["origen_fuente"] == "pedido_explicito"
    assert meta["origen_id"].startswith("boveda:")


def test_boveda_genera_origen_fuente_vacia_no_se_inventa(memoria_modulo):
    """Sin origen_fuente, no se agrega la clave a metadatas."""
    modulo, coleccion = memoria_modulo
    modulo.guardar_recuerdo(texto_a_guardar="dato", etiqueta_tema="Memoria_IA")
    meta = coleccion.llamadas_add[0]["metadatas"][0]
    assert "origen_fuente" not in meta


# ─── Integración: resolver_olvidar boveda:* → invalidar_por_origen ───────────

class _MemoriaStub:
    """Fake de modulos.memoria que registra las llamadas a invalidar_por_origen."""

    def __init__(self):
        self.invalidados = []

    def invalidar_por_origen(self, origen_id):
        self.invalidados.append(origen_id)
        return True


@pytest.fixture
def memoria_stub(monkeypatch, tmp_path, olvidos_tmp):
    """Inyecta una memoveria stub + rutas temporales de olvidos."""
    stub = _MemoriaStub()
    sys.modules["modulos.memoria"] = stub
    yield stub
    sys.modules.pop("modulos.memoria", None)


@pytest.fixture
def olvidos_tmp(tmp_path, monkeypatch):
    from modulos import olvidos
    monkeypatch.setattr(olvidos, "RUTA_OLVIDOS", str(tmp_path / "olvidos.json"))
    return tmp_path


def test_resolver_olvidar_boveda_invoca_invalidar_por_origen(memoria_stub):
    from modulos import resumen_memoria as rm

    id_boveda = "boveda:memoria_ia:488f6c7c78"
    resultado = rm.resolver_olvidar(id_boveda)

    assert resultado["exito"] is True
    assert memoria_stub.invalidados == [id_boveda]


def test_resolver_olvidar_boveda_registra_tombstone(memoria_stub):
    from modulos import olvidos
    from modulos import resumen_memoria as rm

    id_boveda = "boveda:memoria_ia:488f6c7c78"
    rm.resolver_olvidar(id_boveda)

    assert olvidos.esta_olvidado(id_boveda) is True


def test_resolver_olvidar_boveda_malformado_no_invoca_delete(memoria_stub):
    from modulos import resumen_memoria as rm

    resultado = rm.resolver_olvidar("boveda:idsueltos")  # sin :slug etiqueta ni hash

    assert resultado["exito"] is False
    assert memoria_stub.invalidados == []


def test_resolver_editar_boveda_no_soportado(memoria_stub):
    from modulos import resumen_memoria as rm

    resultado = rm.resolver_editar("boveda:memoria_ia:488f6c7c78", "nuevo texto")

    assert resultado["exito"] is False
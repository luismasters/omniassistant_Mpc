"""
Registro persistente de olvidos ("tombstones") de Argus.

Guarda la lista de IDs lógicos que el usuario eliminó desde el panel de
memoria, de forma thread-safe y durable en disco (olvidos.json en la raíz
del proyecto).

Reglas del contrato:
- Cada entrada es el ID CANÓNICO EXACTO del panel (p.ej. "vida:salud",
  "mentor:stack_backend", "gamer:grim_dawn"). No hay fuzzy matching.
- La comparación es por igualdad de string determinista. El candidato que
  produce la extracción/consolidación se normaliza con el MISMO slug que
  genera resumen_memoria (ver _slug_estable en cada perfil), y se compara
  por igualdad.
- Este módulo NO importa perfiles ni resumen_memoria (evita ciclos). Valida
  el prefijo del ID contra los prefijos conocidos del panel.

API:
- registrar_olvido(id) -> bool
- quitar_olvido(id) -> bool
- esta_olvidado(id) -> bool
- obtener_ids_olvidados(prefijo=None) -> set[str]

Este módulo NO importa config, pywebview ni ChromaDB, por lo que es seguro
importarlo y testeable fuera de línea.
"""

import json
import os
import re
import threading
import datetime

from modulos.logger import logger


# Ruta al archivo de olvidos (raíz del proyecto)
RUTA_OLVIDOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "olvidos.json")

# Prefijos válidos de id lógico del panel (deben coincidir con
# resumen_memoria.RESOLVER_OLVIDAR / RESOLVER_EDITAR).
PREFIJOS_VALIDOS = ("funcional:", "vida:", "mentor:", "gamer:", "boveda:")

# Patrón del id de memoria libre de ChromaDB (contrato boveda:*).
# boveda:<slug(etiqueta)>:<10 hex de sha256>  — ej: boveda:memoria_ia:a1b2c3d4e5
_PATRON_BOVEDA = re.compile(r"^boveda:[a-zA-Z0-9_]+:[0-9a-f]{10}$")

# Lock thread-safe (RLock: varias funciones anidadas re-adquieren el mismo lock)
_lock_olvidos = threading.RLock()


# ─── HELPERS INTERNOS ────────────────────────────────────────────────────────

def _normalizar_id(id_elemento) -> str:
    """Devuelve el id como string recortado ("" si es vacío/no-string)."""
    if id_elemento is None:
        return ""
    return str(id_elemento).strip()


def _id_valido(id_: str) -> bool:
    """Un id olvidable debe tener un prefijo conocido del panel.

    Los ids de memoria libre (`boveda:`) además deben cumplir el formato
    exacto `boveda:<slug>:<10hex>`; un id boveda malformado se rechaza para
    que nunca derive en un delete por where con un origen_id inválido.
    """
    if not id_:
        return False
    if not id_.startswith(PREFIJOS_VALIDOS):
        return False
    if id_.startswith("boveda:"):
        return _id_boveda_valido(id_)
    return True


def _id_boveda_valido(id_: str) -> bool:
    """Un id de memoria libre de ChromaDB debe tener el formato exacto
    `boveda:<slug>:<10hex>`. Evita que un id malformado pueda terminar
    ejecutando un delete peligroso en invalidar_por_origen()."""
    return bool(_PATRON_BOVEDA.match(id_))


def leer_registro() -> dict:
    """
    Devuelve {id: fecha} con todos los olvidos guardados. Thread-safe.
    Si el archivo no existe, está corrupto o no tiene la estructura
    esperada, devuelve un registro vacío.
    """
    with _lock_olvidos:
        if not os.path.exists(RUTA_OLVIDOS):
            return {}
        try:
            with open(RUTA_OLVIDOS, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("olvidos"), dict):
                return data["olvidos"]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Error leyendo olvidos.json: {e}. Registro vacío.")
        return {}


def _escribir_registro(registro: dict) -> None:
    """Escribe el registro completo. NO es thread-safe — llamar con _lock_olvidos."""
    try:
        with open(RUTA_OLVIDOS, "w", encoding="utf-8") as f:
            json.dump({"olvidos": registro}, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.exception(f"Error escribiendo olvidos.json: {e}")


# ─── API PÚBLICA ─────────────────────────────────────────────────────────────

def registrar_olvido(id_elemento) -> bool:
    """
    Registra un id como olvidado (lo agrega al registro o lo refresca si ya
    existía). Devuelve True si el id es válido y quedó registrado; False si
    no tiene un prefijo conocido.
    """
    id_ = _normalizar_id(id_elemento)
    if not _id_valido(id_):
        return False
    hoy = datetime.date.today().strftime("%Y-%m-%d")
    with _lock_olvidos:
        registro = leer_registro()
        registro[id_] = hoy
        _escribir_registro(registro)
        return True


def quitar_olvido(id_elemento) -> bool:
    """
    Elimina un id del registro de olvidos (se usa al editar el dato, que
    vuelve a quedar permitido). Devuelve True si existía y se quitó; False
    si no estaba o el id no es válido.
    """
    id_ = _normalizar_id(id_elemento)
    if not _id_valido(id_):
        return False
    with _lock_olvidos:
        registro = leer_registro()
        if id_ not in registro:
            return False
        del registro[id_]
        _escribir_registro(registro)
        return True


def esta_olvidado(id_elemento) -> bool:
    """Devuelve True si el id está registrado como olvidado."""
    id_ = _normalizar_id(id_elemento)
    if not _id_valido(id_):
        return False
    with _lock_olvidos:
        registro = leer_registro()
    return id_ in registro


def obtener_ids_olvidados(prefijo=None) -> set:
    """
    Devuelve el conjunto de ids olvidados (opcionalmente filtrado por un
    prefijo como "vida:"). Es la API que usan los filtros de extracción y
    consolidación para saber qué datos NO deben reintroducir.
    """
    with _lock_olvidos:
        registro = leer_registro()
    ids = set(registro.keys())
    if prefijo:
        prefijo = str(prefijo or "")
        return {i for i in ids if i.startswith(prefijo)}
    return ids
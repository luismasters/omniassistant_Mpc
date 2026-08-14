"""
Backfill de la bóveda (Fase 3B): carga `origen_id` / `origen_fuente` sobre los
documentos legacy de ChromaDB guardados ANTES del contrato `boveda:*`.

CONTRATO BASE (no se inventa nada nuevo, se reutiliza lo existente):
- El `origen_id` canónico es el que ya genera `modulos.memoria._generar_origen_id_boveda`
  (la MISMA función que usa `guardar_recuerdo()`): `boveda:<slug(etiqueta)>:<10hex sha256>`.
  Así, migrar un legacy produce el mismo id que re-guardarlo con `guardar_recuerdo()`.
- Se respeta `guardar_recuerdo()` e `invalidar_por_origen()` de memoria.py SIN
  modificarlos: el backfill opera con `Collection.update()` sobre los ids originales
  (conserva documento, embedding e id físico), solo agregando metadatos.

REGLAS DE SEGURIDAD:
- NO hace nada al importar. Solo funciona vía función o CLI.
- Modo por defecto: `--dry-run` (audita y planifica, sin escribir nada).
- `--ejecutar`: crea ANTES un backup completo de la bóveda y solo escribe si hay
  documentos migrables.
- Idempotente: cualquier documento que YA tenga `origen_id` se salta.
- Migrable inequívoco: documento sin `origen_id`, con `etiqueta` y contenido no
  vacíos. Cualquier otro caso se clasifica como AMBIGUO y se excluye/reporta.
- Conserva los metadatos originales (solo agrega `origen_id` y `origen_fuente`).
"""

import argparse
import datetime
import json
import os
import shutil

# El venv (Python 3.13) no puede importar chromadb con los descriptores de
# protobuf por defecto (ver tests/test_integracion_boveda.py). ChromaDB se
# importa de forma perezosa, así que forzar la implementación pura ANTES de
# cualquier import es seguro. No afecta a main_web.py (Python 3.11).
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

NOMBRE_COLECCION = "contexto_general"
ORIGEN_FUENTE_BACKFILL = "perfil_proyecto"


# ─── Infraestructura ─────────────────────────────────────────────────────────

def _ruta_por_defecto_boveda():
    """Ruta real de la bóveda: <repo>/modulos/boveda_memoria/."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(raiz, "modulos", "boveda_memoria")


def _ruta_por_defecto_backups():
    """Ruta por defecto de los backups: <repo>/backups/."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(raiz, "backups")


def _abrir_coleccion(ruta_boveda=None):
    """
    Abre la colección 'contexto_general' a auditar/migrar.
    - Con ruta: cliente propio sobre esa ruta (útil para tests y auditorías).
    - Sin ruta: usa `modulos.memoria.coleccion_principal` (la bóveda REAL).
    """
    if ruta_boveda:
        import chromadb
        from chromadb.utils import embedding_functions

        cliente = chromadb.PersistentClient(path=ruta_boveda)
        return cliente.get_or_create_collection(
            NOMBRE_COLECCION,
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            ),
        )
    from modulos.memoria import coleccion_principal

    return coleccion_principal


def _generar_origen_id_canonico(etiqueta, contenido):
    """Reutiliza la generación canónica de guardar_recuerdo()."""
    from modulos.memoria import _generar_origen_id_boveda

    return _generar_origen_id_boveda(etiqueta, contenido)


def _leer_documentos(coleccion):
    fila = coleccion.get(include=["documents", "metadatas"])
    return (
        fila.get("ids") or [],
        fila.get("documents") or [],
        fila.get("metadatas") or [],
    )


# ─── Clasificación ───────────────────────────────────────────────────────────

def clasificar_documentos(coleccion):
    """
    Clasifica cada documento de la bóveda según su estado de migración.
    Devuelve un dict con listas 'migrados', 'migrables', 'ambiguos' (y 'errores').
    No escribe nada.
    """
    ids, docs, metas = _leer_documentos(coleccion)
    resumen = {
        "total": len(ids),
        "migrados": [],
        "migrables": [],
        "ambiguos": [],
        "errores": [],
    }

    for i, id_ in enumerate(ids):
        documento = docs[i] if i < len(docs) else ""
        meta = (metas[i] if i < len(metas) else {}) or {}
        origen_actual = meta.get("origen_id")

        if origen_actual:
            resumen["migrados"].append({
                "id": id_,
                "origen_id": origen_actual,
            })
            continue

        etiqueta = (meta.get("etiqueta") or "").strip()
        contenido = (documento or "").strip()
        if not etiqueta or not contenido:
            resumen["ambiguos"].append({
                "id": id_,
                "motivo": "sin etiqueta o sin contenido",
                "etiqueta": etiqueta,
                "contenido": contenido[:80],
            })
            continue

        resumen["migrables"].append({
            "id": id_,
            "documento": documento,
            "etiqueta": etiqueta,
            "metadatos_originales": meta,
            "origen_id": _generar_origen_id_canonico(etiqueta, contenido),
        })

    return resumen


def auditar_boveda(ruta_boveda=None, coleccion=None):
    """
    Auditoría sin efectos: conteos y familias, listo para informe.
    Uso normal (producción): sin ruta → bóveda real.
    """
    coleccion = coleccion or _abrir_coleccion(ruta_boveda)
    resumen = clasificar_documentos(coleccion)

    familias = {}
    for m in resumen["migrables"]:
        familias.setdefault(m["origen_id"], []).append(m["id"])

    return {
        "documentos_encontrados": resumen["total"],
        "migrables": len(resumen["migrables"]),
        "ya_migrados": len(resumen["migrados"]),
        "ambiguos": len(resumen["ambiguos"]),
        "errores": len(resumen["errores"]),
        "detalle_ambiguos": resumen["ambiguos"],
        "detalle_ya_migrados": resumen["migrados"],
        "origen_id_unicos": len(familias),
        "familias_con_multiples_documentos": {
            k: v for k, v in familias.items() if len(v) > 1
        },
    }


# ─── Backup ──────────────────────────────────────────────────────────────────

def _copiar_boveda(origen, destino):
    """Copia el contenido de `origen` a `destino`, salteando el propio
    destino si (por error de configuración) estuviera anidado dentro."""
    os.makedirs(destino, exist_ok=True)
    for entrada in os.listdir(origen):
        ruta_origen = os.path.join(origen, entrada)
        if os.path.abspath(ruta_origen) == os.path.abspath(destino):
            continue
        ruta_destino = os.path.join(destino, entrada)
        if os.path.isdir(ruta_origen):
            shutil.copytree(ruta_origen, ruta_destino)
        else:
            shutil.copy2(ruta_origen, ruta_destino)


def crear_backup(ruta_boveda=None, destino_backups=None):
    """
    Copia completa del directorio de la bóveda a
    <destino_backups>/boveda_memoria_<YYYYMMDD_HHMMSS>. Devuelve la ruta.
    """
    origen = ruta_boveda or _ruta_por_defecto_boveda()
    destino_base = destino_backups or _ruta_por_defecto_backups()
    marca = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(destino_base, f"boveda_memoria_{marca}")

    if not os.path.isdir(origen):
        raise FileNotFoundError(f"No existe la bóveda en: {origen}")

    if os.path.exists(destino):
        raise FileExistsError(f"El backup ya existe (no se sobrescribe): {destino}")

    os.makedirs(destino_base, exist_ok=True)
    _copiar_boveda(origen, destino)
    return destino


# ─── Migración ───────────────────────────────────────────────────────────────

def ejecutar_backfill(ruta_boveda=None, destino_backups=None, coleccion=None):
    """
    Migración REAL (con escritura). Idempotente y con backup previo.

    - Si no hay documentos migrables devuelve el auditoría sin escrituras y
      con backup=None.
    - Crea UN backup completo ANTES de la primera escritura.
    - Actualiza solo metadatos (id y contenido se conservan).
    """
    coleccion = coleccion or _abrir_coleccion(ruta_boveda)
    resumen = clasificar_documentos(coleccion)
    migrables = resumen["migrables"]

    if not migrables:
        return {
            "documentos_encontrados": resumen["total"],
            "migrables": 0,
            "ya_migrados": len(resumen["migrados"]),
            "ambiguos": len(resumen["ambiguos"]),
            "errores": len(resumen["errores"]),
            "backup": None,
            "actualizados": [],
        }

    backup = crear_backup(ruta_boveda, destino_backups)

    actualizados = []
    for m in migrables:
        meta_nueva = dict(m["metadatos_originales"])
        meta_nueva["origen_id"] = m["origen_id"]
        meta_nueva["origen_fuente"] = ORIGEN_FUENTE_BACKFILL
        coleccion.update(ids=[m["id"]], metadatas=[meta_nueva])
        actualizados.append({
            "id": m["id"],
            "origen_id": m["origen_id"],
            "etiqueta": m["etiqueta"],
        })

    return {
        "documentos_encontrados": resumen["total"],
        "migrables": len(migrables),
        "ya_migrados": len(resumen["migrados"]),
        "ambiguos": len(resumen["ambiguos"]),
        "errores": len(resumen["errores"]),
        "detalle_ambiguos": resumen["ambiguos"],
        "backup": backup,
        "actualizados": actualizados,
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="backfill_boveda",
        description="Backfill de la bóveda (Fase 3B). Dry-run por defecto.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Solo auditar/planificar, sin escribir (predeterminado).",
    )
    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Escribir: crea backup previo y migra los documentos migrables.",
    )
    parser.add_argument("--ruta-boveda", default=None, help="Ruta de la bóveda (por defecto: la real).")
    parser.add_argument("--destino-backups", default=None, help="Carpeta de backups (por defecto: <repo>/backups).")
    args = parser.parse_args(argv)

    if args.ejecutar:
        resultado = ejecutar_backfill(args.ruta_boveda, args.destino_backups)
    else:
        resultado = auditar_boveda(args.ruta_boveda)

    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
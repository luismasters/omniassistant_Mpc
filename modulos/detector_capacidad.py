# -*- coding: utf-8 -*-
"""
Detección de capacidad por embeddings (Fase D, Punto 3 — refinamiento).

Flujo conservador ANTIFALSOS POSITIVOS:
  1. El fast-path de palabras clave (`modulos.prompts.detectar_capacidad_por_tema`)
     resuelve las señales explícitas (determinista, cero costo).
  2. Solo si las keywords NO detectan señal, este módulo refina por similitud
     semántica contra prototipos de mentoría/gaming.
  3. Activa SOLO si la mejor similitud supera el umbral Y le saca un margen
     claro a la otra capacidad (mensaje ambiguo → None → general).

Umbrales calibrados con datos reales (offline, 14/08/2026):
  - Paráfrasis cercana de mentoría/gaming: 0.60–1.00
  - Mensajes neutrales (hora, clima, chistes, comandos): máx observado ~0.57
  - Umbral 0.62 + margen 0.05 deja a los neutrales SIN activar.

El modelo vive en la bóveda (`modulos.memoria.modelo_traductor`); acá se
importa LAZY para que los tests offline no carguen el modelo.
"""
import config
from modulos.logger import logger

_PROTOTIPOS_MENTORIA = (
    "quiero aprender a programar",
    "ayudame a preparar mi entrevista tecnica",
    "como armo mi stack tecnologico",
    "dame un roadmap para mi carrera profesional",
    "quiero practicar para conseguir trabajo",
)

_PROTOTIPOS_GAMING = (
    "que build le conviene a mi personaje",
    "estoy jugando una partida competitiva",
    "como mejoro mi sensibilidad en el juego",
    "dame consejos para ganar en este juego",
)

_UMBRAL_CAPACIDAD_EMBEDDINGS = 0.62
_MARGEN_CAPACIDAD_EMBEDDINGS = 0.05

_prototipos_cache = None  # (emb_mentor, emb_gamer) calculados una sola vez


def _coseno(a, b):
    """Similitud coseno entre dos vectores del mismo largo."""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def _decidir_capacidad_por_scores(mentor, gamer):
    """
    Lógica pura de decisión (testeable offline): activa una capacidad solo si
    supera el umbral Y le saca al menos un margen a la otra capacidad.
    """
    if mentor >= _UMBRAL_CAPACIDAD_EMBEDDINGS and (mentor - gamer) >= _MARGEN_CAPACIDAD_EMBEDDINGS:
        return "mentor"
    if gamer >= _UMBRAL_CAPACIDAD_EMBEDDINGS and (gamer - mentor) >= _MARGEN_CAPACIDAD_EMBEDDINGS:
        return "gamer"
    return None


def _obtener_prototipos_emb(modelo):
    """Embeddings de los prototipos, calculados una sola vez por proceso."""
    global _prototipos_cache
    if _prototipos_cache is None:
        # chromadb 1.5.9 expone embed_query(lista) → lista de vectores.
        embs = modelo.embed_query(list(_PROTOTIPOS_MENTORIA) + list(_PROTOTIPOS_GAMING))
        n = len(_PROTOTIPOS_MENTORIA)
        _prototipos_cache = (embs[:n], embs[n:])
    return _prototipos_cache


def detectar_capacidad_por_embeddings(texto):
    """
    Refinamiento por embeddings: devuelve "mentor" | "gamer" | None.
    Nunca lanza: ante cualquier problema degrada a None (igual que keywords
    sin señal). Respeta el kill-switch config.ACTIVACION_CAPACIDAD_EMBEDDINGS.
    """
    if not texto or not str(texto).strip():
        return None
    if not config.ACTIVACION_CAPACIDAD_EMBEDDINGS:
        return None
    try:
        from modulos.memoria import modelo_traductor, _cache_get, _cache_set
        clave_cache = f"capacidad:{str(texto).strip().lower()}"
        cacheado = _cache_get(clave_cache)
        if cacheado is not None:
            return cacheado or None
        emb_mentor, emb_gamer = _obtener_prototipos_emb(modelo_traductor)
        vec_msg = modelo_traductor.embed_query([str(texto).strip()])[0]
        mentor = max(_coseno(vec_msg, v) for v in emb_mentor)
        gamer = max(_coseno(vec_msg, v) for v in emb_gamer)
        decision = _decidir_capacidad_por_scores(mentor, gamer)
        _cache_set(clave_cache, decision or "")
        return decision
    except Exception as e:
        logger.debug(f"Activación por embeddings no disponible: {e}")
        return None
import logging
import os

from modulos.logger import _RotatingFileHandlerRobusto


def _logger_con_handler(tmp_path, nombre, handler):
    lg = logging.getLogger(f"tests_rotacion_{nombre}")
    lg.handlers.clear()
    lg.propagate = False
    lg.setLevel(logging.DEBUG)
    lg.addHandler(handler)
    return lg


def test_rotacion_crea_backups(tmp_path):
    log = tmp_path / "rot.log"
    handler = _RotatingFileHandlerRobusto(str(log), maxBytes=1024, backupCount=2, encoding="utf-8")
    lg = _logger_con_handler(tmp_path, "backups", handler)
    for i in range(300):
        lg.info("linea %d " + "x" * 80, i)
    handler.close()

    archivos = sorted(p.name for p in tmp_path.glob("rot.log*"))
    assert "rot.log" in archivos
    # rot.log + rot.log.1 + rot.log.2
    assert len(archivos) == 3


def test_rotacion_tolera_archivo_bloqueado(tmp_path, monkeypatch):
    """Windows no puede renombrar un archivo abierto por otro proceso; el
    handler no debe romperse ni lanzar errores cuando eso ocurre."""
    log = tmp_path / "locked.log"

    def fake_rename(src, dst):
        raise PermissionError(32, "archivo bloqueado por otro proceso")

    monkeypatch.setattr(os, "rename", fake_rename)

    handler = _RotatingFileHandlerRobusto(str(log), maxBytes=1024, backupCount=2, encoding="utf-8")
    lg = _logger_con_handler(tmp_path, "locked", handler)

    for i in range(50):
        lg.info("linea %d " + "x" * 40, i)  # no debe lanzar excepción

    assert os.path.exists(log)
    handler.close()
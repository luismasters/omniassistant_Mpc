import os

import modulos.sistema as sistema


def test_mapear_monitor_identidad():
    assert sistema._mapear_monitor(1) == 1
    assert sistema._mapear_monitor(2) == 2
    assert sistema._mapear_monitor(99) == 99


def test_obtener_ruta_dinamica_existente(tmp_path):
    f = tmp_path / "x.txt"
    f.touch()
    inexistente = tmp_path / "y.txt"
    assert sistema.obtener_ruta_dinamica([str(f), str(inexistente)]) == str(f)


def test_obtener_ruta_dinamica_fallback():
    opciones = [r"C:\no\existe\a", r"C:\no\existe\b"]
    assert sistema.obtener_ruta_dinamica(opciones) == opciones[0]


def test_explorar_directorio_ruta_inexistente(tmp_path):
    resultado = sistema.explorar_directorio(str(tmp_path / "carpeta_inexistente"))
    assert "no existe" in resultado


def test_explorar_directorio_lista_contenido(tmp_path):
    (tmp_path / "a.txt").touch()
    (tmp_path / "b.txt").touch()
    (tmp_path / "sub").mkdir()
    resultado = sistema.explorar_directorio(str(tmp_path))
    assert "Carpetas (1)" in resultado
    assert "Archivos (2)" in resultado
    assert "a.txt" in resultado
    assert "b.txt" in resultado
    assert "sub" in resultado


def test_explorar_directorio_limpieza_sufijos(tmp_path):
    (tmp_path / "hola.txt").touch()
    resultado = sistema.explorar_directorio(f"{tmp_path}@ 2||url:https://ejemplo.com")
    assert "hola.txt" in resultado


def test_ejecutar_navegar_sitio_comun(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        sistema, "_abrir_url_en_navegador",
        lambda url, mon=None, nav=None: llamadas.append((url, mon, nav)) or "ok",
    )
    sistema.ejecutar_comando_sistema("navegar: youtube")
    assert llamadas == [("https://www.youtube.com", None, "brave")]


def test_ejecutar_navegar_url_explicita(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        sistema, "_abrir_url_en_navegador",
        lambda url, mon=None, nav=None: llamadas.append((url, mon, nav)) or "ok",
    )
    sistema.ejecutar_comando_sistema("navegar: https://github.com/luismasters")
    assert llamadas[0][0] == "https://github.com/luismasters"


def test_ejecutar_abrir_programa(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        sistema, "_abrir_programa_o_carpeta",
        lambda obj, mon=None, nav=None: llamadas.append(obj) or "ok",
    )
    sistema.ejecutar_comando_sistema("abrir: notepad")
    assert llamadas == ["notepad"]


def test_ejecutar_abrir_url(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        sistema, "_abrir_url_en_navegador",
        lambda url, mon=None, nav=None: llamadas.append(url) or "ok",
    )
    sistema.ejecutar_comando_sistema("abrir: www.youtube.com")
    assert llamadas == ["www.youtube.com"]


def test_ejecutar_cerrar(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        sistema, "_cerrar_programa",
        lambda objetivo: llamadas.append(objetivo) or "ok",
    )
    sistema.ejecutar_comando_sistema("cerrar: notepad")
    assert llamadas == ["notepad"]


def test_ejecutar_mover_sin_monitor():
    resultado = sistema.ejecutar_comando_sistema("mover: brave")
    assert "Especifica un monitor" in resultado


def test_ejecutar_mover_con_monitor(monkeypatch):
    registros = []

    class FakeThread:
        daemon = True

        def __init__(self, target, args=(), kwargs=None, daemon=None):
            self.target = target
            self.args = args
            self.kwargs = kwargs or {}

        def start(self):
            self.target(*self.args, **self.kwargs)

    monkeypatch.setattr(sistema.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        sistema, "forzar_ventana_a_monitor",
        lambda nombre, mon: registros.append((nombre, mon)),
    )
    resultado = sistema.ejecutar_comando_sistema("mover: brave @ 2")
    assert registros == [("brave", 2)]
    assert "monitor 2" in resultado.lower()


def test_ejecutar_comando_desconocido():
    resultado = sistema.ejecutar_comando_sistema("hacer: algo")
    assert resultado.startswith("Comando no ejecutable")


def test_abrir_url_normaliza_y_llama_popen(monkeypatch):
    pops = []
    monkeypatch.setattr(sistema.subprocess, "Popen", lambda *a, **k: pops.append(a) or None)
    resultado = sistema._abrir_url_en_navegador("youtube")
    assert pops, "Popen no fue llamado"
    assert "https://www.youtube.com" in pops[0][0]
    assert "Abriendo" in resultado


def test_abrir_url_con_url_parcial(monkeypatch):
    pops = []
    monkeypatch.setattr(sistema.subprocess, "Popen", lambda *a, **k: pops.append(a) or None)
    sistema._abrir_url_en_navegador("midominio.com")
    assert "https://midominio.com" in pops[0][0]


def test_cerrar_programa_nombre_corto_abortado():
    resultado = sistema._cerrar_programa("ab")
    assert "demasiado corto" in resultado


def test_cerrar_programa_steam(monkeypatch):
    llamadas = []
    monkeypatch.setattr(sistema.os, "system", lambda c: llamadas.append(c))
    resultado = sistema._cerrar_programa("steam")
    assert llamadas == ["start steam://exit"]
    assert "Steam" in resultado


def test_cerrar_programa_por_ventana(monkeypatch):
    asesinados = []

    class FakeProc:
        def __init__(self, pid):
            self.pid = pid

        def kill(self):
            asesinados.append(self.pid)

    monkeypatch.setattr(
        sistema.win32gui, "EnumWindows",
        lambda cb, *a: cb(999, None) or True,
    )
    monkeypatch.setattr(sistema.win32gui, "IsWindowVisible", lambda hwnd: True)
    monkeypatch.setattr(sistema.win32gui, "GetWindowText", lambda hwnd: "Notepad - app")
    monkeypatch.setattr(
        sistema.win32process, "GetWindowThreadProcessId",
        lambda hwnd: (7, 99),
    )
    monkeypatch.setattr(sistema.psutil, "Process", lambda pid: FakeProc(pid))
    monkeypatch.setattr(sistema.os, "system", lambda c: None)

    resultado = sistema._cerrar_programa("notepad")
    assert asesinados == [99]
    assert "protocolo de cierre" in resultado


def test_cerrar_programa_por_proceso(monkeypatch):
    class FakeProc:
        def __init__(self, name, pid):
            self.info = {"name": name, "pid": pid}

        def kill(self):
            self.killed = True

    fake = FakeProc("notepad.exe", 123)

    def fake_iter(attrs=None):
        return iter([fake])

    monkeypatch.setattr(sistema.win32gui, "EnumWindows", lambda cb, *a: None)
    monkeypatch.setattr(sistema.psutil, "process_iter", fake_iter)
    monkeypatch.setattr(sistema.os, "system", lambda c: None)

    sistema._cerrar_programa("notepad")
    assert getattr(fake, "killed", False) is True


def test_cerrar_programa_dinamico_mata_proceso(monkeypatch):
    class FakeProc:
        def __init__(self, name, pid):
            self.info = {"pid": pid, "name": name}

        def kill(self):
            self.killed = True

    fake = FakeProc("notepad.exe", 123)

    def fake_iter(attrs=None):
        return iter([fake])

    monkeypatch.setattr(sistema.psutil, "process_iter", fake_iter)
    assert sistema.cerrar_programa_dinamico("notepad") is True
    assert getattr(fake, "killed", False) is True


def test_cerrar_programa_dinamico_sin_match(monkeypatch):
    class FakeProc:
        def __init__(self, name, pid):
            self.info = {"pid": pid, "name": name}

        def kill(self):
            self.killed = True

    fake = FakeProc("chrome.exe", 1)

    def fake_iter(attrs=None):
        return iter([fake])

    monkeypatch.setattr(sistema.psutil, "process_iter", fake_iter)
    assert sistema.cerrar_programa_dinamico("notepad") is False
    assert not hasattr(fake, "killed")


def test_radar_inteligente_con_match(monkeypatch, tmp_path):
    def fake_walk(ruta):
        yield (str(tmp_path), [], ["Discord.lnk"])

    monkeypatch.setattr(sistema.os, "walk", fake_walk)
    monkeypatch.setattr(sistema.os.path, "exists", lambda p: True)
    monkeypatch.setattr(sistema.process, "extractOne", lambda *a, **k: ("Discord", 90))

    ruta = sistema.radar_inteligente("Discord")
    assert ruta == os.path.join(str(tmp_path), "Discord.lnk")


def test_radar_inteligente_sin_match(monkeypatch, tmp_path):
    def fake_walk(ruta):
        yield (str(tmp_path), [], ["Discord.lnk"])

    monkeypatch.setattr(sistema.os, "walk", fake_walk)
    monkeypatch.setattr(sistema.os.path, "exists", lambda p: True)
    monkeypatch.setattr(sistema.process, "extractOne", lambda *a, **k: ("Discord", 30))

    assert sistema.radar_inteligente("Discord") is None

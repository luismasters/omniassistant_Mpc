# OmniAssistant 🤖

OmniAssistant es un asistente de escritorio interactivo y autónomo potenciado por Inteligencia Artificial (Google Gemini). Diseñado para funcionar como un "Pair Programmer" y un administrador del sistema operativo, combina interacción por voz y texto con capacidades avanzadas de lectura de código, visión por computadora y gestión de memoria híbrida (RAG).

## 🌟 Características Principales (Estado Actual)

### 1. Interfaz y Experiencia de Usuario (UI/UX)
* **GUI Minimalista:** Ventana flotante en modo oscuro con transparencias y esquema de colores pasteles (Tkinter).
* **Interacción Híbrida:** Soporte para comandos de voz (motor Whisper con tecla rápida) y chat de texto.
* **Telemetría en Vivo:** Monitoreo en segundo plano del hardware con alertas visuales y de voz para sobrecalentamiento de GPU (VRAM) o saturación de RAM.

### 2. Control del Sistema Operativo (Radar Inteligente)
* **Ejecución Local:** Capacidad para abrir/cerrar programas, juegos, documentos y navegar por internet.
* **Radar Dinámico:** Motor de búsqueda inteligente que prioriza ejecutables y accesos directos, omitiendo automáticamente carpetas de desarrollo (`venv`, `node_modules`, `.git`) para evitar falsos positivos.
* **Soporte Multimonitor:** Detección de ventanas activas y capacidad para mover o maximizar aplicaciones entre distintos monitores mediante comandos.

### 3. Cerebro RAG y Gestión de Datos (Memoria Híbrida)
* **Ingesta Masiva de Archivos:** Interfaz para adjuntar múltiples archivos simultáneamente (Código fuente, PDFs, TXT).
* **Memoria Volátil (Pair Programming):** Capacidad para inyectar archivos enteros en el contexto temporal de la IA, ideal para debatir código, buscar bugs o refactorizar sin ensuciar la base de datos.
* **Memoria Permanente (Bóveda):** Sistema de *Chunking* que divide documentos grandes y los indexa en una base de datos vectorial (ChromaDB) usando Metadata, permitiendo consultas rápidas a largo plazo con bajo consumo de tokens.

### 4. Visión y Herramientas DevOps
* **Visión Artificial:** Captura de pantalla a demanda para proveer contexto visual a la IA sobre errores, interfaces o estructura de archivos.
* **Git Automático:** Módulo integrado para realizar rutinas de sincronización (`add`, `commit`, `push`) directamente desde el chat de voz hacia repositorios de GitHub.

---

## 🏗️ Estructura del Proyecto

El sistema está modularizado para garantizar escalabilidad y fácil mantenimiento:

```text
OmniAssistant/
├── main.py               # Interfaz gráfica (Tkinter) y controlador principal
├── config.py             # Variables de entorno y configuraciones globales
├── servidor_sistema_mcp.py # Integración MCP para gestión de herramientas
├── gestor_boveda.py      # Gestión de memoria y base de datos local
├── prueba_mcp.py         # Validaciones de procesos MCP
└── modulos/              # Módulos especializados
    ├── ia.py             # Lógica de Gemini, System Prompt y flujos RAG híbridos
    ├── sistema.py        # Interacción con el SO y monitoreo de hardware
    ├── audio.py          # Captura de micrófono (Whisper) y síntesis de voz (TTS)
    ├── vision.py         # Captura de pantalla
    ├── archivos.py       # Manipulación de archivos
    ├── busqueda.py       # Búsqueda web
    ├── git_bot.py        # Control de versiones
    └── memoria.py        # Motor vectorial (ChromaDB)
```


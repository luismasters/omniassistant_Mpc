import os
import re
from typing import Optional, Dict, List
from modulos.logger import logger

class GestorSkills:
    """Gestor de Skills de Argus"""
    
    def __init__(self):
        self.ruta_base = os.path.dirname(os.path.abspath(__file__))
        self.skills: Dict[str, Dict] = {}
        self._cargar_todas_las_skills()
    
    def _cargar_todas_las_skills(self):
        for item in os.listdir(self.ruta_base):
            ruta_skill = os.path.join(self.ruta_base, item)
            if os.path.isdir(ruta_skill) and not item.startswith('_'):
                self._cargar_skill(item, ruta_skill)
        logger.info(f"✅ Skills cargadas: {', '.join(self.skills.keys()) if self.skills else 'ninguna'}")
    
    def _cargar_skill(self, nombre: str, ruta: str):
        try:
            skill_data = {}
            ruta_skill_md = os.path.join(ruta, "SKILL.md")
            if os.path.exists(ruta_skill_md):
                with open(ruta_skill_md, 'r', encoding='utf-8') as f:
                    skill_data['metadatos'] = f.read()
            
            ruta_instructions = os.path.join(ruta, "instructions.md")
            if os.path.exists(ruta_instructions):
                with open(ruta_instructions, 'r', encoding='utf-8') as f:
                    skill_data['instrucciones'] = f.read()
            else:
                logger.warning(f"⚠️ Skill '{nombre}' no tiene instructions.md")
                return
            
            ruta_ejemplos = os.path.join(ruta, "ejemplos.md")
            if os.path.exists(ruta_ejemplos):
                with open(ruta_ejemplos, 'r', encoding='utf-8') as f:
                    skill_data['ejemplos'] = f.read()
            
            self.skills[nombre] = skill_data
            logger.debug(f"✅ Skill cargada: {nombre}")
        except Exception as e:
            logger.exception(f"Error cargando skill {nombre}: {e}")
    
    def obtener_skill_relevante(self, consulta: str):
        """
        Determina si alguna skill es relevante para la consulta del usuario.
        RETORNA: (nombre_skill, instrucciones) o None
        """
        consulta_lower = consulta.lower()

        # ── SKILL: control_audio ──────────────────────────────────────────────
        palabras_clave_audio = [
            'volumen', 'subir', 'bajar', 'silenciar', 'silencia', 'silenciá',
            'mutear', 'mute', 'unmute', 'desmuteá', 'desmutea', 'activar audio',
            'audio', 'sonido', 'headset', 'auriculares', 'parlantes', 'altavoces',
            'salida de audio', 'dispositivo de audio', 'cambiar audio',
            'a tope', 'al máximo', 'sin sonido', 'con sonido'
        ]
        patrones_audio = [
            r'vol(umen)?', r'subi[r]? el (vol|son)', r'baj[ar]? el (vol|son)',
            r'silenci[a-z]+', r'mute[a-z]*', r'sin sonido', r'ponelo al \d+',
            r'pon[é]? (el)? vol', r'cuánto (está|esta) el vol',
            r'qué apps (tienen|con) (audio|sonido)',
        ]
        es_audio = any(p in consulta_lower for p in palabras_clave_audio)
        es_audio = es_audio or any(re.search(p, consulta_lower) for p in patrones_audio)

        if es_audio and 'control_audio' in self.skills:
            nombre = 'control_audio'
            instrucciones = self.skills[nombre].get('instrucciones', '')
            logger.debug(f"🔊 Skill relevante detectada: {nombre}")
            return nombre, instrucciones

        # ── SKILL: busqueda_web_actualizada ──────────────────────────────────
        palabras_clave_web = [
            'actual', 'hoy', 'reciente', 'último', 'nueva', 'noticias',
            'cotización', 'precio', 'lanzamiento', 'estreno', 'cambio',
            'novedad', 'tendencia', '2026', '2025', 'semana', 'mes',
            'ahora', 'últimas', 'recientes', 'ayer', 'mañana', 'top',
            'ranking', 'netflix', 'películas', 'series', 'campeón',
            'campeona', 'street fighter', 'cpt'
        ]
        patrones_temporales = [
            r'cu[aá]ndo', r'fecha', r'lanzamiento', r'estreno',
            r'noticias', r'pasa', r'pasa[ndo]?', r'actualidad',
            r'cotizaci[óo]n', r'precio', r'd[óo]lar', r'euro',
            r'quien es el actual', r'quien es el campeón'
        ]
        es_temporal = any(p in consulta_lower for p in palabras_clave_web)
        es_temporal = es_temporal or any(re.search(p, consulta_lower) for p in patrones_temporales)

        if es_temporal and 'busqueda_web_actualizada' in self.skills:
            nombre = 'busqueda_web_actualizada'
            instrucciones = self.skills[nombre].get('instrucciones', '')
            logger.debug(f"🔍 Skill relevante detectada: {nombre}")
            return nombre, instrucciones

        return None
    
    def obtener_instrucciones(self, nombre_skill: str) -> str:
        if nombre_skill in self.skills:
            return self.skills[nombre_skill].get('instrucciones', '')
        return ""
    
    def obtener_metadatos(self, nombre_skill: str) -> str:
        if nombre_skill in self.skills:
            return self.skills[nombre_skill].get('metadatos', '')
        return ""

# Instancia global
gestor = GestorSkills()
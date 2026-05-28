# Guardalo como modulos/limpiar_memoria.py
from memoria import coleccion_principal

def limpiar_todo():
    # Borramos todos los recuerdos
    ids = coleccion_principal.get()['ids']
    if ids:
        coleccion_principal.delete(ids=ids)
        print("✅ Bóveda vaciada. Ahora tenemos la memoria limpia.")
    else:
        print("ℹ️ La bóveda ya estaba vacía.")

if __name__ == "__main__":
    limpiar_todo()
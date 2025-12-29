import json
import os
from datetime import datetime
import Settings as ST


class Programaciones:
    def __init__(self, archivo='programaciones.json'):
        self.configuracion = ST.ConfiguracionSoftware()
        self.ruta_programaciones = self.configuracion.diccionario_valores.get("directorio_programaciones", "./")
        self.archivo = os.path.join(self.ruta_programaciones, archivo)
        self.directorio_historico = os.path.join(self.ruta_programaciones, "historico/")

        if not os.path.exists(self.ruta_programaciones):
            os.makedirs(self.ruta_programaciones)
        if not os.path.exists(self.directorio_historico):
            os.makedirs(self.directorio_historico)

        self.programaciones = []
        self.cargar_programaciones()

    # -------------------------
    # Helpers
    def _generar_id(self):
        import time
        return f"prog_{int(time.time() * 1000)}"

    def _normalize_dt(self, s: str) -> str:
        """
        Acepta:
          - 'YYYY-MM-DD HH:MM'
          - 'YYYY-MM-DD HH:MM:SS'
        Devuelve siempre 'YYYY-MM-DD HH:MM:SS'
        """
        s = (s or "").strip()
        if len(s) == 16:  # YYYY-MM-DD HH:MM
            return s + ":00"
        return s

    def _parse_dt(self, s: str):
        s = self._normalize_dt(s)
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

    # -------------------------
    # API pública
    def agregar_programacion(
            self,
            tipo,
            inicio,
            fin,
            duracion=None,
            activo=True,
            targets=None,
            accion="on",
            fin_accion="off",
            nombre=None,
        ):
            """
            tipo: 'Tiempo' o 'Fecha'
            inicio/fin: 'YYYY-MM-DD HH:MM:SS'
            targets: ['l1','l2',...]
            accion: 'on' | 'off' (al inicio)
            fin_accion: 'on' | 'off' (al finalizar)
            """

            programacion = {
                "id": self._generar_id(),
                "tipo": tipo,
                "nombre": nombre or "",
                "inicio": inicio,
                "fin": fin,
                "duracion": duracion,
                "activo": bool(activo),
                "targets": list(targets or []),
                "accion": accion or "on",
                "fin_accion": fin_accion or "off",
                "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            self.programaciones.append(programacion)
            self.guardar_programaciones()
            print(f"Programación agregada: {programacion['tipo']} - ID: {programacion['id']}")
            return programacion

    def obtener_programaciones(self):
        return self.programaciones

    def obtener_programacion(self, id_programacion):
        for prog in self.programaciones:
            if prog.get("id") == id_programacion:
                return prog
        return None

    def eliminar_programacion(self, id_programacion):
        for i, prog in enumerate(self.programaciones):
            if prog.get("id") == id_programacion:
                self.programaciones.pop(i)
                self.guardar_programaciones()
                print(f"Programación eliminada: ID {id_programacion}")
                return True
        return False

    def eliminar_por_indice(self, indice):
        try:
            self.programaciones.pop(indice)
            self.guardar_programaciones()
            print(f"Programación eliminada en índice {indice}")
            return True
        except IndexError:
            print(f"Índice {indice} fuera de rango")
            return False

    def actualizar_estado(self, id_programacion, activo):
        for prog in self.programaciones:
            if prog.get("id") == id_programacion:
                prog["activo"] = activo
                self.guardar_programaciones()
                print(f"Estado actualizado para ID {id_programacion}: {activo}")
                return True
        return False

    def obtener_programaciones_activas(self):
        """Retorna solo las programaciones activas en el momento actual"""
        ahora = datetime.now()
        activas = []

        for prog in self.programaciones:
            if not prog.get("activo", False):
                continue

            try:
                inicio = self._parse_dt(prog.get("inicio", ""))
                fin = self._parse_dt(prog.get("fin", ""))
                if inicio <= ahora <= fin:
                    # Backward compatible: si viene viejo sin targets/accion/fin_accion
                    prog.setdefault("targets", [])
                    prog.setdefault("accion", "on")
                    prog.setdefault("fin_accion", "off")
                    activas.append(prog)
            except Exception:
                continue

        return activas

    def limpiar_programaciones_vencidas(self):
        """Elimina programaciones que ya terminaron y las mueve al historial"""
        ahora = datetime.now()
        validas = []
        eliminadas = []

        for prog in self.programaciones:
            try:
                fin = self._parse_dt(prog.get("fin", ""))
                if fin > ahora:
                    validas.append(prog)
                else:
                    eliminadas.append(prog)
            except Exception:
                validas.append(prog)

        if eliminadas:
            self._guardar_en_historico(eliminadas)
            self.programaciones = validas
            self.guardar_programaciones()
            print(f"{len(eliminadas)} programaciones movidas al historial")

        return len(eliminadas)

    def guardar_programaciones(self):
        try:
            with open(self.archivo, "w", encoding="utf-8") as f:
                json.dump(self.programaciones, f, indent=4, ensure_ascii=False)
            print(f"Programaciones guardadas en: {self.archivo}")
            return True
        except Exception as e:
            print(f"Error al guardar programaciones: {e}")
            return False

    def cargar_programaciones(self):
        if not os.path.exists(self.archivo):
            print("No existe archivo de programaciones. Se creará uno nuevo.")
            self.programaciones = []
            return False

        try:
            with open(self.archivo, "r", encoding="utf-8") as f:
                self.programaciones = json.load(f)
            print(f"Cargadas {len(self.programaciones)} programaciones desde: {self.archivo}")
            return True
        except Exception as e:
            print(f"Error al cargar programaciones: {e}")
            self.programaciones = []
            return False

    def _guardar_en_historico(self, programaciones_vencidas):
        try:
            fecha_actual = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            archivo_historico = os.path.join(self.directorio_historico, f"historico_{fecha_actual}.json")

            with open(archivo_historico, "w", encoding="utf-8") as f:
                json.dump(programaciones_vencidas, f, indent=4, ensure_ascii=False)

            print(f"Historial guardado en: {archivo_historico}")
            return True
        except Exception as e:
            print(f"Error al guardar historial: {e}")
            return False

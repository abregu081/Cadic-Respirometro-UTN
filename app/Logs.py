import os
import sys
import datetime
import Settings as ST

class LogsGenerator:
    def __init__(self):
        self.configuracion = ST.ConfiguracionSoftware()
        self.ruta_logs = self.configuracion.diccionario_valores.get("directorio_salida_logs", "")
        if not os.path.exists(self.ruta_logs):
            os.makedirs(self.ruta_logs)
        self.fecha_actual = datetime.datetime.now().strftime("%Y_%m_%d")
        self.fecha_hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
        self.carpeta_fecha = os.path.join(self.ruta_logs, self.fecha_actual)
        if not os.path.exists(self.carpeta_fecha):
            os.makedirs(self.carpeta_fecha)
        self.archivo_los = os.path.join(self.carpeta_fecha, f"log_{self.fecha_hora_actual}.txt")

    def escribir_log(self, mensaje):
        try:
            with open(self.archivo_los, "a") as archivo:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                archivo.write(f"[{timestamp}] {mensaje}\n")
        except Exception as e:
            print("Error al escribir en el log:", e)
        
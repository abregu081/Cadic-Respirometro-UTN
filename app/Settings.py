import os
import sys

class configuracion:
    def __init__(self):
        self.ruta_config = os.path.join(os.path.dirname(sys.argv[0]), "Setting.ini")
        diccionario_config = {}
        try:
            with open(self.ruta_config, "r") as archivo:
                lineas_config = archivo.readlines()
                for linea in lineas_config:
                    linea = linea.strip()
                    if not linea or linea.startswith("#"):
                        continue
                    if "=" in linea:
                        clave, valor = linea.split("=", 1)
                        diccionario_config[clave.strip()] = valor.strip()
        except Exception as e:
            print("Error config:", e)
        self.diccionario_valores = diccionario_config
    
    def obtener_claves_wifi(self):
        ssid = self.diccionario_valores.get("WIFI_SSID", "")
        password = self.diccionario_valores.get("WIFI_PASSWORD", "")
        return ssid, password
        
    def obtener_parametros_servidor_mqtt(self):
        host = self.diccionario_valores.get("MQTT_HOST", "")
        port = int(self.diccionario_valores.get("MQTT_PORT", "1883"))
        return host, port
    
    def obtener_topicos_mqtt(self):
        topico_cmd = self.diccionario_valores.get("TOPICO_CMD", "")
        topico_estado = self.diccionario_valores.get("TOPICO_ESTADO", "")
        return topico_cmd, topico_estado

class ConfiguracionSoftware:
   def __init__(self):
        self.nombre_software = "Andrea_Software_v1.0"
        self.creador_software = "UVI - UTNFRGTDF"
        self.ruta_config = os.path.join(os.path.dirname(sys.argv[0]), "Setting.ini")
        diccionario_config = {}
        try:
            with open(self.ruta_config, "r") as archivo:
                lineas_config = archivo.readlines()
                for linea in lineas_config:
                    linea = linea.strip()
                    if not linea or linea.startswith("#"):
                        continue
                    if "=" in linea:
                        clave, valor = linea.split("=", 1)
                        diccionario_config[clave.strip()] = valor.strip()
        except Exception as e:
            print("Error config:", e)
        self.diccionario_valores = diccionario_config

   @staticmethod
   def obtener_directorio_programaciones(self):
         directorio = self.diccionario_valores.get("directorio_programaciones", "")
         if not os.path.exists(directorio):
               os.makedirs(directorio)
         return directorio
   
   @staticmethod
   def obtener_directorio_salida_logs(self):
         directorio = self.diccionario_valores.get("directorio_salida_logs", "")
         if not os.path.exists(directorio):
               os.makedirs(directorio)
         return directorio

        
   
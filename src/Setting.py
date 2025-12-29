class configuracion:
    def __init__(self):
        self.ruta_config = "/app/config.ini"
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
    
    def obtener_pines_reles(self):
        pines = []
        for i in range(1, 9):
            clave = f"PIN_RELE_{i}"
            valor = self.diccionario_valores.get(clave)
            if valor is not None:
                try:
                    pines.append(int(valor))
                except ValueError:
                    print(f"Valor inválido para {clave}: {valor}")
        return pines
    
    def guardar_cambios(self,cambios: dict):
        data = dict(self.diccionario_valores)

        for k,v in cambios.items():
            data[k] = v
    


        
    

import network
import time
import Setting as ST


class WiFi:
    def __init__(self):
        self.configuracion = ST.configuracion()
        self.ssid, self.password = self.configuracion.obtener_claves_wifi()
        self.wlan = network.WLAN(network.STA_IF)
        self.conectado = False
        self.intentos_maximos = 10
        self.timeout_conexion = 10
    
    def conectar(self, mostrar_progreso=True):
        """
        Conecta a la red WiFi configurada
        
        Args:
            mostrar_progreso: Si True, muestra el progreso de conexión
            
        Returns:
            bool: True si se conectó exitosamente, False en caso contrario
        """
        if self.wlan.isconnected():
            print("Ya conectado a WiFi")
            self.conectado = True
            return True
        
        # Activar interfaz WiFi
        self.wlan.active(True)
        
        if mostrar_progreso:
            print("Conectando a la red WiFi:", self.ssid)
        
        # Intentar conectar
        self.wlan.connect(self.ssid, self.password)
        
        # Esperar conexión
        inicio = time.time()
        while not self.wlan.isconnected():
            if time.time() - inicio > self.timeout_conexion:
                print("Timeout: No se pudo conectar a WiFi")
                self.conectado = False
                return False
            
            if mostrar_progreso:
                print(".", end="")
            time.sleep(0.5)
        
        if mostrar_progreso:
            print()
        
        self.conectado = True
        config = self.wlan.ifconfig()
        print("Conectado a WiFi exitosamente!")
        print("IP:", config[0])
        print("Máscara:", config[1])
        print("Gateway:", config[2])
        print("DNS:", config[3])
        
        return True
    
    def desconectar(self):
        """Desconecta del WiFi"""
        if self.wlan.isconnected():
            self.wlan.disconnect()
            self.conectado = False
            print("Desconectado de WiFi")
        self.wlan.active(False)
    
    def reconectar(self, intentos=None):
        """
        Intenta reconectar al WiFi en caso de pérdida de conexión
        
        Args:
            intentos: Número máximo de intentos (None usa intentos_maximos)
            
        Returns:
            bool: True si logró reconectar, False si falló
        """
        if intentos is None:
            intentos = self.intentos_maximos
        
        print("Intentando reconectar al WiFi...")
        
        for intento in range(1, intentos + 1):
            print(f"Intento {intento} de {intentos}")
            
            # Desconectar si está en un estado inconsistente
            if self.wlan.isconnected():
                self.wlan.disconnect()
                time.sleep(1)
            
            # Intentar conectar
            if self.conectar(mostrar_progreso=False):
                print("Reconexión exitosa!")
                return True
            
            # Esperar antes del siguiente intento
            if intento < intentos:
                print("Esperando antes de reintentar...")
                time.sleep(2)
        
        print(f"No se pudo reconectar después de {intentos} intentos")
        self.conectado = False
        return False
    
    def verificar_conexion(self, auto_reconectar=True):
        """
        Verifica si el WiFi está conectado
        
        Args:
            auto_reconectar: Si True, intenta reconectar automáticamente si se perdió la conexión
            
        Returns:
            bool: True si está conectado (o se reconectó), False en caso contrario
        """
        if self.wlan.isconnected():
            self.conectado = True
            return True
        
        print("Conexión WiFi perdida")
        self.conectado = False
        
        if auto_reconectar:
            return self.reconectar()
        
        return False
    
    def obtener_info(self):
        """
        Obtiene información de la conexión WiFi actual
        
        Returns:
            dict: Información de la red o None si no está conectado
        """
        if not self.wlan.isconnected():
            return None
        
        config = self.wlan.ifconfig()
        return {
            'ip': config[0],
            'mascara': config[1],
            'gateway': config[2],
            'dns': config[3],
            'ssid': self.ssid,
            'conectado': True
        }
    
    def obtener_intensidad_senal(self):
        """
        Obtiene la intensidad de la señal WiFi (RSSI)
        
        Returns:
            int: Valor RSSI en dBm o None si no está conectado
        """
        if not self.wlan.isconnected():
            return None
        
        # RSSI (Received Signal Strength Indicator)
        rssi = self.wlan.status('rssi')
        return rssi

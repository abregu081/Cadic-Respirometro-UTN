# boot.py - Se ejecuta al iniciar el ESP32
import time
from wifi import WiFi
from ServidorMQTT import ServidorMQTT



print("=== Iniciando sistema ===")

# 1. Conectar a WiFi
print("\n--- Configurando WiFi ---")
wifi = WiFi()
if wifi.conectar():
    print("WiFi configurado correctamente")
    info = wifi.obtener_info()
    if info:
        print("Dirección IP asignada:", info['ip'])
else:
    print("ERROR: No se pudo conectar al WiFi")
    print("El sistema continuará sin conexión de red")

if wifi.conectado:
    print("\n--- Conectando al servidor MQTT ---")
    mqtt = ServidorMQTT()
    
    try:
        mqtt.conectar()
        print("Servidor MQTT configurado correctamente")
    except Exception as e:
        print("ERROR al conectar MQTT:", e)
        print("Se intentará reconectar más tarde")

print("\n=== Sistema iniciado ===")

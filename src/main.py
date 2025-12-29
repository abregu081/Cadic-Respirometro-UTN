from machine import Pin, Timer
import time
import ujson
import urandom

import boot
import Setting as ST


# -------------------------
# Configuración pines relés (desde config.ini)
pines = ST.configuracion().obtener_pines_reles()
if len(pines) < 8:
    raise ValueError("Faltan pines de relés en config.ini (necesito PIN_RELE_1..PIN_RELE_8)")

# Pines del módulo de relés (8 canales)
RELES = [Pin(p, Pin.OUT) for p in pines[:8]]

# LED de placa
LED_PIN = 2
led = Pin(LED_PIN, Pin.OUT)
led.value(0)


# -------------------------
# Helpers relés (ACTIVO-BAJO: 0=ON, 1=OFF)
def rele_set(i: int, encender: bool):
    # i: 1..8
    RELES[i - 1].value(0 if encender else 1)

def rele_get(i: int) -> str:
    return "on" if RELES[i - 1].value() == 0 else "off"


def publicar_estado_reles(retain=False):
    """
    Publica estado completo en el tópico estado:
    {"online":"on","l1":"off",...,"l8":"off"}
    """
    if not hasattr(boot, "mqtt"):
        return
    payload = {"online": "on"}
    for i in range(1, 9):
        payload["l{}".format(i)] = rele_get(i)
    boot.mqtt.publicar(boot.mqtt.topico_estado, ujson.dumps(payload), retain=retain)


def publicar_offline_retenido():
    """
    Útil si tu broker/app quiere saber que murió la placa.
    Si tu wrapper soporta retain, esto deja el estado 'offline' retenido.
    """
    if not hasattr(boot, "mqtt"):
        return
    try:
        boot.mqtt.publicar(boot.mqtt.topico_estado, ujson.dumps({"online": "off"}), retain=True)
    except Exception as e:
        print("No se pudo publicar offline retenido:", e)


# -------------------------
# ARRANQUE SEGURO: todo OFF
for i in range(1, 9):
    rele_set(i, False)


# -------------------------
# Timer LED (NO toca MQTT)
timer = None
t_on = 1000
t_off = 1000
estado_led = False

def callback_timer(t):
    global estado_led, t_on, t_off, timer
    if estado_led:
        led.value(0)
        estado_led = False
        timer.init(period=t_off, mode=Timer.ONE_SHOT, callback=callback_timer)
    else:
        led.value(1)
        estado_led = True
        timer.init(period=t_on, mode=Timer.ONE_SHOT, callback=callback_timer)

def iniciar_timer(on_ms, off_ms):
    global timer, t_on, t_off, estado_led
    t_on = int(on_ms)
    t_off = int(off_ms)
    if timer:
        timer.deinit()
    timer = Timer(0)
    led.value(1)
    estado_led = True
    timer.init(period=t_on, mode=Timer.ONE_SHOT, callback=callback_timer)

def detener_timer():
    global timer
    if timer:
        timer.deinit()
        timer = None
    led.value(0)


# -------------------------
# Publicación periódica segura (NO publicar MQTT dentro de Timer callback)
_next_pub_ms = 0
_pub_interval_ms = 3000  # inicial

def _armar_siguiente_pub():
    global _next_pub_ms, _pub_interval_ms
    # intervalo aleatorio 2..5 segundos (2000..5000ms)
    _pub_interval_ms = 2000 + (urandom.getrandbits(16) % 3001)
    _next_pub_ms = time.ticks_add(time.ticks_ms(), _pub_interval_ms)


# -------------------------
# MQTT callback
def callback_mqtt(topic, msg):
    try:
        if isinstance(msg, (bytes, bytearray)):
            data = ujson.loads(msg.decode())
        else:
            data = ujson.loads(msg)

        # 1) pedido de estado (cuando la app abre)
        if data.get("get") == "status":
            publicar_estado_reles(retain=False)
            return

        # 2) compatibilidad cmd/estado
        cmd = data.get("cmd") or data.get("estado")

        # Control LED principal
        if cmd == "on":
            detener_timer()
            led.value(1)

        elif cmd == "off":
            detener_timer()
            led.value(0)

        elif cmd == "timer":
            on_time = data.get("on", 1000)
            off_time = data.get("off", 1000)
            iniciar_timer(on_time, off_time)

        # 3) Control relés l1..l8
        cambio = False
        for i in range(1, 9):
            key = "l{}".format(i)
            if key in data:
                v = data[key]
                if v == "on":
                    rele_set(i, True)
                    cambio = True
                elif v == "off":
                    rele_set(i, False)
                    cambio = True

        # si hubo cambios, publicar estado completo (retain=False para no ensuciar retained)
        # si vos querés que el último estado quede retenido, poné retain=True
        if cambio:
            publicar_estado_reles(retain=False)

    except Exception as e:
        print("Error callback MQTT:", e)


# -------------------------
# Suscripción inicial + publicación de estado al iniciar
def suscribir_y_publicar_inicio():
    if not hasattr(boot, "mqtt"):
        return

    # (Opcional) si tu wrapper permite configurar LWT, hacelo en tu boot.mqtt.conectar()
    # acá solo dejamos offline retenido previo y luego online
    try:
        # deja "offline" como default al reiniciar (si el dispositivo muere sin cerrar, queda offline)
        publicar_offline_retenido()
    except Exception:
        pass

    boot.mqtt.suscribir(boot.mqtt.topico_cmd, callback_mqtt)

    # Estado inicial
    publicar_estado_reles(retain=True)  # dejamos el “último” retenido como ONLINE y estados actuales
    _armar_siguiente_pub()


# IMPORTANTE: llamar al inicio
suscribir_y_publicar_inicio()


# -------------------------
# Loop principal
contador = 0

try:
    while True:
        # Cada ~30s verificar WiFi
        if contador % 30 == 0 and hasattr(boot, "wifi"):
            try:
                boot.wifi.verificar_conexion(auto_reconectar=True)
            except Exception as e:
                print("Error wifi.verificar_conexion:", e)

        # MQTT: mensajes + reconexión
        if hasattr(boot, "mqtt"):
            try:
                boot.mqtt.verificar_mensajes()
            except Exception as e:
                print("Error MQTT verificar_mensajes:", e)
                try:
                    boot.mqtt.reconectar()
                    suscribir_y_publicar_inicio()
                except Exception as e2:
                    print("Error MQTT reconectar:", e2)

            # ✅ Heartbeat periódico (online + estados) cada 2-5s (retain=False)
            try:
                if time.ticks_diff(time.ticks_ms(), _next_pub_ms) >= 0:
                    publicar_estado_reles(retain=False)
                    _armar_siguiente_pub()
            except Exception as e:
                print("Error publicando estado periódico:", e)
                _armar_siguiente_pub()

        time.sleep(1)
        contador += 1

except KeyboardInterrupt:
    detener_timer()
    # marcar offline retenido al salir “bien”
    try:
        publicar_offline_retenido()
    except Exception:
        pass
    if hasattr(boot, "mqtt"):
        try:
            boot.mqtt.desconectar()
        except Exception as e:
            print("Error MQTT desconectar:", e)

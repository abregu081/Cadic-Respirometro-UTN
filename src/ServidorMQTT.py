# ServidorMQTT.py (MicroPython)
from umqtt.simple import MQTTClient
import time
import machine
import ubinascii
import ujson
import Setting as ST


class ServidorMQTT:
    def __init__(self):
        self.configuracion = ST.configuracion()
        self.host, self.port = self.configuracion.obtener_parametros_servidor_mqtt()
        self.topico_cmd, self.topico_estado = self.configuracion.obtener_topicos_mqtt()

        self.cliente = None
        self.conectado = False

        # Keepalive: ayuda a que el broker detecte caídas y dispare el LWT
        self.keepalive = 30  # segundos (ajustable)
        self._ultimo_intento = 0

        # Client ID único por placa
        uid = ubinascii.hexlify(machine.unique_id()).decode()
        self.client_id = f"Andrea_ESP32_{uid}"

        # Mensajes online/offline (retained)
        self.payload_online_on = ujson.dumps({"online": "on"})
        self.payload_online_off = ujson.dumps({"online": "off"})

    def conectar(self):
        try:
            self.cliente = MQTTClient(
                client_id=self.client_id,
                server=self.host,
                port=self.port,
                keepalive=self.keepalive,
            )

            # Last Will: si se cae inesperadamente, el broker publica esto
            # (No todas las builds traen set_last_will; por eso el hasattr)
            if hasattr(self.cliente, "set_last_will"):
                self.cliente.set_last_will(
                    self.topico_estado,
                    self.payload_online_off,
                    retain=True,
                    qos=0,
                )

            self.cliente.connect()
            self.conectado = True
            print("Conectado al servidor MQTT en {}:{} (id={})".format(self.host, self.port, self.client_id))

            # Apenas conecta: marcar ONLINE (retained)
            self.publicar(self.topico_estado, self.payload_online_on, retain=True)

            return True

        except Exception as e:
            self.conectado = False
            print("Error al conectar al servidor MQTT:", e)
            return False

    def desconectar(self):
        try:
            if self.cliente:
                # Desconexión limpia: publicar OFF también (retained)
                try:
                    self.publicar(self.topico_estado, self.payload_online_off, retain=True)
                except:
                    pass

                self.cliente.disconnect()
            self.conectado = False
            print("Desconectado del servidor MQTT")
        except Exception as e:
            self.conectado = False
            print("Error al desconectar del servidor MQTT:", e)

    def publicar(self, topic, mensaje, retain=False):
        try:
            if not self.cliente:
                raise Exception("Cliente MQTT no inicializado")

            # umqtt acepta str/bytes; dejamos str
            self.cliente.publish(topic, mensaje, retain=retain)
            # print("Mensaje publicado en {}: {}".format(topic, mensaje))
            return True
        except Exception as e:
            self.conectado = False
            print("Error al publicar en {}: {}".format(topic, e))
            return False

    def suscribir(self, topic, callback=None):
        try:
            if not self.cliente:
                raise Exception("Cliente MQTT no inicializado")

            if callback:
                self.cliente.set_callback(callback)

            self.cliente.subscribe(topic)
            print("Suscrito al tópico {}".format(topic))
            return True
        except Exception as e:
            self.conectado = False
            print("Error al suscribir al tópico {}: {}".format(topic, e))
            return False

    def verificar_mensajes(self):
        """
        check_msg() no bloquea. Si hay mensaje llama al callback.
        Si explota por desconexión, marcamos conectado=False para que tu loop reconecte.
        """
        try:
            if self.cliente:
                self.cliente.check_msg()
            return True
        except Exception as e:
            self.conectado = False
            print("Error al verificar mensajes entrantes:", e)
            return False

    def esperar_mensaje(self):
        """
        wait_msg() bloquea hasta recibir un msg.
        Útil si querés un modo 'solo escuchar'.
        """
        try:
            print("Esperando mensajes en {}...".format(self.topico_cmd))
            while True:
                self.cliente.wait_msg()
        except Exception as e:
            self.conectado = False
            print("Error al esperar mensajes:", e)

    def reconectar(self, min_interval_s=2):
        """
        Reconexión con un mínimo de espera entre intentos para no spamear.
        """
        ahora = time.time()
        if (ahora - self._ultimo_intento) < min_interval_s:
            return False

        self._ultimo_intento = ahora

        try:
            try:
                self.desconectar()
            except:
                pass

            time.sleep(1)
            ok = self.conectar()
            return ok
        except Exception as e:
            self.conectado = False
            print("Error al reconectar al servidor MQTT:", e)
            return False

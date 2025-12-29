import time
import paho.mqtt.client as mqtt
import Settings as ST


class ServidorMQTT:
    def __init__(self):
        self.configuracion = ST.configuracion()
        self.host, self.port = self.configuracion.obtener_parametros_servidor_mqtt()
        self.topico_cmd, self.topico_estado = self.configuracion.obtener_topicos_mqtt()

        # Cliente MQTT
        self.cliente = mqtt.Client(client_id="Andrea_software")
        self.conectado = False

        # Callbacks por tópico
        # callback(topic: str, payload: bytes) -> None
        self._callbacks = {}

        # Configurar callbacks principales
        self.cliente.on_connect = self._on_connect
        self.cliente.on_disconnect = self._on_disconnect
        self.cliente.on_message = self._on_message

    # -------------------------
    # Callbacks internos Paho
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.conectado = True
            print("Conectado al servidor MQTT en {}:{}".format(self.host, self.port))

            # Re-suscribir a tópicos registrados (por si reconectó)
            for topic in self._callbacks.keys():
                try:
                    self.cliente.subscribe(topic)
                except Exception as e:
                    print("Error re-suscribiendo {}: {}".format(topic, e))
        else:
            self.conectado = False
            print("Error al conectar al servidor MQTT. Código: {}".format(rc))

    def _on_disconnect(self, client, userdata, rc):
        self.conectado = False
        print("Desconectado del servidor MQTT (rc={})".format(rc))

    def _on_message(self, client, userdata, msg):
        try:
            cb = self._callbacks.get(msg.topic)
            if cb:
                cb(msg.topic, msg.payload)
            else:
                print("Mensaje recibido en {}: {}".format(msg.topic, msg.payload.decode(errors="ignore")))
        except Exception as e:
            print("Error procesando mensaje MQTT:", e)

    # -------------------------
    # API pública
    def conectar(self):
        try:
            self.cliente.connect(self.host, self.port, keepalive=60)
            self.cliente.loop_start()  # loop en segundo plano
            print("Conectando al servidor MQTT en {}:{}".format(self.host, self.port))
            return True
        except Exception as e:
            self.conectado = False
            print("Error al conectar al servidor MQTT:", e)
            return False

    def desconectar(self):
        try:
            self.cliente.loop_stop()
            self.cliente.disconnect()
            self.conectado = False
            print("Desconectando del servidor MQTT")
            return True
        except Exception as e:
            print("Error al desconectar del servidor MQTT:", e)
            return False

    def publicar(self, topic, mensaje, retain=False, qos=0):
        try:
            if isinstance(mensaje, str):
                mensaje = mensaje.encode()

            result = self.cliente.publish(topic, mensaje, qos=qos, retain=retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print("Publicado en {} (retain={}): {}".format(topic, retain, mensaje))
                return True
            else:
                print("Error al publicar. Código: {}".format(result.rc))
                return False

        except Exception as e:
            print("Error al publicar en {}: {}".format(topic, e))
            return False

    def suscribir(self, topic, callback=None, qos=0):
        """
        callback(topic: str, payload: bytes) -> None
        """
        try:
            if callback:
                self._callbacks[topic] = callback

            self.cliente.subscribe(topic, qos=qos)
            print("Suscrito al tópico {}".format(topic))
            return True
        except Exception as e:
            print("Error al suscribir al tópico {}: {}".format(topic, e))
            return False

    def desuscribir(self, topic):
        try:
            if topic in self._callbacks:
                del self._callbacks[topic]
            self.cliente.unsubscribe(topic)
            print("Desuscrito del tópico {}".format(topic))
            return True
        except Exception as e:
            print("Error al desuscribir {}: {}".format(topic, e))
            return False

    def reconectar(self, espera_s=2):
        """
        Fuerza reconexión. El on_connect re-suscribe a todo lo registrado.
        """
        try:
            try:
                self.desconectar()
            except Exception:
                pass

            time.sleep(espera_s)
            return self.conectar()

        except Exception as e:
            print("Error al reconectar al servidor MQTT:", e)
            return False

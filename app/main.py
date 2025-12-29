import flet as ft
from datetime import datetime, timedelta
import math
import Programaciones as PR
import ConexionMQTT as mqtt
import json
import asyncio
import queue
import time as pytime
import os

class ControlRespirometro(ft.Container):
    
    # -------------------------
    # CONFIGURACIONES (VISTA)
    def _get_setting_ini_path(self) -> str:
        """Devuelve la ruta real del Setting.ini tanto en modo dev como compilado (.exe)."""
        import os, sys
        # 1) en el mismo directorio del ejecutable/script
        p1 = os.path.join(os.path.dirname(sys.argv[0]), "Setting.ini")
        # 2) compatibilidad con tu estructura anterior
        p2 = os.path.join("app", "Setting.ini")

        if os.path.exists(p1):
            return p1
        if os.path.exists(p2):
            return p2

        # si no existe, preferimos crearlo junto al ejecutable
        return p1

    def _leer_setting_ini(self) -> str:
        try:
            ruta = self._get_setting_ini_path()
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as ex:
            return f"Error al leer Setting.ini: {ex}"

    def _escribir_setting_ini(self, contenido: str) -> None:
        ruta = self._get_setting_ini_path()
        # crear carpeta si hace falta (por si queda algo como app/Setting.ini)
        import os
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)

    def _parse_ini_kv(self, contenido: str) -> dict:
        d = {}
        for linea in contenido.splitlines():
            s = linea.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            d[k.strip()] = v.strip()
        return d

    # -------------------------
    # Historial de programaciones (persistente en JSON)
    def _get_historial_path(self) -> str:
        import os, sys
        return os.path.join(os.path.dirname(sys.argv[0]), "HistorialProgramaciones.json")

    def _cargar_historial(self) -> list:
        ruta = self._get_historial_path()
        try:
            if os.path.exists(ruta):
                with open(ruta, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"Historial: error al leer {ruta}: {e}")
        return []

    def _guardar_historial(self) -> None:
        ruta = self._get_historial_path()
        try:
            # asegurar directorio (por si sys.argv[0] apunta a otro lugar)
            os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(self.historial_programaciones, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Historial: error al guardar {ruta}: {e}")

    def _agregar_historial(self, evento: str, prog: dict | None = None, extra: dict | None = None) -> None:
        try:
            item = {
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "evento": evento,
            }
            if prog:
                # Guardar solo campos relevantes para mostrar
                item["prog"] = {
                    "id": prog.get("id"),
                    "tipo": prog.get("tipo"),
                    "inicio": prog.get("inicio"),
                    "fin": prog.get("fin"),
                    "duracion": prog.get("duracion"),
                    "targets": prog.get("targets", []),
                    "accion": prog.get("accion"),
                    "fin_accion": prog.get("fin_accion"),
                }
            if extra:
                item["extra"] = extra

            self.historial_programaciones.insert(0, item)  # newest first
            # limitar tamaño
            if len(self.historial_programaciones) > 300:
                self.historial_programaciones = self.historial_programaciones[:300]
            self._guardar_historial()
        except Exception as e:
            print(f"Historial: no se pudo agregar item: {e}")


    def _aplicar_updates_a_ini(self, contenido: str, updates: dict) -> str:
        """Actualiza solo claves existentes (o las agrega) preservando comentarios/orden."""
        lines = contenido.splitlines(True)  # conserva \n
        done = set()

        out = []
        for ln in lines:
            stripped = ln.strip()
            if not stripped or stripped.startswith("#") or "=" not in ln:
                out.append(ln)
                continue

            k, v = ln.split("=", 1)
            key = k.strip()
            if key in updates:
                out.append(f"{key}={updates[key]}\n")
                done.add(key)
            else:
                out.append(ln)

        # agregar claves que no estaban
        missing = [k for k in updates.keys() if k not in done]
        if missing:
            if out and not out[-1].endswith("\n"):
                out[-1] = out[-1] + "\n"
            out.append("\n# --- Agregado por la app ---\n")
            for k in missing:
                out.append(f"{k}={updates[k]}\n")

        return "".join(out)

    def mostrar_vista_config(self, e=None):
        self.vista_actual = "config"
        self.build_config_view()
        self.page.update()

    def volver_desde_config(self, e=None):
        self.vista_actual = "main"
        self.build_main_view()
        self.page.update()

    def mostrar_vista_historial(self, e=None):
        self.vista_actual = "history"
        # recargar desde disco por si cambió
        self.historial_programaciones = self._cargar_historial()
        self.build_history_view()
        self.page.update()

    def volver_desde_historial(self, e=None):
        self.vista_actual = "main"
        self.build_main_view()
        self.page.update()


    def _snack(self, msg: str):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg))
        self.page.snack_bar.open = True
        self.page.update()

    def build_config_view(self):
        """Vista de configuración: formulario + editor de texto."""
        contenido = self._leer_setting_ini()
        kv = self._parse_ini_kv(contenido)

        # Campos (formulario)
        self.cfg_wifi_ssid = ft.TextField(label="WIFI_SSID", value=kv.get("WIFI_SSID", ""), width=420, color="black")
        self.cfg_wifi_pass = ft.TextField(label="WIFI_PASSWORD", value=kv.get("WIFI_PASSWORD", ""), width=420, password=True, can_reveal_password=True, color="black")

        self.cfg_mqtt_host = ft.TextField(label="MQTT_HOST", value=kv.get("MQTT_HOST", ""), width=420, color="black")
        self.cfg_mqtt_port = ft.TextField(label="MQTT_PORT", value=str(kv.get("MQTT_PORT", "1883")), width=160, color="black")

        self.cfg_topic_cmd = ft.TextField(label="TOPICO_CMD", value=kv.get("TOPICO_CMD", ""), width=420, color="black")
        self.cfg_topic_estado = ft.TextField(label="TOPICO_ESTADO", value=kv.get("TOPICO_ESTADO", ""), width=420, color="black")

        # Editor texto (raw)
        self.cfg_raw_editor = ft.TextField(
            value=contenido,
            multiline=True,
            min_lines=18,
            max_lines=26,
            expand=True,
            color="black",
            border_color=self.blue_color,
        )

        def guardar_formulario(ev):
            try:
                # validar puerto
                try:
                    port_int = int(self.cfg_mqtt_port.value.strip() or "1883")
                    if port_int <= 0 or port_int > 65535:
                        raise ValueError()
                except Exception:
                    self._snack("MQTT_PORT inválido (1..65535).")
                    return

                updates = {
                    "WIFI_SSID": (self.cfg_wifi_ssid.value or "").strip(),
                    "WIFI_PASSWORD": (self.cfg_wifi_pass.value or "").strip(),
                    "MQTT_HOST": (self.cfg_mqtt_host.value or "").strip(),
                    "MQTT_PORT": str(port_int),
                    "TOPICO_CMD": (self.cfg_topic_cmd.value or "").strip(),
                    "TOPICO_ESTADO": (self.cfg_topic_estado.value or "").strip(),
                }

                actual = self._leer_setting_ini()
                nuevo = self._aplicar_updates_a_ini(actual, updates)
                self._escribir_setting_ini(nuevo)
                self.cfg_raw_editor.value = nuevo
                self._snack("Configuración guardada. Reiniciá la app para aplicar cambios.")
            except Exception as ex:
                self._snack(f"Error al guardar: {ex}")

        def guardar_raw(ev):
            try:
                self._escribir_setting_ini(self.cfg_raw_editor.value or "")
                self._snack("Setting.ini guardado. Reiniciá la app para aplicar cambios.")
            except Exception as ex:
                self._snack(f"Error al guardar: {ex}")

        header = ft.Container(
            padding=10,
            bgcolor=self.dark_white,
            border_radius=12,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.SETTINGS, color=self.blue_color),
                            ft.Text("Configuraciones", size=20, weight="bold", color="black"),
                            ft.Text(f"Archivo: {self._get_setting_ini_path()}", size=11, color=self.grey_color),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.FilledButton(
                                "Volver",
                                icon=ft.Icons.ARROW_BACK,
                                style=ft.ButtonStyle(bgcolor="black", color="white"),
                                on_click=self.volver_desde_config,
                            ),
                        ],
                    ),
                ],
            ),
        )

        tab_form = ft.Container(
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Formulario rápido", size=16, weight="bold", color="black"),
                    ft.Text("Editá los campos principales sin tocar el archivo manualmente.", size=12, color=self.grey_color),
                    ft.Divider(height=10, color="transparent"),

                    ft.Text("WiFi", size=13, weight="bold", color="black"),
                    self.cfg_wifi_ssid,
                    self.cfg_wifi_pass,

                    ft.Divider(height=10, color="transparent"),
                    ft.Text("MQTT", size=13, weight="bold", color="black"),
                    ft.Row(controls=[self.cfg_mqtt_host, self.cfg_mqtt_port], spacing=10),
                    self.cfg_topic_cmd,
                    self.cfg_topic_estado,

                    ft.Divider(height=10, color="transparent"),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        controls=[
                            ft.FilledButton(
                                "Guardar",
                                icon=ft.Icons.SAVE,
                                style=ft.ButtonStyle(bgcolor=self.blue_color, color="white"),
                                on_click=guardar_formulario,
                            ),
                        ],
                    ),
                ],
            ),
        )

        tab_raw = ft.Container(
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Editor de texto (avanzado)", size=16, weight="bold", color="black"),
                    ft.Text("Si sabés lo que hacés, podés editar el Setting.ini completo.", size=12, color=self.grey_color),
                    self.cfg_raw_editor,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        controls=[
                            ft.FilledButton(
                                "Guardar",
                                icon=ft.Icons.SAVE,
                                style=ft.ButtonStyle(bgcolor=self.blue_color, color="white"),
                                on_click=guardar_raw,
                            ),
                        ],
                    ),
                ],
            ),
        )

        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[
                ft.Tab(text="Formulario", icon=ft.Icons.LIST_ALT, content=tab_form),
                ft.Tab(text="Texto", icon=ft.Icons.CODE, content=tab_raw),
            ],
            expand=1,
        )

        self.content = ft.Column(
            expand=True,
            spacing=10,
            controls=[
                header,
                tabs,
            ],
        )
    def _actualizar_ui_rele(self, rele_key: str, encendido: bool):
        # actualizar modelo
        rele = next((r for r in self.reles if r["key"] == rele_key), None)
        if rele:
            rele["estado"] = encendido

        # actualizar widgets (si ya existen)
        w = self._rele_widgets.get(rele_key)
        if w:
            w["indicador"].bgcolor = self.green_color if encendido else self.red_color
            w["txt_estado"].value = "ON" if encendido else "OFF"
            w["btn"].text = "Apagar" if encendido else "Encender"
            w["btn"].icon = ft.Icons.POWER_OFF if encendido else ft.Icons.POWER

    async def _ui_loop(self):
        while True:
            # 1) procesar cola MQTT en UI thread
            self._procesar_mqtt_queue()

            # 2) actualizar lógica/UI (ya estás en UI thread)
            if self.vista_actual == "main":
                self.evaluar_programaciones()      # ahora seguro
                self.actualizar_estado_mqtt()      # ahora seguro

            self.page.update()
            await asyncio.sleep(0.5)  # 0.5s o 1s

    def _procesar_mqtt_queue(self):
        updated = False
        while True:
            try:
                data = self._mqtt_queue.get_nowait()
            except queue.Empty:
                break

            # marca “último visto”
            self._last_seen_estado = datetime.now()

            # online/offline si viene
            if "online" in data:
                online = (data["online"] == "on")
                self.indicador_placa.bgcolor = self.green_color if online else self.red_color
                self.texto_placa.value = "PLACA: ONLINE" if online else "PLACA: OFFLINE"
                self.texto_placa.color = self.green_color if online else self.red_color

            # estados l1..l8
            for i in range(1, 9):
                k = f"l{i}"
                if k in data:
                    self._actualizar_ui_rele(k, data[k] == "on")

            updated = True

        return updated

    def _aplicar_programaciones_a_reles(self, programaciones_activas):
        def parse_inicio(p):
            try:
                return datetime.strptime(p["inicio"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.min

        activas_ordenadas = sorted(programaciones_activas, key=parse_inicio)

        desired = {}
        for prog in activas_ordenadas:
            for k in prog.get("targets", []):
                desired[k] = prog.get("accion", "on")

        ids_actuales = {p.get("id") for p in programaciones_activas if p.get("id")}
        terminadas = self._active_prog_ids_prev - ids_actuales

        # ✅ USAR CACHE (aunque ya se haya movido al historial)
        for pid in terminadas:
            prog = self._active_prog_prev.get(pid) or self.gestor_programaciones.obtener_programacion(pid)
            if not prog:
                continue
            fin_acc = prog.get("fin_accion", "off")
            
            # Registrar finalización en historial (una vez por programación)
            self._agregar_historial(
                evento="FINALIZADA",
                prog=prog,
                extra={"fin_accion_aplicada": fin_acc}
            )

            for k in prog.get("targets", []):
                if k not in desired:
                    desired[k] = fin_acc

        for k, acc in desired.items():
            encender = (acc == "on")
            rele = next((r for r in self.reles if r["key"] == k), None)
            estado_actual = bool(rele["estado"]) if rele else None
            if estado_actual is None:
                continue
            if estado_actual != encender:
                self.enviar_mqtt_rele(k, encender)

        # ✅ actualizar “prev”
        self._active_prog_ids_prev = ids_actuales
        self._active_prog_prev = {p["id"]: p for p in programaciones_activas if p.get("id")}


    def _on_mqtt_estado(self, topic, payload: bytes):
        try:
            data = json.loads(payload.decode("utf-8", errors="ignore"))
            # Encolar para procesar en UI thread
            self._mqtt_queue.put(data)
        except Exception as e:
            print("Error decodificando topico_estado:", e)
            
    def enviar_mqtt_rele(self, rele_key: str, encender: bool):
        """Envía: {"l2":"off"} / {"l2":"on"} al tópico cmd."""
        if getattr(self.mqtt, 'conectado', False):
            try:
                payload = json.dumps({rele_key: "on" if encender else "off"})
                self.mqtt.publicar(self.mqtt.topico_cmd, payload)
                print(f"Comando {rele_key} -> {'on' if encender else 'off'} enviado: {payload}")
            except Exception as ex:
                print(f"Error enviando {rele_key}: {ex}")
        else:
            print("MQTT no conectado")
    

    def _toggle_rele_handler(self, rele_key: str):
        def handler(e):
            # Tomar estado actual del modelo (lo actualiza topico_estado)
            rele = next((r for r in self.reles if r["key"] == rele_key), None)
            if not rele:
                return

            # Queremos el opuesto, pero NO tocamos la UI acá
            nuevo = not bool(rele["estado"])

            # Mandar comando (la UI se actualizará cuando llegue topico_estado)
            self.enviar_mqtt_rele(rele_key, nuevo)

        return handler


    def crear_lista_reles(self):
        """Crea la lista scrollable de relés con botón a la derecha."""
        self._rele_widgets = {}
        items = []

        for rele in self.reles:
            key = rele["key"]
            encendido = bool(rele["estado"])

            indicador = ft.Container(
                width=10, height=10, border_radius=5,
                bgcolor=self.green_color if encendido else self.red_color
            )
            txt_nombre = ft.Text(rele["nombre"], size=12, weight="bold", color="black")
            txt_estado = ft.Text("ON" if encendido else "OFF", size=11, color=self.grey_color)

            btn = ft.FilledButton(
                text="Apagar" if encendido else "Encender",
                icon=ft.Icons.POWER_OFF if encendido else ft.Icons.POWER,
                height=34,
                style=ft.ButtonStyle(bgcolor="black", color="white"),
                on_click=self._toggle_rele_handler(key),
            )

            self._rele_widgets[key] = {"indicador": indicador, "txt_estado": txt_estado, "btn": btn}

            items.append(
                ft.Container(
                    padding=8,
                    border_radius=10,
                    bgcolor="white",
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    indicador,
                                    ft.Column([txt_nombre, txt_estado], spacing=0),
                                ],
                            ),
                            btn,
                        ],
                    ),
                )
            )

        return items


    def __init__(self, page: ft.Page):
        super().__init__(expand=True)
        self.page = page
        self._mqtt_queue = queue.Queue()
        self._last_online_ts = 0.0
        self.page.title = "Control Respirómetro CADIC"
        self.bg_color = "#ffffff"
        self.dark_white = "#e7e6e9"
        self.grey_color = "#a9acb6"
        self.yellow_color = "#ece5d5"
        self.green_color = "#4caf50"
        self.red_color = "#f44336"
        self.blue_color = "#2196f3"
        self.page.bgcolor = self.bg_color
        self.detalle_prog_titulo = ft.Text("", size=14, weight="bold", color="black")
        self.detalle_prog_linea1 = ft.Text("", size=12, color=self.grey_color)
        self.detalle_prog_linea2 = ft.Text("", size=12, color=self.grey_color)
        self.detalle_prog_linea3 = ft.Text("", size=12, color=self.grey_color)
        self.page.theme = ft.Theme(font_family="Roboto")  # o "Noto Sans", "Ubuntu"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self._selected_prog_id = None
        self._active_prog_prev = {}
        self._last_seen_estado = None
        self._offline_timeout_s = 320  # si no veo estado en tanto tiempo, marcar offline  

        self.card_detalle_prog = ft.Container(
            visible=False,
            border_radius=12,
            bgcolor="white",
            padding=12,
            border=ft.border.all(1, self.dark_white),
            content=ft.Column(
                spacing=4,
                controls=[
                    self.detalle_prog_titulo,
                    self.detalle_prog_linea1,
                    self.detalle_prog_linea2,
                    self.detalle_prog_linea3,
                ],
            ),
        )
        
        # Relés (modelo simple)
        # Cambiá nombres/cantidad según tu placa
        self.reles = [
            {"key": f"l{i}", "nombre": f"Relé {i}", "estado": False}
            for i in range(1, 9)
        ]
        # Widgets por relé (para poder actualizar UI rápido)
        self._rele_widgets = {}  
        # Estado de la placa
        self.placa_encendida = False
        self.placa_pausada = False
        self.programacion_activa_actual = None
        self.tiempo_pausado_inicio = None
        
        # --- NUEVO: selección de relés + acción para programación ---
        self.chk_reles = {
            r["key"]: ft.Checkbox(
                label=r["nombre"],
                value=False,
                width=95,
                label_style=ft.TextStyle(size=12, color="black"),
            )
            for r in self.reles
        }

        self.accion_prog = ft.Dropdown(
            label="Acción al INICIO",
            value="on",
            width=240,
            text_style=ft.TextStyle(size=14, color="black"),
            label_style=ft.TextStyle(size=12, color="black"),
            options=[
                ft.dropdown.Option("on", "Encender (ON)"),
                ft.dropdown.Option("off", "Apagar (OFF)"),
            ],
        )

        self.fin_accion_prog = ft.Dropdown(
            label="Acción al FINAL",
            value="off",
            width=240,
            text_style=ft.TextStyle(size=14, color="black"),
            label_style=ft.TextStyle(size=12, color="black"),
            options=[
                ft.dropdown.Option("off", "Apagar (OFF)"),
                ft.dropdown.Option("on", "Encender (ON)"),
            ],
        )

        # --- NUEVO: para detectar programas que terminan/inician ---
        self._active_prog_ids_prev = set()

        # Gestor de programaciones
        self.gestor_programaciones = PR.Programaciones()

        # Historial persistente de programaciones (creadas/finalizadas/canceladas)
        self.historial_programaciones = self._cargar_historial()

        
        # Vista actual (main o add)
        self.vista_actual = "main"
        
        # Campos de entrada para programación por tiempo
        self.tiempo_horas = ft.TextField(label="Horas", value="0", width=80, text_align=ft.TextAlign.CENTER, color="black")
        self.tiempo_minutos = ft.TextField(label="Minutos", value="0", width=80, text_align=ft.TextAlign.CENTER, color="black")
        self.tiempo_segundos = ft.TextField(label="Segundos", value="0", width=80, text_align=ft.TextAlign.CENTER, color="black")
        
        # Campos de entrada para programación por fechas
        self.fecha_inicio = ft.TextField(label="Fecha Inicio", value=datetime.now().strftime("%Y-%m-%d"), width=150, read_only=True, color="black")
        self.hora_inicio = ft.TextField(label="Hora", value=datetime.now().strftime("%H:%M"), width=100, color="black")
        self.fecha_fin = ft.TextField(label="Fecha Fin", value=datetime.now().strftime("%Y-%m-%d"), width=150, read_only=True, color="black")
        self.hora_fin = ft.TextField(label="Hora", value=datetime.now().strftime("%H:%M"), width=100, color="black")
        
        # Indicador de estado
        self.indicador_estado = ft.Container(
            width=20, height=20, border_radius=10,
            bgcolor=self.red_color
        )
        
        self.texto_estado = ft.Text("APAGADO", size=16, weight="bold", color=self.red_color)
        
        # Estado ONLINE/OFFLINE de la placa (viene por MQTT topico_estado: {"online":"on/off"})
        self.indicador_placa = ft.Container(
            width=14, height=14, border_radius=7,
            bgcolor=self.red_color
        )
        self.texto_placa = ft.Text("PLACA: OFFLINE", size=12, weight="bold", color=self.red_color)

        # Textos para programación activa
        self.texto_prog_activa = ft.Text("Ninguna programación activa", size=14, color=self.grey_color, text_align=ft.TextAlign.CENTER)
        self.texto_tiempo_restante = ft.Text("", size=12, color=self.blue_color, weight="bold", text_align=ft.TextAlign.CENTER)
        self.texto_proxima_prog = ft.Text("", size=12, color=self.grey_color, text_align=ft.TextAlign.CENTER)
        
        # MQTT
        self.mqtt = mqtt.ServidorMQTT()
        self.mqtt.conectar()

        # Indicador de conexión MQTT
        self.indicador_mqtt = ft.Container(
            width=16, height=16, border_radius=8,
            bgcolor=self.red_color, margin=ft.margin.only(right=6)
        )
        self.texto_mqtt = ft.Text("MQTT: Desconectado", size=12, color=self.red_color)

        # Suscribirse al estado de la placa
        self.mqtt.suscribir(self.mqtt.topico_estado, self._on_mqtt_estado)

        # Pedir estado inicial (si tu ESP32 soporta {"get":"status"})
        self.mqtt.publicar(self.mqtt.topico_cmd, json.dumps({"get": "status"}))

        # Crear la interfaz
        self.build_main_view()

        # Iniciar timer para actualizar programaciones y estado MQTT cada segundo
        self.page.run_task(self._ui_loop)
    
    def iniciar_timer_programaciones(self):
        import threading, time
        def actualizar():
            while True:
                time.sleep(1)
                if self.vista_actual == "main":
                    # ejecutar lógica en thread ok,
                    # pero la UI update siempre con call_from_thread adentro de tus funcs
                    self.evaluar_programaciones()
                    self.actualizar_estado_mqtt()
        threading.Thread(target=actualizar, daemon=True).start()
    

    def seleccionar_programacion(self, prog: dict):
        pid = prog.get("id")

        # Si clickeo la misma, alterno (toggle)
        if self.card_detalle_prog.visible and self._selected_prog_id == pid:
            self.card_detalle_prog.visible = False
            self._selected_prog_id = None
            self.page.update()
            return

        self._selected_prog_id = pid
        self.card_detalle_prog.visible = True
        self.detalle_prog_titulo.value = f"{prog.get('tipo','')}  {prog.get('nombre','')}".strip()
        self.detalle_prog_linea1.value = f"Inicio: {prog.get('inicio','')}"
        self.detalle_prog_linea2.value = f"Fin:    {prog.get('fin','')}"
        self.detalle_prog_linea3.value = (
            f"Relés: {', '.join(prog.get('targets', []))} | "
            f"Inicio: {prog.get('accion','on')} | Final: {prog.get('fin_accion','off')}"
        )
        self.page.update()
        
    def actualizar_estado_mqtt(self):
        conectado = getattr(self.mqtt, "conectado", False)
        self.indicador_mqtt.bgcolor = self.green_color if conectado else self.red_color
        self.texto_mqtt.value = "MQTT: Conectado" if conectado else "MQTT: Desconectado"
        self.texto_mqtt.color = self.green_color if conectado else self.red_color

        # placa online por "último visto"
        if self._last_seen_estado is None:
            placa_online = False
        else:
            dt = (datetime.now() - self._last_seen_estado).total_seconds()
            placa_online = dt <= self._offline_timeout_s

        if placa_online:
            self.indicador_placa.bgcolor = self.green_color
            self.texto_placa.value = "PLACA: ONLINE"
            self.texto_placa.color = self.green_color
        else:
            self.indicador_placa.bgcolor = self.red_color
            self.texto_placa.value = "PLACA: OFFLINE"
            self.texto_placa.color = self.red_color

        enabled = placa_online and conectado
        for w in self._rele_widgets.values():
            w["btn"].disabled = not enabled


    def evaluar_programaciones(self):
        """Evalúa las programaciones activas y actualiza la UI"""
        try:
            # Si está pausado, no evaluar programaciones pero mantener UI actualizada
            if self.placa_pausada:
                self.page.update()
                return

            ahora = datetime.now()

            # 1) Traer activas
            programaciones_activas = self.gestor_programaciones.obtener_programaciones_activas()

            # 2) Aplicar a relés ANTES de limpiar vencidas (así detecta terminadas y manda fin_accion)
            self._aplicar_programaciones_a_reles(programaciones_activas)

            # 3) Actualizar UI según si hay activa
            if programaciones_activas:
                prog_actual = programaciones_activas[0]
                self.programacion_activa_actual = prog_actual

                fin = datetime.strptime(prog_actual["fin"], "%Y-%m-%d %H:%M:%S")
                tiempo_restante = fin - ahora

                horas = int(tiempo_restante.total_seconds() // 3600)
                minutos = int((tiempo_restante.total_seconds() % 3600) // 60)
                segundos = int(tiempo_restante.total_seconds() % 60)

                self.texto_prog_activa.value = f"Activa: {prog_actual['tipo']} - {prog_actual.get('duracion', 'En curso')}"
                self.texto_prog_activa.color = self.green_color
                self.texto_tiempo_restante.value = f"Tiempo restante: {horas:02d}:{minutos:02d}:{segundos:02d}"

                # Activar placa automáticamente si hay programación activa y no está encendida manualmente
                if not self.placa_encendida and not self.placa_pausada:
                    self.placa_encendida = True
                    self.indicador_estado.bgcolor = self.green_color
                    self.texto_estado.value = "ENCENDIDO (AUTO)"
                    self.texto_estado.color = self.green_color
            else:
                self.programacion_activa_actual = None
                self.texto_prog_activa.value = "Ninguna programación activa"
                self.texto_prog_activa.color = self.grey_color
                self.texto_tiempo_restante.value = ""

                # Apagar placa si no hay programación activa (solo si fue AUTO)
                if self.placa_encendida and "AUTO" in self.texto_estado.value:
                    self.placa_encendida = False
                    self.indicador_estado.bgcolor = self.red_color
                    self.texto_estado.value = "APAGADO"
                    self.texto_estado.color = self.red_color

            # 4) Buscar próxima programación (esto puede quedar igual)
            todas = self.gestor_programaciones.obtener_programaciones()
            proximas = []
            for prog in todas:
                try:
                    inicio = datetime.strptime(prog["inicio"], "%Y-%m-%d %H:%M:%S")
                    if inicio > ahora and prog.get("activo", True):
                        proximas.append((inicio, prog))
                except ValueError:
                    continue

            if proximas:
                proximas.sort(key=lambda x: x[0])
                proxima_fecha, proxima_prog = proximas[0]
                tiempo_hasta = proxima_fecha - ahora

                dias = tiempo_hasta.days
                horas = int(tiempo_hasta.seconds // 3600)
                minutos = int((tiempo_hasta.seconds % 3600) // 60)

                if dias > 0:
                    self.texto_proxima_prog.value = f"Próxima: {proxima_prog['tipo']} en {dias}d {horas}h {minutos}m"
                else:
                    self.texto_proxima_prog.value = f"Próxima: {proxima_prog['tipo']} en {horas}h {minutos}m"
            else:
                self.texto_proxima_prog.value = "No hay programaciones futuras"

            # 5) Recién acá limpiar vencidas (ya se aplicó fin_accion cuando correspondía)
            vencidas = self.gestor_programaciones.limpiar_programaciones_vencidas()
            if vencidas > 0:
                print(f"Limpiadas {vencidas} programaciones vencidas")
                if self.vista_actual == "main":
                    self.build_main_view()

            self.page.update()

        except Exception as e:
            print(f"Error al evaluar programaciones: {e}")

    
    def confirmar_apagar(self, e):
        """Apaga el estado y termina la programación activa directamente, sin pop-up."""
        print("=== Botón APAGAR presionado === (sin pop-up)")
        if self.programacion_activa_actual:

            # Registrar cancelación en historial
            try:
                self._agregar_historial(evento="CANCELADA", prog=self.programacion_activa_actual)
            except Exception:
                pass
            print(f"Terminando programación activa: {self.programacion_activa_actual['tipo']}")
            self.gestor_programaciones.eliminar_programacion(self.programacion_activa_actual.get('id'))
            self.build_main_view()
        self.apagar_placa()
        self.page.update()
    
    def apagar_placa(self):
        """Apagar la placa"""
        self.placa_encendida = False
        self.placa_pausada = False
        self.tiempo_pausado_inicio = None
        self.indicador_estado.bgcolor = self.red_color
        self.texto_estado.value = "APAGADO"
        self.texto_estado.color = self.red_color
        self.page.update()
        print("Sistema apagado")
    
    def pausar_placa(self, e):
        """Pausar/Reanudar la placa"""
        if not self.placa_encendida:
            return
        
        self.placa_pausada = not self.placa_pausada
        
        if self.placa_pausada:
            # Pausar: registrar el tiempo de pausa
            self.tiempo_pausado_inicio = datetime.now()
            self.indicador_estado.bgcolor = "#FFA500"  # Naranja
            self.texto_estado.value = "PAUSADO"
            self.texto_estado.color = "#FFA500"
        else:
            # Reanudar: extender el tiempo de finalización de la programación activa
            if self.tiempo_pausado_inicio and self.programacion_activa_actual:
                tiempo_pausado = datetime.now() - self.tiempo_pausado_inicio
                
                # Extender la programación activa
                prog_id = self.programacion_activa_actual['id']
                for prog in self.gestor_programaciones.programaciones:
                    if prog.get('id') == prog_id:
                        fin_actual = datetime.strptime(prog['fin'], '%Y-%m-%d %H:%M:%S')
                        nuevo_fin = fin_actual + tiempo_pausado
                        prog['fin'] = nuevo_fin.strftime('%Y-%m-%d %H:%M:%S')
                        self.gestor_programaciones.guardar_programaciones()
                        print(f"Programación extendida por {tiempo_pausado}")
                        break
                
                self.tiempo_pausado_inicio = None
            
            self.indicador_estado.bgcolor = self.green_color
            self.texto_estado.value = "ENCENDIDO"
            self.texto_estado.color = self.green_color
        
        self.page.update()
    
    def toggle_placa(self, e):
        """Encender/Apagar manual de la placa"""
        self.placa_encendida = not self.placa_encendida
        if self.placa_encendida:
            self.placa_pausada = False
            self.indicador_estado.bgcolor = self.green_color
            self.texto_estado.value = "ENCENDIDO (MANUAL)"
            self.texto_estado.color = self.green_color
        else:
            self.indicador_estado.bgcolor = self.red_color
            self.texto_estado.value = "APAGADO"
            self.texto_estado.color = self.red_color
        self.page.update()
    
    def mostrar_vista_agregar(self, e):
        """Cambiar a la vista de agregar programación"""
        self.vista_actual = "add"

        # Setear fecha/hora por defecto en "Ahora" cada vez que abrís esta pantalla
        ahora = datetime.now()
        self.fecha_inicio.value = ahora.strftime("%Y-%m-%d")
        self.hora_inicio.value = ahora.strftime("%H:%M")
        self.fecha_fin.value = ahora.strftime("%Y-%m-%d")
        self.hora_fin.value = ahora.strftime("%H:%M")
        self.build_add_view()
        self.page.update()
    
    def volver_a_main(self, e):
        """Volver a la vista principal"""
        self.vista_actual = "main"
        self.build_main_view()
        self.page.update()
    
    def agregar_programacion_tiempo(self, e):
        try:
            horas = int(self.tiempo_horas.value or 0)
            minutos = int(self.tiempo_minutos.value or 0)
            segundos = int(self.tiempo_segundos.value or 0)

            if horas == 0 and minutos == 0 and segundos == 0:
                return

            targets = [k for k, chk in self.chk_reles.items() if chk.value]
            if not targets:
                print("No seleccionaste relés.")
                return

            total_segundos = horas * 3600 + minutos * 60 + segundos
            tiempo_inicio = datetime.now()
            tiempo_fin = tiempo_inicio + timedelta(seconds=total_segundos)

            nuevo = self.gestor_programaciones.agregar_programacion(
                tipo="Tiempo",
                inicio=tiempo_inicio.strftime("%Y-%m-%d %H:%M:%S"),
                fin=tiempo_fin.strftime("%Y-%m-%d %H:%M:%S"),
                duracion=f"{horas}h {minutos}m {segundos}s",
                activo=True,
                targets=targets,
                accion=self.accion_prog.value or "on",
                fin_accion=self.fin_accion_prog.value or "off",
            )

            # Guardar en historial (creada)
            prog_hist = nuevo if isinstance(nuevo, dict) else {
                "tipo": "Tiempo",
                "inicio": tiempo_inicio.strftime("%Y-%m-%d %H:%M:%S"),
                "fin": tiempo_fin.strftime("%Y-%m-%d %H:%M:%S"),
                "duracion": f"{horas}h {minutos}m {segundos}s",
                "targets": targets,
                "accion": self.accion_prog.value or "on",
                "fin_accion": self.fin_accion_prog.value or "off",
            }
            self._agregar_historial(evento="CREADA", prog=prog_hist)


            # limpiar
            self.tiempo_horas.value = "0"
            self.tiempo_minutos.value = "0"
            self.tiempo_segundos.value = "0"
            for chk in self.chk_reles.values():
                chk.value = False

            self.volver_a_main(None)
        except ValueError:
            pass
    
    def agregar_programacion_fecha(self, e):
        try:
            targets = [k for k, chk in self.chk_reles.items() if chk.value]
            if not targets:
                print("No seleccionaste relés.")
                return

            inicio_str = f"{self.fecha_inicio.value} {self.hora_inicio.value}"
            fin_str = f"{self.fecha_fin.value} {self.hora_fin.value}"

            # normalizar a HH:MM:SS
            if len(inicio_str) == 16:
                inicio_str += ":00"
            if len(fin_str) == 16:
                fin_str += ":00"

            nuevo = self.gestor_programaciones.agregar_programacion(
                tipo="Fecha",
                inicio=inicio_str,
                fin=fin_str,
                duracion="Por rango",
                activo=True,
                targets=targets,
                accion=self.accion_prog.value or "on",
                fin_accion=self.fin_accion_prog.value or "off",
            )

            # Guardar en historial (creada)
            prog_hist = nuevo if isinstance(nuevo, dict) else {
                "tipo": "Fecha",
                "inicio": inicio_str,
                "fin": fin_str,
                "duracion": "Por rango",
                "targets": targets,
                "accion": self.accion_prog.value or "on",
                "fin_accion": self.fin_accion_prog.value or "off",
            }
            self._agregar_historial(evento="CREADA", prog=prog_hist)


            for chk in self.chk_reles.values():
                chk.value = False

            self.volver_a_main(None)
        except ValueError:
            pass
    
    def eliminar_programacion(self, index):
        """Eliminar una programación"""
        def eliminar(e):
            
            try:
                prog = None
                todas = self.gestor_programaciones.obtener_programaciones()
                if 0 <= index < len(todas):
                    prog = todas[index]
                self._agregar_historial(evento="BORRADA", prog=prog or {"tipo":"(desconocido)"}, extra={"index": index})
            except Exception:
                pass
            self.gestor_programaciones.eliminar_por_indice(index)
            self.build_main_view()
            self.page.update()
        return eliminar
    
    def abrir_calendario_inicio(self, e):
        """Abrir selector de fecha para inicio"""
        def cambiar_fecha(e):
            if e.control.value:
                self.fecha_inicio.value = e.control.value.strftime("%Y-%m-%d")
                self.page.update()
            date_picker.open = False
            self.page.update()
            
        date_picker = ft.DatePicker(
            on_change=cambiar_fecha,
            first_date=datetime(2024, 1, 1),
            last_date=datetime(2030, 12, 31),
        )
        self.page.overlay.append(date_picker)
        date_picker.open = True
        self.page.update()
    
    def abrir_calendario_fin(self, e):
        """Abrir selector de fecha para fin"""
        def cambiar_fecha(e):
            if e.control.value:
                self.fecha_fin.value = e.control.value.strftime("%Y-%m-%d")
                self.page.update()
            date_picker.open = False
            self.page.update()
            
        date_picker = ft.DatePicker(
            on_change=cambiar_fecha,
            first_date=datetime(2024, 1, 1),
            last_date=datetime(2030, 12, 31),
        )
        self.page.overlay.append(date_picker)
        date_picker.open = True
        self.page.update()
    
    def build_main_view(self):
        """Construir la vista principal"""
        
        # Panel central con imagen y estado
        column_1 = ft.Column(
            expand=3,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                # Sección de estado
                ft.Container(
                    height=250,
                    border_radius=15,
                    bgcolor=self.dark_white,
                    padding=20,
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            # Estado del sistema (manual/auto)
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=10,
                                controls=[
                                    self.indicador_estado,
                                    self.texto_estado
                                ]
                            ),

                            # Estado de la placa (ONLINE/OFFLINE por MQTT)
                            ft.Divider(height=10, color="transparent"),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=8,
                                controls=[
                                    self.indicador_placa,
                                    self.texto_placa
                                ]
                            ),

                            ft.Divider(height=20, color="transparent"),

                            # Botones
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=10,
                                controls=[
                                    ft.ElevatedButton(
                                        "ENCENDER",
                                        icon=ft.Icons.POWER_SETTINGS_NEW,
                                        on_click=self.toggle_placa,
                                        bgcolor=self.green_color,
                                        color="white",
                                        width=120,
                                        height=50
                                    ),
                                    ft.ElevatedButton(
                                        "PAUSAR",
                                        icon=ft.Icons.PAUSE,
                                        on_click=self.pausar_placa,
                                        bgcolor="#FFA500",
                                        color="white",
                                        width=120,
                                        height=50
                                    ),
                                    ft.ElevatedButton(
                                        "APAGAR",
                                        icon=ft.Icons.POWER_OFF,
                                        on_click=self.confirmar_apagar,
                                        bgcolor=self.red_color,
                                        color="white",
                                        width=120,
                                        height=50
                                    )
                                ]
                            )
                        ]
                    )
                ),
                
                ft.Divider(height=10, color="transparent"),
                
                # Información del sistema
                ft.Row(
                    expand=True,
                    controls=[
                        ft.Container(
                                expand=True,
                                bgcolor=self.dark_white,
                                border_radius=15,
                                padding=20,
                                content=ft.Column(
                                    expand=True,
                                    alignment=ft.MainAxisAlignment.START,
                                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                    spacing=10,
                                    controls=[
                                        # lista con scroll (ocupa todo el alto del cuadro)
                                        ft.Container(
                                            expand=True,
                                            content=ft.ListView(
                                                expand=True,
                                                spacing=8,
                                                controls=self.crear_lista_reles(),
                                            ),
                                        ),
                                    ]
                                )
                            ),
                        ft.Container(
                            expand=True,
                            bgcolor=self.dark_white,
                            border_radius=15,
                            padding=20,
                            content=ft.Column(
                                alignment=ft.MainAxisAlignment.CENTER,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(name=ft.Icons.DEVICES, color=self.green_color, size=50),
                                    ft.Text("Respirómetro", weight="bold", color="black", size=18),
                                    ft.Text("CADIC", color=self.grey_color, size=14),
                                    ft.Row([
                                        self.indicador_mqtt,
                                        self.texto_mqtt
                                    ], alignment=ft.MainAxisAlignment.CENTER),
                                    
                                ]
                            )
                        ),
                    ]
                ),
                
                ft.Divider(height=10, color="transparent"),
                
                # Cuadro de información de programaciones activas
                ft.Container(
                    height=150,
                    border_radius=15,
                    bgcolor=self.dark_white,
                    padding=20,
                    border=ft.border.all(2, self.blue_color),
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.START,
                        horizontal_alignment=ft.CrossAxisAlignment.START,
                        spacing=10,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("Información de Programación", size=18, weight="bold", color="black"),
                                    ft.Icon(ft.Icons.INFO_OUTLINE, color=self.blue_color, size=24),
                                ]
                            ),
                            ft.Divider(height=1, color=self.grey_color),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE, color=self.green_color, size=20),
                                    self.texto_prog_activa,
                                ]
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.TIMER_OUTLINED, color=self.blue_color, size=20),
                                    self.texto_tiempo_restante,
                                ]
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.SCHEDULE_OUTLINED, color=self.grey_color, size=20),
                                    self.texto_proxima_prog,
                                ]
                            ),
                        ]
                    )
                )
            ]
        )
        
        # Panel derecho con programaciones
        column_2 = ft.Column(
            expand=1, spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    expand=True, border_radius=15, padding=10,
                    gradient=ft.LinearGradient(
                        rotation=math.radians(90),
                        colors=[ft.Colors.with_opacity(0.5, self.grey_color), self.dark_white, self.yellow_color]
                    ),
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("Programaciones", color="black", weight="bold"),
                                    ft.IconButton(icon=ft.Icons.REFRESH, icon_color=self.grey_color, on_click=lambda e: self.page.update())
                                ]
                            ),
                            
                            ft.Divider(height=1, color=self.grey_color),
                            
                            self.card_detalle_prog,

                            # Lista de programaciones
                            ft.Container(
                                expand=True,
                                content=ft.Column(
                                    scroll=ft.ScrollMode.AUTO,
                                    controls=self.crear_lista_programaciones()
                                )
                            ),
                            
                            # Botones Añadir e Historial
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.FilledButton(
                                        text="cfg",
                                        icon=ft.Icons.SETTINGS,
                                        width=80,
                                        style=ft.ButtonStyle(bgcolor=self.blue_color, color="white"),
                                        on_click=self.mostrar_vista_config
                                    ),
                                    ft.FilledButton(
                                        text="Añadir",
                                        icon=ft.Icons.ADD,
                                        width=100,
                                        style=ft.ButtonStyle(bgcolor="black", color="white"),
                                        on_click=self.mostrar_vista_agregar
                                    ),
                                    ft.FilledButton(
                                        text="Historial",
                                        icon=ft.Icons.HISTORY,
                                        width=100,
                                        style=ft.ButtonStyle(bgcolor=self.grey_color, color="white"),
                                        on_click=self.mostrar_vista_historial
                                    ),
                                ]
                            )
                        ]
                    )
                )
            ]
        )
        
        # Actualizar contenido
        self.content = ft.Row(
            expand=True,
            controls=[
                column_1,
                column_2,
            ]
        )
        
        if not hasattr(self.page, '_controls_added'):
            self.page.add(self)
            self.page._controls_added = True
        else:
            self.page.update()
    
    def crear_lista_programaciones(self):
        programaciones = self.gestor_programaciones.obtener_programaciones()

        if not programaciones:
            return [ft.Container(padding=20, content=ft.Text("No hay programaciones", color=self.grey_color))]

        lista = []
        for i, prog in enumerate(programaciones):
            lista.append(
                ft.Container(
                    bgcolor="white" if i % 2 == 0 else "transparent",
                    border_radius=10,
                    padding=10,
                    margin=ft.margin.only(bottom=5),
                    on_click=lambda e, p=prog: self.seleccionar_programacion(p),  # <- CLAVE
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text(prog.get("tipo",""), weight="bold", color="black", size=12),
                                    ft.Text(f"{prog.get('inicio','')[:16]}", size=10, color=self.grey_color),
                                ],
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                icon_color=self.red_color,
                                icon_size=20,
                                on_click=self.eliminar_programacion(i),
                            ),
                        ],
                    ),
                )
            )
        return lista
    
    def crear_lista_historial(self, limite: int = 30):
        items = []
        data = self._cargar_historial()
        for item in data[:limite]:
            ts = item.get("ts", "")
            evento = item.get("evento", "")
            prog = item.get("prog") or {}
            tipo = prog.get("tipo", "-")
            inicio = prog.get("inicio", "-")
            fin = prog.get("fin", "-")
            targets = prog.get("targets", [])
            accion = prog.get("accion", "-")
            fin_accion = prog.get("fin_accion", "-")

            titulo = f"{evento} • {tipo}"
            subt = f"{ts}  |  {inicio} → {fin}"
            detalle = f"Relés: {', '.join(targets) if targets else '-'}   |   Inicio: {accion}   |   Final: {fin_accion}"

            items.append(
                ft.Container(
                    bgcolor="white",
                    border_radius=12,
                    padding=12,
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text(titulo, size=14, weight=ft.FontWeight.BOLD, color="black"),
                            ft.Text(subt, size=12, color="black"),
                            ft.Text(detalle, size=12, color="black"),
                        ],
                    ),
                )
            )

        if not items:
            items.append(
                ft.Container(
                    padding=20,
                    content=ft.Text("No hay historial todavía.", color="black")
                )
            )
        return items

    def build_history_view(self):
        """Vista de historial"""
        self.content = ft.Container(
            expand=True,
            padding=20,
            bgcolor=self.bg_color,
            content=ft.Column(
                expand=True,
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.ARROW_BACK,
                                on_click=self.volver_desde_historial,
                            ),
                            ft.Text("Historial", size=26, weight=ft.FontWeight.BOLD, color="black"),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                on_click=lambda e: (setattr(self, "historial_programaciones", self._cargar_historial()), self.build_history_view(), self.page.update()),
                            ),
                        ],
                    ),
                    ft.Divider(),
                    ft.ListView(
                        expand=True,
                        spacing=10,
                        controls=self.crear_lista_historial(limite=40),
                    ),
                ],
            ),
        )


    def build_add_view(self):
        """Construir la vista para agregar programación"""
        
        # Menú lateral (mismo que main)
        menu = ft.Container(
            width=60, margin=10,
            alignment=ft.alignment.center,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(width=40, height=40, border_radius=10, bgcolor=self.dark_white,
                                content=ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="black", on_click=self.volver_a_main)
                                ),
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(width=40, height=40, border_radius=10, bgcolor=self.dark_white,
                                content=ft.IconButton(icon=ft.Icons.TIMER, icon_color="black")
                                ),
                        ]
                    ),
                ]
            )
        )
        
        # Panel central con formularios
        column_1 = ft.Column(
            expand=3,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Container(
                    padding=20,
                    content=ft.Column(
                        controls=[
                            ft.Text("Nueva Programación", size=28, weight="bold", color="black"),
                            ft.Divider(height=20, color=self.grey_color),
                            ft.Container(
                            bgcolor=self.dark_white,
                            border_radius=15,
                            padding=20,
                            content=ft.Column(
                                controls=[
                                    ft.Text("Relés a controlar", size=20, weight="bold", color="black"),
                                    ft.Text("Seleccioná uno o varios relés y la acción", size=12, color="black"),
                                    ft.Divider(height=10, color="transparent"),

                                    ft.Container(
                                        height=70,
                                        alignment=ft.alignment.center,
                                        content=ft.Row(
                                            controls=list(self.chk_reles.values()),
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            spacing=12,
                                            scroll=ft.ScrollMode.AUTO,
                                        ),
                                    ),

                                    ft.Divider(height=10, color="transparent"),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        controls=[self.accion_prog, self.fin_accion_prog],
                                    ),
                                ]
                            )
                        ),
                            # Programación por tiempo
                            ft.Container(
                                bgcolor=self.dark_white,
                                border_radius=15,
                                padding=20,
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Programación por Tiempo", size=20, weight="bold", color="black"),
                                        ft.Text("Define la duración del encendido", size=12, color="black"),
                                        ft.Divider(height=10, color="transparent"),
                                        ft.Row(
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            controls=[
                                                self.tiempo_horas,
                                                ft.Text(":", size=30, color="black"),
                                                self.tiempo_minutos,
                                                ft.Text(":", size=30, color="black"),
                                                self.tiempo_segundos,
                                            ]
                                        ),
                                        ft.Divider(height=10, color="transparent"),
                                        ft.ElevatedButton(
                                            "Guardar Programación por Tiempo",
                                            icon=ft.Icons.SAVE,
                                            on_click=self.agregar_programacion_tiempo,
                                            bgcolor=self.blue_color,
                                            color="white",
                                            width=300
                                        )
                                    ]
                                )
                            ),
                            
                            ft.Divider(height=20, color="transparent"),
                            
                            # Programación por fecha
                            ft.Container(
                                bgcolor=self.dark_white,
                                border_radius=15,
                                padding=20,
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Programación por Fecha y Hora", size=20, weight="bold", color="black"),
                                        ft.Text("Define rango de fechas y horarios", size=12, color="black"),
                                        ft.Divider(height=10, color="transparent"),
                                        
                                        # Fecha y hora de inicio
                                        ft.Text("Fecha y Hora de Inicio", weight="bold", color="black"),
                                        ft.Row(
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            controls=[
                                                self.fecha_inicio,
                                                ft.IconButton(
                                                    icon=ft.Icons.CALENDAR_TODAY,
                                                    on_click=self.abrir_calendario_inicio,
                                                    bgcolor="white",
                                                    tooltip="Seleccionar fecha de inicio"
                                                ),
                                                self.hora_inicio,
                                            ]
                                        ),
                                        
                                        ft.Divider(height=10, color="transparent"),
                                        
                                        # Fecha y hora de fin
                                        ft.Text("Fecha y Hora de Fin", weight="bold", color="black"),
                                        ft.Row(
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            controls=[
                                                self.fecha_fin,
                                                ft.IconButton(
                                                    icon=ft.Icons.CALENDAR_TODAY,
                                                    on_click=self.abrir_calendario_fin,
                                                    bgcolor="white",
                                                    tooltip="Seleccionar fecha de fin"
                                                ),
                                                self.hora_fin,
                                            ]
                                        ),
                                        
                                        ft.Divider(height=10, color="transparent"),
                                        ft.ElevatedButton(
                                            "Guardar Programación por Fecha",
                                            icon=ft.Icons.SAVE,
                                            on_click=self.agregar_programacion_fecha,
                                            bgcolor=self.green_color,
                                            color="white",
                                            width=300
                                        )
                                    ]
                                )
                            ),
                            
                            ft.Divider(height=20, color="transparent"),
                            
                            # Botón cancelar
                            ft.Container(
                                alignment=ft.alignment.center,
                                content=ft.ElevatedButton(
                                    "Cancelar",
                                    icon=ft.Icons.CANCEL,
                                    on_click=self.volver_a_main,
                                    bgcolor=self.red_color,
                                    color="white",
                                    width=200
                                )
                            )
                        ]
                    )
                )
            ]
        )
        
        # Actualizar contenido
        self.content = ft.Row(
            expand=True,
            controls=[
                menu,
                column_1,
            ]
        )
        
        self.page.update()

ft.app(target=ControlRespirometro)
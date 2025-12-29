# scheduler_daemon.py
import time
import json
from datetime import datetime

import Programaciones as PR
import ConexionMQTT as mqtt

def parse_dt(s: str) -> datetime:
    s = (s or "").strip()
    if len(s) == 16:  # YYYY-MM-DD HH:MM
        s += ":00"
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

class SchedulerDaemon:
    def __init__(self):
        self.gestor = PR.Programaciones()  # usa directorio_programaciones del Settings :contentReference[oaicite:5]{index=5}
        self.mqtt = mqtt.ServidorMQTT()    # paho + loop_start :contentReference[oaicite:6]{index=6}
        self.mqtt.conectar()

        self._prev_active_ids = set()
        self._prev_active_by_id = {}

    def _publish_cmd(self, payload: dict):
        if not getattr(self.mqtt, "conectado", False):
            self.mqtt.reconectar()
        if getattr(self.mqtt, "conectado", False):
            self.mqtt.publicar(self.mqtt.topico_cmd, json.dumps(payload), retain=False)

    def tick(self):
        # recargar por si la UI editó el json
        self.gestor.cargar_programaciones()

        activas = self.gestor.obtener_programaciones_activas()  # :contentReference[oaicite:7]{index=7}
        activas = sorted(activas, key=lambda p: parse_dt(p.get("inicio", "")))

        # desired state: lo activo “gana”
        desired = {}
        for prog in activas:
            accion = prog.get("accion", "on")
            for k in prog.get("targets", []):
                desired[k] = accion

        # detectar terminadas (para aplicar fin_accion)
        active_ids = {p.get("id") for p in activas if p.get("id")}
        ended_ids = self._prev_active_ids - active_ids

        for pid in ended_ids:
            prog = self._prev_active_by_id.get(pid) or self.gestor.obtener_programacion(pid)
            if not prog:
                continue
            fin_acc = prog.get("fin_accion", "off")
            for k in prog.get("targets", []):
                # solo aplicar fin_accion si ya no hay otra activa controlando ese relé
                if k not in desired:
                    desired[k] = fin_acc

        # publicar comandos (solo para relés involucrados)
        for k, acc in desired.items():
            self._publish_cmd({k: acc})

        # limpiar vencidas (mueve a histórico) :contentReference[oaicite:8]{index=8}
        self.gestor.limpiar_programaciones_vencidas()

        # cache
        self._prev_active_ids = active_ids
        self._prev_active_by_id = {p["id"]: p for p in activas if p.get("id")}

    def run(self):
        while True:
            try:
                self.tick()
            except Exception as e:
                print("Scheduler error:", e)
            time.sleep(1)

if __name__ == "__main__":
    SchedulerDaemon().run()

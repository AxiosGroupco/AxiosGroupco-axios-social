"""Marcador progresivo para celular Android corporativo (interfaz).
Llama uno por uno a los contactos de una lista: si no contestan, cuelga y sigue;
si contestan, no hace nada y espera a que la persona termine de hablar."""
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import motor

VERDE, ROJO, AMBAR, AZUL, GRIS = "#1b7f3b", "#b3261e", "#9a6700", "#0b57d0", "#444444"

AYUDA_CONEXION = {
    "sin_adb": ("No se encontró el componente de conexión. Vuelva a descargar la aplicación.", ROJO),
    "ninguno": ("① Conecte el celular al computador con el cable USB.\n"
                "Si ya está conectado: en el celular active la «Depuración USB» "
                "(ver la guía del celular) o pruebe otro cable o puerto.", ROJO),
    "sin_autorizar": ("② Mire la pantalla del celular: marque «Permitir siempre desde este "
                      "equipo» y toque «Permitir».", AMBAR),
    "desconectado": ("El celular no responde. Desconecte el cable y vuelva a conectarlo.", AMBAR),
    "listo": ("✔ Celular conectado y listo.", VERDE),
}
TEXTO_RESULTADO = {
    "CONTESTO": "Contestó", "POSIBLE_BUZON": "Posible buzón", "NO_CONTESTA": "No contestó",
    "NO_CONECTO": "No conectó", "ERROR_MARCADO": "Error al marcar", "COLGADO_MANUAL": "Colgada a mano",
    "OMITIDO_LEY2300": "Omitido (ya contactado)",
}


class App:
    def __init__(self, root):
        self.root = root
        root.title("Marcador Axios – llamadas una por una")
        root.geometry("900x640")
        root.minsize(760, 520)
        self.cfg = motor.cargar_config()
        self.tel = motor.Telefono(motor.preparar_adb())
        self.q = queue.Queue()
        self.contactos = []
        self.conectado, self.serial, self.trabajando = False, "", False
        self.asistido = False
        self.nota_actual = ""
        self.ev_colgar, self.ev_retener = threading.Event(), threading.Event()
        self.ev_continuar, self.pausado, self.detenido = threading.Event(), threading.Event(), threading.Event()

        est = ttk.Style()
        est.configure("Grande.TButton", font=("Segoe UI", 12, "bold"), padding=8)
        est.configure("TButton", font=("Segoe UI", 10), padding=5)
        est.configure("Treeview", rowheight=26, font=("Segoe UI", 10))

        self.l_con = tk.Label(root, text="Buscando el celular…", font=("Segoe UI", 11), fg=GRIS,
                              anchor="w", justify="left", padx=10, pady=6, wraplength=860)
        self.l_con.pack(fill="x")

        barra = ttk.Frame(root, padding=(8, 2))
        barra.pack(fill="x")
        ttk.Button(barra, text="📂 Cargar lista", command=self.cargar).pack(side="left")
        self.b_ini = ttk.Button(barra, text="▶ Iniciar llamadas", style="Grande.TButton",
                                command=self.iniciar, state="disabled")
        self.b_ini.pack(side="left", padx=6)
        self.b_pau = ttk.Button(barra, text="⏸ Pausar", command=self.pausar, state="disabled")
        self.b_pau.pack(side="left")
        ttk.Button(barra, text="⚙ Ajustes", command=self.ajustes).pack(side="right")
        ttk.Button(barra, text="📊 Ver resultados", command=self.abrir_resultados).pack(side="right", padx=6)
        ttk.Button(barra, text="Plantilla de lista", command=self.plantilla).pack(side="right")

        self.l_est = tk.Label(root, text="Cargue la lista de contactos (Excel o CSV con las columnas "
                              "nombre y telefono).", font=("Segoe UI", 15, "bold"), fg=AZUL,
                              pady=12, padx=10, wraplength=860, justify="center")
        self.l_est.pack(fill="x")

        acc = ttk.Frame(root, padding=(8, 0))
        acc.pack(fill="x")
        self.b_ret = ttk.Button(acc, text="☎ ¡Contestaron! (no colgar)", style="Grande.TButton",
                                command=self.ev_retener.set)
        self.b_col = ttk.Button(acc, text="✖ Colgar / terminé de hablar", style="Grande.TButton",
                                command=self.ev_colgar.set, state="disabled")
        self.b_col.pack(side="left")

        fn = ttk.Frame(root, padding=(8, 8))
        fn.pack(fill="x")
        ttk.Label(fn, text="Nota de la llamada:").pack(side="left")
        self.e_nota = ttk.Entry(fn, font=("Segoe UI", 11), state="disabled")
        self.e_nota.pack(side="left", fill="x", expand=True, padx=6)
        self.e_nota.bind("<Return>", lambda _: self.guardar_nota())
        self.b_sig = ttk.Button(fn, text="Guardar y llamar al siguiente ⏭", style="Grande.TButton",
                                command=self.guardar_nota, state="disabled")
        self.b_sig.pack(side="left")

        cols = ("nombre", "telefono", "resultado", "hora", "nota")
        marco = ttk.Frame(root)
        marco.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree = ttk.Treeview(marco, columns=cols, show="headings", selectmode="browse")
        for c, t, w in zip(cols, ("Nombre", "Teléfono", "Resultado", "Hora", "Nota"), (230, 110, 170, 80, 250)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        sb = ttk.Scrollbar(marco, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("ok", foreground=VERDE)
        self.tree.tag_configure("no", foreground=GRIS)
        self.tree.tag_configure("ahora", background="#fff3bf")

        root.protocol("WM_DELETE_WINDOW", self.cerrar)
        root.after(150, self.procesar_cola)
        threading.Thread(target=self.vigilar_conexion, daemon=True).start()

    # ------------------------------------------------ hilo -> interfaz
    def ui(self, fn, *a):
        self.q.put((fn, a))

    def procesar_cola(self):
        try:
            while True:
                fn, a = self.q.get_nowait()
                fn(*a)
        except queue.Empty:
            pass
        self.root.after(120, self.procesar_cola)

    def estado(self, texto, color=AZUL):
        self.l_est.config(text=texto, fg=color)

    # ------------------------------------------------ conexión con el celular (automática)
    def vigilar_conexion(self):
        anterior = None
        while not self.detenido.is_set():
            if not self.trabajando:
                est, serial = self.tel.conexion()
                if est != anterior:
                    anterior = est
                    modelo = ""
                    if est == "listo":
                        self.tel.preparar()
                        modelo = self.tel.modelo()
                    self.ui(self.mostrar_conexion, est, serial, modelo)
            time.sleep(2)

    def mostrar_conexion(self, est, serial, modelo):
        texto, color = AYUDA_CONEXION[est]
        self.conectado, self.serial = est == "listo", serial
        if self.conectado and modelo:
            texto += f"  ({modelo})"
        self.l_con.config(text=texto, fg=color)
        self.refrescar_inicio()

    def refrescar_inicio(self):
        listo = self.conectado and bool(self.contactos) and not self.trabajando
        self.b_ini.config(state="normal" if listo else "disabled")

    # ------------------------------------------------ lista
    def cargar(self):
        if self.trabajando:
            return
        ruta = filedialog.askopenfilename(title="Elija la lista de contactos",
                                          filetypes=[("Excel o CSV", "*.xlsx *.xlsm *.csv")])
        if not ruta:
            return
        try:
            self.contactos, desc = motor.leer_lista(ruta)
        except Exception as e:  # archivo dañado, abierto en Excel, sin columnas...
            messagebox.showerror("No pude leer la lista", str(e))
            return
        self.tree.delete(*self.tree.get_children())
        for i, c in enumerate(self.contactos):
            self.tree.insert("", "end", iid=str(i), values=(c["nombre"], c["telefono"], "", "", ""))
        extra = f" ({desc} filas sin teléfono válido o repetidas se omitieron)" if desc else ""
        self.estado(f"{len(self.contactos)} contactos cargados{extra}.\nPresione «Iniciar llamadas».")
        self.refrescar_inicio()

    def plantilla(self):
        ruta = os.path.join(motor.carpeta_datos(), "plantilla_lista.xlsx")
        try:
            motor.crear_plantilla(ruta)
            os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("Plantilla", f"No se pudo crear la plantilla:\n{e}")

    def abrir_resultados(self):
        try:
            os.startfile(motor.ruta_log() if os.path.exists(motor.ruta_log()) else motor.carpeta_datos())
        except Exception as e:
            messagebox.showerror("Resultados", str(e))

    def ajustes(self):
        if self.trabajando:
            messagebox.showinfo("Ajustes", "Pause o termine las llamadas antes de cambiar los ajustes.")
            return
        v = tk.Toplevel(self.root)
        v.title("Ajustes")
        v.transient(self.root)
        v.grab_set()
        f = ttk.Frame(v, padding=14)
        f.pack()
        timbre = tk.IntVar(value=self.cfg["timbre_max_s"])
        cobr = tk.BooleanVar(value=self.cfg["cobranza"])
        modo = tk.StringVar(value=self.cfg["modo"].get(self.serial, "auto"))
        ttk.Label(f, text="Segundos de timbre antes de pasar al siguiente:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(f, from_=10, to=60, textvariable=timbre, width=5).grid(row=0, column=1, padx=8)
        ttk.Checkbutton(f, text="Llamadas de cobranza: no repetir en la misma semana a quien ya contestó "
                        "(Ley 2300)", variable=cobr).grid(row=1, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(f, text="Detección de «contestaron»:").grid(row=2, column=0, sticky="w")
        ttk.Combobox(f, textvariable=modo, values=("auto", "asistido"), state="readonly",
                     width=10).grid(row=2, column=1, padx=8)
        ttk.Label(f, text="auto: el programa detecta solo cuando contestan.\nasistido: usted presiona "
                  "«¡Contestaron!» al oír que contestan.", foreground=GRIS).grid(row=3, column=0, columnspan=2,
                                                                               sticky="w", pady=(4, 10))

        def guardar():
            try:
                self.cfg["timbre_max_s"] = max(10, min(60, int(timbre.get())))
            except (tk.TclError, ValueError):
                pass
            self.cfg["cobranza"] = bool(cobr.get())
            if self.serial:
                self.cfg["modo"][self.serial] = modo.get()
            motor.guardar_config(self.cfg)
            v.destroy()
        ttk.Button(f, text="Guardar", command=guardar).grid(row=4, column=0, columnspan=2)

    # ------------------------------------------------ control
    def iniciar(self):
        if not motor.horario_permitido():
            messagebox.showwarning("Fuera de horario", "La Ley 2300 solo permite llamar de lunes a viernes "
                                   "de 7:00 a.m. a 7:00 p.m. y sábados de 8:00 a.m. a 3:00 p.m. "
                                   "No se llama domingos ni festivos.")
            return
        sel = self.tree.selection()
        desde = int(sel[0]) if sel else 0
        if desde and not messagebox.askyesno("Iniciar", f"¿Empezar desde «{self.contactos[desde]['nombre']}» "
                                             "(la fila seleccionada)?\n\n«No» empieza desde el principio."):
            desde = 0
        self.asistido = self.cfg["modo"].get(self.serial) == "asistido"
        self.trabajando = True
        self.pausado.clear()
        self.b_ini.config(state="disabled")
        self.b_pau.config(state="normal", text="⏸ Pausar")
        self.b_col.config(state="normal")
        self.mostrar_boton_asistido()
        threading.Thread(target=self.trabajar, args=(desde,), daemon=True).start()

    def mostrar_boton_asistido(self):
        if self.asistido and self.trabajando:
            self.b_ret.pack(side="left", padx=(0, 8), before=self.b_col)
        else:
            self.b_ret.pack_forget()

    def pasar_a_asistido(self):
        self.asistido = True
        if self.serial:
            self.cfg["modo"][self.serial] = "asistido"
            motor.guardar_config(self.cfg)
        self.mostrar_boton_asistido()
        self.root.bell()
        self.estado("Este celular no avisa cuándo contestan.\nCuando OIGA que contestan, presione "
                    "«¡Contestaron!» para que no se cuelgue.", AMBAR)

    def pausar(self):
        if self.pausado.is_set():
            self.pausado.clear()
            self.b_pau.config(text="⏸ Pausar")
        else:
            self.pausado.set()
            self.b_pau.config(text="▶ Reanudar")

    def pedir_nota(self, c):
        self.estado(f"Llamada con {c['nombre']} terminada.\nEscriba una nota (opcional) y presione "
                    "«Guardar y llamar al siguiente».", AZUL)
        self.e_nota.config(state="normal")
        self.b_sig.config(state="normal")
        self.e_nota.focus()
        self.root.bell()

    def guardar_nota(self):
        if str(self.b_sig["state"]) == "disabled":
            return
        self.nota_actual = self.e_nota.get().strip()
        self.e_nota.delete(0, "end")
        self.e_nota.config(state="disabled")
        self.b_sig.config(state="disabled")
        self.ev_continuar.set()

    def marcar_fila(self, i, resultado="", hora="", nota="", tag="ahora"):
        c = self.contactos[i]
        self.tree.item(str(i), values=(c["nombre"], c["telefono"], resultado, hora, nota), tags=(tag,))
        self.tree.see(str(i))

    def fin_trabajo(self, texto, color=VERDE):
        self.trabajando = False
        self.b_pau.config(state="disabled")
        self.b_col.config(state="disabled")
        self.mostrar_boton_asistido()
        self.estado(texto, color)
        self.refrescar_inicio()
        self.root.bell()

    def cerrar(self):
        if self.trabajando and not messagebox.askyesno("Salir", "Hay llamadas en curso. ¿Cerrar de todos modos?"):
            return
        self.detenido.set()
        self.ev_continuar.set()
        if self.trabajando:
            self.tel.colgar()
        threading.Thread(target=self.tel.apagar_servidor, daemon=True).start()
        self.root.after(400, self.root.destroy)

    # ------------------------------------------------ hilo de trabajo
    def trabajar(self, desde):
        total = len(self.contactos)
        for i in range(desde, total):
            c = self.contactos[i]
            avisado = False
            while self.pausado.is_set() and not self.detenido.is_set():
                if not avisado:
                    avisado = True
                    self.ui(self.estado, "En pausa. Presione «Reanudar» para seguir llamando.", GRIS)
                time.sleep(0.3)
            if self.detenido.is_set():
                return
            if not motor.horario_permitido():
                self.ui(self.fin_trabajo, "Se acabó el horario permitido para llamar (Ley 2300).\n"
                        "Mañana puede continuar seleccionando la fila donde quedó.", ROJO)
                return
            if self.tel.conexion()[0] != "listo":
                self.ui(self.fin_trabajo, "Se perdió la conexión con el celular. Revise el cable y "
                        "vuelva a presionar «Iniciar llamadas».", ROJO)
                return
            hora = time.strftime("%H:%M")
            if self.cfg["cobranza"] and motor.contactado_esta_semana(c["telefono"]):
                motor.registrar(c["nombre"], c["telefono"], "OMITIDO_LEY2300", "Contacto efectivo previo esta semana")
                self.ui(self.marcar_fila, i, TEXTO_RESULTADO["OMITIDO_LEY2300"], hora, "", "no")
                continue

            self.ui(self.marcar_fila, i, "Llamando…", hora)
            self.ui(self.estado, f"[{i + 1} de {total}]  Llamando a {c['nombre']}\n{c['telefono']}")
            res, self.asistido = motor.una_llamada(
                self.tel, c["telefono"], self.cfg["timbre_max_s"], self.ev_colgar, self.ev_retener,
                asistido=self.asistido,
                al_cambiar=lambda e: self.ui(self.pasar_a_asistido) if e == "ASISTIDO" else None)
            nota = ""
            if res in motor.EFECTIVOS:
                if res == "CONTESTO":
                    self.ui(self.estado, f"☎  CONTESTÓ {c['nombre']}\nHable con calma. Al terminar, cuelgue "
                            "en el celular o presione «Colgar».", VERDE)
                else:
                    self.ui(self.estado, f"⚠  {c['nombre']}: parece BUZÓN DE VOZ\nSi es buzón presione "
                            "«Colgar». Si es una persona, hable normalmente.", AMBAR)
                self.ui(self.root.bell)
                self.ev_colgar.clear()
                motor.esperar_fin(self.tel, self.ev_colgar, self.detenido)
                if self.detenido.is_set():
                    return
                self.ev_continuar.clear()
                self.ui(self.pedir_nota, c)
                self.ev_continuar.wait()
                if self.detenido.is_set():
                    return
                nota = self.nota_actual
            motor.registrar(c["nombre"], c["telefono"], res, nota)
            self.ui(self.marcar_fila, i, TEXTO_RESULTADO.get(res, res), hora, nota,
                    "ok" if res == "CONTESTO" else "no")
            time.sleep(self.cfg["pausa_s"])
        self.ui(self.fin_trabajo, "✅ Lista terminada. Presione «Ver resultados» para abrir el registro.")


def main():
    root = tk.Tk()
    app = App(root)
    if "--autotest" in sys.argv:  # prueba de humo del .exe: abre, dibuja y cierra
        root.update()
        app.detenido.set()
        app.tel.apagar_servidor()
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()

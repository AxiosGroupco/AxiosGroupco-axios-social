"""Marcador Axios: marcador progresivo para celular Android corporativo (interfaz).
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

# ---------------------------------------------------------------- estilo (colores de la marca)
NAVY, NAVY2, TEAL, TEAL_H, CELESTE = "#0b1f33", "#16324f", "#13808a", "#0f6a73", "#4fc3cf"
ROJO, ROJO_H, VERDE, VERDE_H, AMBAR = "#c8102e", "#a50d26", "#1b7f3b", "#166a31", "#8a5a00"
FONDO, TARJETA, BORDE, TEXTO, SUAVE = "#f1f5f9", "#ffffff", "#e2e8f0", "#0b1f33", "#64748b"
F = "Segoe UI"
TONOS = {  # fondo y color del título del panel principal
    "neutro": (TARJETA, TEXTO), "info": ("#e9f5f6", TEAL), "ok": ("#e3f5e9", VERDE),
    "alerta": ("#fff4d6", AMBAR), "error": ("#fde8ea", ROJO), "pausa": ("#eef2f6", SUAVE),
}
BOTONES = {  # tipo: (fondo, fondo al pasar el ratón, texto)
    "pri": (TEAL, TEAL_H, "#ffffff"), "peligro": (ROJO, ROJO_H, "#ffffff"), "ok": (VERDE, VERDE_H, "#ffffff"),
    "sec": ("#dfe7ef", "#cbd5e1", TEXTO), "cab": (NAVY2, "#1f4468", "#ffffff"),
}

ESTADO_CONEXION = {  # estado: (texto corto del encabezado, color, ayuda)
    "sin_adb": ("● Falta un componente", "#ff9a9a",
                "No se encontró el componente de conexión. Vuelva a descargar la aplicación."),
    "ninguno": ("● Celular sin conectar", "#ff9a9a",
                "Conecte el celular al computador con el cable USB. Si ya está conectado: active la "
                "«Depuración USB» en el celular (botón Ayuda, paso 2) o pruebe otro cable o puerto."),
    "sin_autorizar": ("● Falta un permiso en el celular", "#fbbf24",
                      "Mire la pantalla del celular: marque «Permitir siempre desde este equipo» y "
                      "toque «Permitir»."),
    "desconectado": ("● El celular no responde", "#fbbf24",
                     "Desconecte el cable USB y vuelva a conectarlo."),
    "listo": ("● Celular conectado", "#6ee7a0", ""),
}
TEXTO_RESULTADO = {
    "CONTESTO": "Contestó", "POSIBLE_BUZON": "Posible buzón", "NO_CONTESTA": "No contestó",
    "NO_CONECTO": "No conectó", "ERROR_MARCADO": "Error al marcar", "COLGADO_MANUAL": "Colgada a mano",
    "OMITIDO_LEY2300": "Omitido (ya contactado)",
}

TUTORIAL = [
    ("Bienvenida", "Marcador Axios llama por usted, uno por uno, a los contactos de una lista usando "
     "el celular conectado al computador.\n\n"
     "•  Si NO contestan, cuelga y llama al siguiente.\n"
     "•  Si contestan, no hace nada: usted habla con calma y el programa espera.\n\n"
     "Este recorrido explica cada botón. Puede volver a verlo cuando quiera con el botón «Ayuda»."),
    ("Paso 1 · Preparar el celular (una sola vez)",
     "1.  Ajustes → Acerca del teléfono → toque 7 veces «Número de compilación».\n"
     "2.  Ajustes → Sistema → Opciones de desarrollador → active «Depuración USB».\n"
     "     En Xiaomi/Redmi/POCO active también «Depuración USB (ajustes de seguridad)».\n"
     "3.  Si tiene dos SIM, deje la corporativa como predeterminada para llamadas.\n"
     "4.  Conecte los audífonos al celular (no al computador)."),
    ("Paso 2 · Conectar el celular",
     "Conecte el celular con el cable USB y desbloquéelo.\n\n"
     "La primera vez el celular pregunta «¿Permitir depuración USB?»: marque «Permitir siempre "
     "desde este equipo» y toque «Permitir».\n\n"
     "Arriba a la derecha debe aparecer en verde «● Celular conectado». Si aparece en rojo o "
     "amarillo, la franja de abajo le dice exactamente qué hacer."),
    ("Paso 3 · Botón «Cargar lista»",
     "Elija el archivo de Excel (o CSV) con sus contactos. La primera fila debe tener los títulos:\n\n"
     "          nombre     |     telefono\n\n"
     "•  «Plantilla de lista» (abajo) crea un Excel de ejemplo listo para llenar.\n"
     "•  Los teléfonos repetidos o mal escritos se omiten solos.\n"
     "•  Los contactos aparecen en la tabla de la parte inferior."),
    ("Paso 4 · Botón «Iniciar llamadas»",
     "El programa empieza a llamar desde el primer contacto.\n\n"
     "•  Para continuar una lista a medias, haga clic en la fila donde quedó y luego presione "
     "«Iniciar llamadas».\n"
     "•  La barra de avance muestra cuántos lleva y cuántos contestaron.\n"
     "•  Si nadie contesta en el tiempo de timbre, cuelga y sigue solo con el siguiente."),
    ("Paso 5 · Cuando contestan",
     "Suena un aviso y el panel se pone VERDE con el nombre de la persona.\n\n"
     "•  Hable normalmente por los audífonos: el programa no hace nada mientras tanto.\n"
     "•  Al terminar, cuelgue en el celular o presione «Colgar».\n"
     "•  Si la nota está activada, escriba el detalle de la llamada y presione «Guardar y llamar "
     "al siguiente». Si está desactivada, el programa sigue solo.\n"
     "•  Panel AMARILLO «parece buzón de voz»: si es buzón presione «Colgar»; si es una persona, hable."),
    ("Paso 6 · Botones durante las llamadas",
     "⏸ Pausar / ▶ Reanudar\n"
     "     Detiene el marcado al terminar la llamada actual (para un descanso). Reanudar continúa.\n\n"
     "✖ Colgar\n"
     "     Cuelga la llamada actual: úsela al terminar de hablar o para saltar un número.\n\n"
     "☎ ¡Contestaron!\n"
     "     Solo aparece si su celular no avisa cuándo contestan. Presiónelo apenas oiga que "
     "contestan, para que el programa no cuelgue."),
    ("Paso 7 · Resultados",
     "«Ver resultados» abre en Excel el registro de todas las llamadas (queda en "
     "Documentos › MarcadorAxios).\n\n"
     "En la tabla verá el resultado de cada contacto:\n"
     "•  Contestó: se habló con la persona.\n"
     "•  No contestó: timbró y nadie respondió.\n"
     "•  No conectó: ocupado, apagado, rechazada o número errado.\n"
     "•  Posible buzón: contestó sin timbrar.\n"
     "•  Omitido: ya se había hablado con esa persona esta semana."),
    ("Paso 8 · Ajustes y horario",
     "En «Ajustes» puede cambiar:\n"
     "•  Los segundos de timbre antes de pasar al siguiente.\n"
     "•  Si quiere escribir una nota al terminar cada llamada.\n"
     "•  Si son llamadas de cobranza (no repite en la semana a quien ya contestó).\n\n"
     "Horario permitido por la Ley 2300: lunes a viernes de 7:00 a.m. a 7:00 p.m. y sábados de "
     "8:00 a.m. a 3:00 p.m. Domingos y festivos el programa no llama.\n\n"
     "¡Listo! Ya puede empezar."),
]


def recurso(nombre):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "recursos", nombre)


class Boton(tk.Button):
    """Botón plano con los colores de la marca y efecto al pasar el ratón."""

    def __init__(self, padre, texto, comando, tipo="sec", grande=False, **kw):
        self.c_fondo, self.c_hover, self.c_texto = BOTONES[tipo]
        super().__init__(padre, text=texto, command=comando, relief="flat", bd=0, cursor="hand2",
                         font=(F, 12 if grande else 10, "bold"), padx=18 if grande else 12,
                         pady=10 if grande else 6, bg=self.c_fondo, fg=self.c_texto,
                         activebackground=self.c_hover, activeforeground=self.c_texto,
                         disabledforeground="#f8fafc", highlightthickness=0, **kw)
        self.bind("<Enter>", lambda _: self._pintar(self.c_hover))
        self.bind("<Leave>", lambda _: self._pintar(self.c_fondo))

    def _pintar(self, color):
        if str(self["state"]) != "disabled":
            self.config(bg=color)

    def activo(self, si=True):
        self.config(state="normal" if si else "disabled", bg=self.c_fondo if si else "#c3ccd6",
                    cursor="hand2" if si else "arrow")


class App:
    def __init__(self, root, vigilar=True):
        self.root = root
        root.title("Marcador Axios")
        root.geometry("980x700")
        root.minsize(860, 600)
        root.configure(bg=FONDO)
        self.cfg = motor.cargar_config()
        self.tel = motor.Telefono(motor.preparar_adb())
        self.q = queue.Queue()
        self.contactos = []
        self.conectado, self.serial, self.trabajando = False, "", False
        self.asistido = False
        self.nota_actual = ""
        self.hechos = self.contestaron = 0
        self.ev_colgar, self.ev_retener = threading.Event(), threading.Event()
        self.ev_continuar, self.pausado, self.detenido = threading.Event(), threading.Event(), threading.Event()
        self._iconos()
        self._estilos()
        self._encabezado()
        self._cuerpo()
        self.estado("Cargue la lista de contactos",
                    "Presione «Cargar lista» y elija el Excel con las columnas nombre y telefono.")
        root.protocol("WM_DELETE_WINDOW", self.cerrar)
        root.after(150, self.procesar_cola)
        if vigilar:
            threading.Thread(target=self.vigilar_conexion, daemon=True).start()
            if not self.cfg.get("tutorial_visto"):
                root.after(500, self.tutorial)

    # ------------------------------------------------ construcción de la ventana
    def _iconos(self):
        self.img_logo = self.img_logo_g = None
        try:
            self.img_logo = tk.PhotoImage(file=recurso("icono_44.png"))
            self.img_logo_g = tk.PhotoImage(file=recurso("icono_96.png"))
            if os.name == "nt":
                self.root.iconbitmap(default=recurso("icono.ico"))
            else:
                self.root.iconphoto(True, self.img_logo_g)
        except tk.TclError:
            pass  # sin iconos la aplicación funciona igual

    def _estilos(self):
        est = ttk.Style()
        est.theme_use("clam")
        est.configure("Treeview", rowheight=30, font=(F, 10), background=TARJETA, fieldbackground=TARJETA,
                      foreground=TEXTO, borderwidth=0)
        est.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # sin borde oscuro
        est.configure("Treeview.Heading", font=(F, 10, "bold"), background="#dfe7ef", foreground=TEXTO,
                      relief="flat", padding=6)
        est.map("Treeview", background=[("selected", "#bfe6eb")], foreground=[("selected", TEXTO)])
        est.map("Treeview.Heading", background=[("active", "#cbd5e1")])
        est.configure("Avance.Horizontal.TProgressbar", troughcolor=BORDE, background=TEAL,
                      bordercolor=BORDE, lightcolor=TEAL, darkcolor=TEAL, thickness=10)
        est.configure("Vertical.TScrollbar", background="#dfe7ef", troughcolor=FONDO, bordercolor=FONDO,
                      arrowcolor=SUAVE)
        est.configure("TCheckbutton", background=TARJETA, foreground=TEXTO, font=(F, 10))
        est.map("TCheckbutton", background=[("active", TARJETA)])
        est.configure("TSpinbox", padding=4)
        est.configure("TCombobox", padding=4)

    def _encabezado(self):
        cab = tk.Frame(self.root, bg=NAVY)
        cab.pack(fill="x")
        if self.img_logo:
            tk.Label(cab, image=self.img_logo, bg=NAVY).pack(side="left", padx=(16, 10), pady=10)
        tit = tk.Frame(cab, bg=NAVY)
        tit.pack(side="left", pady=10, padx=(0 if self.img_logo else 16, 0))
        tk.Label(tit, text="Marcador Axios", font=(F, 16, "bold"), fg="#ffffff", bg=NAVY).pack(anchor="w")
        tk.Label(tit, text="Llamadas una por una, sin marcar a mano", font=(F, 9), fg="#a9b8c9",
                 bg=NAVY).pack(anchor="w")
        Boton(cab, "⚙  Ajustes", self.ajustes, "cab").pack(side="right", padx=(6, 16))
        Boton(cab, "?  Ayuda", self.tutorial, "cab").pack(side="right")
        self.l_con = tk.Label(cab, text="● Buscando el celular…", font=(F, 10, "bold"), fg="#a9b8c9", bg=NAVY)
        self.l_con.pack(side="right", padx=16)
        # franja de ayuda: solo se ve cuando falta algo para conectar el celular
        self.f_aviso = tk.Frame(self.root, bg="#fff4d6")
        self.l_aviso = tk.Label(self.f_aviso, text="", font=(F, 10), fg="#5c3d00", bg="#fff4d6",
                                justify="left", anchor="w", padx=18, pady=8, wraplength=920)
        self.l_aviso.pack(fill="x")

    def _cuerpo(self):
        self.cuerpo = cuerpo = tk.Frame(self.root, bg=FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=14)

        # panel principal: qué está pasando ahora
        self.panel = tk.Frame(cuerpo, bg=TARJETA, highlightthickness=1, highlightbackground=BORDE)
        self.panel.pack(fill="x")
        self.l_tit = tk.Label(self.panel, font=(F, 20, "bold"), bg=TARJETA, fg=TEXTO, wraplength=900)
        self.l_tit.pack(pady=(18, 2), padx=16)
        self.l_det = tk.Label(self.panel, font=(F, 11), bg=TARJETA, fg="#334155", wraplength=880, justify="center")
        self.l_det.pack(pady=(0, 12), padx=16)
        self.f_av = tk.Frame(self.panel, bg=TARJETA)
        self.f_av.pack(fill="x", padx=24, pady=(0, 16))
        self.barra = ttk.Progressbar(self.f_av, style="Avance.Horizontal.TProgressbar", maximum=1, value=0)
        self.barra.pack(fill="x")
        self.l_av = tk.Label(self.f_av, text="", font=(F, 9), bg=TARJETA, fg=SUAVE)
        self.l_av.pack(anchor="e", pady=(4, 0))

        # botones de acción
        self.f_acc = acc = tk.Frame(cuerpo, bg=FONDO)
        acc.pack(fill="x", pady=12)
        self.b_car = Boton(acc, "Cargar lista", self.cargar, "sec", grande=True)
        self.b_car.pack(side="left")
        self.b_ini = Boton(acc, "▶  Iniciar llamadas", self.iniciar, "pri", grande=True)
        self.b_ini.pack(side="left", padx=10)
        self.b_pau = Boton(acc, "⏸  Pausar", self.pausar, "sec", grande=True)
        self.b_pau.pack(side="left")
        self.b_col = Boton(acc, "✖  Colgar", self.ev_colgar.set, "peligro", grande=True)
        self.b_col.pack(side="right")
        self.b_ret = Boton(acc, "☎  ¡Contestaron!", self.ev_retener.set, "ok", grande=True)
        for b in (self.b_ini, self.b_pau, self.b_col):
            b.activo(False)

        # nota de la llamada: solo aparece cuando se pide
        self.f_nota = tk.Frame(cuerpo, bg="#e9f5f6", highlightthickness=1, highlightbackground=CELESTE,
                               highlightcolor=CELESTE)
        tk.Label(self.f_nota, text="Nota de la llamada (opcional):", font=(F, 10, "bold"), bg="#e9f5f6",
                 fg=TEXTO).pack(side="left", padx=(12, 8), pady=10)
        self.e_nota = tk.Entry(self.f_nota, font=(F, 12), relief="flat", highlightthickness=1,
                               highlightbackground=BORDE, highlightcolor=TEAL)
        self.e_nota.pack(side="left", fill="x", expand=True, ipady=5)
        self.e_nota.bind("<Return>", lambda _: self.guardar_nota())
        Boton(self.f_nota, "Guardar y llamar al siguiente  ⏭", self.guardar_nota, "pri").pack(side="left", padx=12)

        # pie
        pie = tk.Frame(cuerpo, bg=FONDO)
        pie.pack(side="bottom", fill="x", pady=(10, 0))
        Boton(pie, "Ver resultados", self.abrir_resultados).pack(side="left")
        Boton(pie, "Plantilla de lista", self.plantilla).pack(side="left", padx=8)
        tk.Label(pie, text="Horario permitido (Ley 2300):  L–V 7:00 a 19:00  ·  Sáb 8:00 a 15:00  ·  "
                 "domingos y festivos no", font=(F, 9), bg=FONDO, fg=SUAVE).pack(side="right")

        # tabla de contactos
        marco = tk.Frame(cuerpo, bg=TARJETA, highlightthickness=1, highlightbackground=BORDE)
        marco.pack(fill="both", expand=True)
        cols = ("n", "nombre", "telefono", "resultado", "hora", "nota")
        self.tree = ttk.Treeview(marco, columns=cols, show="headings", selectmode="browse")
        for c, t, w, a in zip(cols, ("#", "Nombre", "Teléfono", "Resultado", "Hora", "Nota"),
                              (44, 230, 120, 170, 70, 260), ("center", "w", "w", "w", "center", "w")):
            self.tree.heading(c, text=t, anchor=a)
            self.tree.column(c, width=w, anchor=a, stretch=c in ("nombre", "nota"))
        sb = ttk.Scrollbar(marco, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("par", background="#f6f9fc")
        self.tree.tag_configure("ok", foreground=VERDE)
        self.tree.tag_configure("no", foreground=SUAVE)
        self.tree.tag_configure("ahora", background="#fff1b8")

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

    def estado(self, titulo, detalle="", tono="neutro"):
        fondo, color = TONOS[tono]
        for w in (self.panel, self.l_tit, self.l_det, self.f_av, self.l_av):
            w.config(bg=fondo)
        self.l_tit.config(text=titulo, fg=color)
        self.l_det.config(text=detalle)

    def avance(self):
        total = len(self.contactos)
        self.barra.config(maximum=max(total, 1), value=self.hechos)
        self.l_av.config(text=f"{self.hechos} de {total} llamados   ·   {self.contestaron} contestaron"
                         if total else "")

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

    def mostrar_conexion(self, est, serial, modelo=""):
        corto, color, ayuda = ESTADO_CONEXION[est]
        self.conectado, self.serial = est == "listo", serial
        self.l_con.config(text=corto + (f"  ·  {modelo}" if self.conectado and modelo else ""), fg=color)
        if ayuda:
            self.l_aviso.config(text=ayuda)
            self.f_aviso.pack(fill="x", before=self.cuerpo)
        else:
            self.f_aviso.pack_forget()
        self.refrescar_inicio()

    def refrescar_inicio(self):
        self.b_ini.activo(self.conectado and bool(self.contactos) and not self.trabajando)
        self.b_car.activo(not self.trabajando)

    # ------------------------------------------------ lista
    def cargar(self):
        if self.trabajando:
            return
        ruta = filedialog.askopenfilename(title="Elija la lista de contactos",
                                          filetypes=[("Excel o CSV", "*.xlsx *.xlsm *.csv")])
        if not ruta:
            return
        try:
            contactos, desc = motor.leer_lista(ruta)
        except Exception as e:  # archivo dañado, abierto en Excel, sin columnas...
            messagebox.showerror("No pude leer la lista", str(e))
            return
        self.poner_lista(contactos, desc)

    def poner_lista(self, contactos, desc=0):
        self.contactos = contactos
        self.hechos = self.contestaron = 0
        self.tree.delete(*self.tree.get_children())
        for i, c in enumerate(contactos):
            self.tree.insert("", "end", iid=str(i), values=(i + 1, c["nombre"], c["telefono"], "", "", ""),
                             tags=self._zebra(i))
        extra = f"  ({desc} filas sin teléfono válido o repetidas se omitieron.)" if desc else ""
        self.estado(f"{len(contactos)} contactos listos", "Presione «Iniciar llamadas» para empezar." + extra)
        self.avance()
        self.refrescar_inicio()

    @staticmethod
    def _zebra(i):
        return ("par",) if i % 2 else ()

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

    # ------------------------------------------------ ventanas secundarias
    def _ventana(self, titulo, subtitulo=""):
        v = tk.Toplevel(self.root, bg=TARJETA)
        v.title(titulo)
        v.transient(self.root)
        v.resizable(False, False)
        cab = tk.Frame(v, bg=NAVY)
        cab.pack(fill="x")
        if self.img_logo:
            tk.Label(cab, image=self.img_logo, bg=NAVY).pack(side="left", padx=(16, 10), pady=10)
        t = tk.Frame(cab, bg=NAVY)
        t.pack(side="left", pady=10, padx=(0, 20))
        tk.Label(t, text=titulo, font=(F, 14, "bold"), fg="#ffffff", bg=NAVY).pack(anchor="w")
        l_sub = tk.Label(t, text=subtitulo, font=(F, 9), fg="#a9b8c9", bg=NAVY)
        l_sub.pack(anchor="w")
        return v, l_sub

    def ajustes(self):
        if self.trabajando:
            messagebox.showinfo("Ajustes", "Pause o termine las llamadas antes de cambiar los ajustes.")
            return
        v, _ = self._ventana("Ajustes", "Se guardan para la próxima vez")
        f = tk.Frame(v, bg=TARJETA, padx=22, pady=16)
        f.pack()
        timbre = tk.IntVar(value=self.cfg["timbre_max_s"])
        nota = tk.BooleanVar(value=self.cfg["pedir_nota"])
        cobr = tk.BooleanVar(value=self.cfg["cobranza"])
        modo = tk.StringVar(value=self.cfg["modo"].get(self.serial, "auto"))

        def titulo(txt, fila):
            tk.Label(f, text=txt, font=(F, 10, "bold"), bg=TARJETA, fg=TEXTO).grid(
                row=fila, column=0, columnspan=2, sticky="w", pady=(12, 2))

        def ayuda(txt, fila):
            tk.Label(f, text=txt, font=(F, 9), bg=TARJETA, fg=SUAVE, justify="left", wraplength=430).grid(
                row=fila, column=0, columnspan=2, sticky="w", padx=(24, 0))

        titulo("Tiempo de timbre", 0)
        tk.Label(f, text="Segundos que deja timbrar antes de pasar al siguiente:", font=(F, 10), bg=TARJETA,
                 fg=TEXTO).grid(row=1, column=0, sticky="w")
        ttk.Spinbox(f, from_=10, to=60, textvariable=timbre, width=5, font=(F, 10)).grid(row=1, column=1, padx=8)
        titulo("Al terminar cada llamada contestada", 2)
        ttk.Checkbutton(f, text="Pedir una nota o detalle de la llamada", variable=nota).grid(
            row=3, column=0, columnspan=2, sticky="w")
        ayuda("Activado: espera a que escriba la nota y presione «Guardar y llamar al siguiente».\n"
              "Desactivado: sigue solo con el siguiente contacto a los pocos segundos.", 4)
        titulo("Cumplimiento (Ley 2300)", 5)
        ttk.Checkbutton(f, text="Son llamadas de cobranza", variable=cobr).grid(
            row=6, column=0, columnspan=2, sticky="w")
        ayuda("No vuelve a llamar en la misma semana a quien ya contestó.", 7)
        titulo("Detección de «contestaron»", 8)
        ttk.Combobox(f, textvariable=modo, values=("auto", "asistido"), state="readonly", width=10,
                     font=(F, 10)).grid(row=9, column=0, sticky="w", padx=(24, 0))
        ayuda("auto: el programa detecta solo cuando contestan.\n"
              "asistido: usted presiona «¡Contestaron!» al oír que contestan.", 10)

        def guardar():
            try:
                self.cfg["timbre_max_s"] = max(10, min(60, int(timbre.get())))
            except (tk.TclError, ValueError):
                pass
            self.cfg["pedir_nota"] = bool(nota.get())
            self.cfg["cobranza"] = bool(cobr.get())
            if self.serial:
                self.cfg["modo"][self.serial] = modo.get()
            motor.guardar_config(self.cfg)
            v.destroy()

        pie = tk.Frame(v, bg=TARJETA, padx=22, pady=14)
        pie.pack(fill="x")
        Boton(pie, "Guardar", guardar, "pri").pack(side="right")
        Boton(pie, "Cancelar", v.destroy).pack(side="right", padx=8)
        v.grab_set()
        return v

    def tutorial(self, pagina=0):
        v, l_sub = self._ventana("Cómo usar Marcador Axios")
        cuerpo = tk.Frame(v, bg=TARJETA, padx=26, pady=18, width=640, height=330)
        cuerpo.pack()
        cuerpo.pack_propagate(False)
        l_tit = tk.Label(cuerpo, font=(F, 15, "bold"), bg=TARJETA, fg=TEAL, anchor="w", justify="left",
                         wraplength=590)
        l_tit.pack(fill="x")
        l_txt = tk.Label(cuerpo, font=(F, 11), bg=TARJETA, fg=TEXTO, anchor="nw", justify="left", wraplength=590)
        l_txt.pack(fill="both", expand=True, pady=(10, 0))
        pie = tk.Frame(v, bg=FONDO, padx=22, pady=12)
        pie.pack(fill="x")
        l_puntos = tk.Label(pie, font=(F, 12), bg=FONDO, fg=TEAL)
        l_puntos.pack(side="left")
        pos = {"i": pagina}

        def cerrar():
            if not self.cfg.get("tutorial_visto"):
                self.cfg["tutorial_visto"] = True
                motor.guardar_config(self.cfg)
            v.destroy()

        def mostrar(delta=0):
            if pos["i"] + delta >= len(TUTORIAL):
                return cerrar()
            pos["i"] = max(0, pos["i"] + delta)
            i = pos["i"]
            l_tit.config(text=TUTORIAL[i][0])
            l_txt.config(text=TUTORIAL[i][1])
            l_sub.config(text=f"Pantalla {i + 1} de {len(TUTORIAL)}")
            l_puntos.config(text=" ".join("●" if k == i else "○" for k in range(len(TUTORIAL))))
            b_ant.activo(i > 0)
            b_sig.config(text="Entendido  ✔" if i == len(TUTORIAL) - 1 else "Siguiente  ›")

        b_sig = Boton(pie, "Siguiente  ›", lambda: mostrar(1), "pri")
        b_sig.pack(side="right")
        b_ant = Boton(pie, "‹  Anterior", lambda: mostrar(-1))
        b_ant.pack(side="right", padx=8)
        v.protocol("WM_DELETE_WINDOW", cerrar)
        mostrar()
        return v

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
        self.hechos, self.contestaron = desde, 0
        self.avance()
        self.asistido = self.cfg["modo"].get(self.serial) == "asistido"
        self.trabajando = True
        self.pausado.clear()
        self.refrescar_inicio()
        self.b_pau.config(text="⏸  Pausar")
        self.b_pau.activo(True)
        self.b_col.activo(True)
        self.mostrar_boton_asistido()
        threading.Thread(target=self.trabajar, args=(desde,), daemon=True).start()

    def mostrar_boton_asistido(self):
        if self.asistido and self.trabajando:
            self.b_ret.pack(side="right", padx=10)
        else:
            self.b_ret.pack_forget()

    def pasar_a_asistido(self):
        self.asistido = True
        if self.serial:
            self.cfg["modo"][self.serial] = "asistido"
            motor.guardar_config(self.cfg)
        self.mostrar_boton_asistido()
        self.root.bell()
        self.estado("Este celular no avisa cuándo contestan",
                    "Cuando OIGA que contestan, presione «¡Contestaron!» para que no se cuelgue.", "alerta")

    def pausar(self):
        if self.pausado.is_set():
            self.pausado.clear()
            self.b_pau.config(text="⏸  Pausar")
        else:
            self.pausado.set()
            self.b_pau.config(text="▶  Reanudar")

    def pedir_nota(self, c):
        self.estado(f"Llamada con {c['nombre']} terminada",
                    "Escriba una nota si quiere y presione «Guardar y llamar al siguiente».", "info")
        self.f_nota.pack(fill="x", pady=(0, 12), after=self.f_acc)
        self.e_nota.focus()
        self.root.bell()

    def guardar_nota(self):
        if not self.f_nota.winfo_manager():
            return
        self.nota_actual = self.e_nota.get().strip()
        self.e_nota.delete(0, "end")
        self.f_nota.pack_forget()
        self.ev_continuar.set()

    def marcar_fila(self, i, resultado="", hora="", nota="", tag="ahora"):
        c = self.contactos[i]
        self.tree.item(str(i), values=(i + 1, c["nombre"], c["telefono"], resultado, hora, nota),
                       tags=(tag,) if tag == "ahora" else self._zebra(i) + (tag,))
        self.tree.see(str(i))

    def fila_final(self, i, res, hora, nota):
        self.hechos += 1
        self.contestaron += res == "CONTESTO"
        self.marcar_fila(i, TEXTO_RESULTADO.get(res, res), hora, nota, "ok" if res == "CONTESTO" else "no")
        self.avance()

    def fin_trabajo(self, titulo, detalle="", tono="ok"):
        self.trabajando = False
        self.b_pau.activo(False)
        self.b_col.activo(False)
        self.mostrar_boton_asistido()
        self.estado(titulo, detalle, tono)
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
                    self.ui(self.estado, "En pausa", "Presione «Reanudar» para seguir llamando.", "pausa")
                time.sleep(0.3)
            if self.detenido.is_set():
                return
            if not motor.horario_permitido():
                self.ui(self.fin_trabajo, "Se acabó el horario permitido para llamar",
                        "Mañana puede continuar: haga clic en la fila donde quedó y presione "
                        "«Iniciar llamadas».", "error")
                return
            if self.tel.conexion()[0] != "listo":
                self.ui(self.fin_trabajo, "Se perdió la conexión con el celular",
                        "Revise el cable y vuelva a presionar «Iniciar llamadas».", "error")
                return
            hora = time.strftime("%H:%M")
            if self.cfg["cobranza"] and motor.contactado_esta_semana(c["telefono"]):
                motor.registrar(c["nombre"], c["telefono"], "OMITIDO_LEY2300", "Contacto efectivo previo esta semana")
                self.ui(self.fila_final, i, "OMITIDO_LEY2300", hora, "")
                continue

            self.ui(self.marcar_fila, i, "Llamando…", hora)
            self.ui(self.estado, f"Llamando a {c['nombre']}", f"{c['telefono']}   ·   contacto {i + 1} de {total}",
                    "info")
            res, self.asistido = motor.una_llamada(
                self.tel, c["telefono"], self.cfg["timbre_max_s"], self.ev_colgar, self.ev_retener,
                asistido=self.asistido,
                al_cambiar=lambda e: self.ui(self.pasar_a_asistido) if e == "ASISTIDO" else None)
            nota = ""
            if res in motor.EFECTIVOS:
                if res == "CONTESTO":
                    self.ui(self.estado, f"☎  Contestó {c['nombre']}",
                            "Hable con calma. Al terminar, cuelgue en el celular o presione «Colgar».", "ok")
                else:
                    self.ui(self.estado, f"{c['nombre']}: parece buzón de voz",
                            "Si es buzón presione «Colgar». Si es una persona, hable normalmente.", "alerta")
                self.ui(self.root.bell)
                self.ev_colgar.clear()
                motor.esperar_fin(self.tel, self.ev_colgar, self.detenido)
                if self.detenido.is_set():
                    return
                if self.cfg["pedir_nota"]:
                    self.ev_continuar.clear()
                    self.ui(self.pedir_nota, c)
                    self.ev_continuar.wait()
                    if self.detenido.is_set():
                        return
                    nota = self.nota_actual
                else:
                    self.ui(self.estado, f"Llamada con {c['nombre']} terminada",
                            "En unos segundos llamo al siguiente contacto…", "info")
            motor.registrar(c["nombre"], c["telefono"], res, nota)
            self.ui(self.fila_final, i, res, hora, nota)
            time.sleep(self.cfg["pausa_s"])
        self.ui(self.fin_trabajo, "✔  Lista terminada", "Presione «Ver resultados» para abrir el registro "
                "de las llamadas.")


def main():
    prueba = "--autotest" in sys.argv  # prueba de humo del .exe: abre todo, dibuja y cierra
    root = tk.Tk()
    app = App(root, vigilar=not prueba)
    if prueba:
        app.poner_lista([{"nombre": "Prueba", "telefono": "3001234567"}])
        app.mostrar_conexion("ninguno", "")
        app.tutorial(len(TUTORIAL) - 1)
        app.ajustes()
        root.update()
        if not app.tel.adb:
            sys.exit(3)  # el adb no quedó dentro del ejecutable
        if not app.img_logo:
            sys.exit(4)  # los iconos no quedaron dentro del ejecutable
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()

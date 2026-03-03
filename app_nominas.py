import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from pathlib import Path
from PIL import Image, ImageTk  # para logo redimensionado moderno
import threading
import ctypes
import sys

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import nomina_core

NavigationToolbar2Tk.toolitems = tuple(
    item for item in NavigationToolbar2Tk.toolitems
    if item[0] != 'Subplots'
)

def resource_path(relative: str) -> str:
    """
    Devuelve la ruta absoluta a un recurso, funcionando tanto
    en desarrollo como dentro de un ejecutable PyInstaller.
    """
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return str(Path(base_path) / relative)



# DPI awareness para que no se vea borroso en Windows (en Linux no hace nada)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Windows 8.1+
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # Windows 7
    except Exception:
        pass


PRIMARY = "#a72e56"
PRIMARY_HOVER = "#912649"
BG = "#f8f3f5"
TEXT = "#332e33"


def configure_modern_style(root: tk.Tk):
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(bg=BG)

    style.configure(
        ".", 
        background=BG,
        foreground=TEXT,
        font=("Segoe UI", 11),
        padding=4
    )

    style.configure(
        "TLabel",
        background=BG,
        foreground=TEXT,
        font=("Segoe UI", 11)
    )

    style.configure(
        "Header.TLabel",
        font=("Segoe UI Semibold", 18),
        background=BG,
        foreground=PRIMARY,
        padding=10
    )

    style.configure(
        "Status.TLabel",
        background=BG,
        foreground=TEXT,
        font=("Segoe UI", 10)
    )

    style.configure(
        "TEntry",
        fieldbackground="white",
        bordercolor=PRIMARY,
        relief="flat",
        padding=7
    )

    style.configure(
        "Accent.TButton",
        background=PRIMARY,
        foreground="white",
        font=("Segoe UI Semibold", 11),
        padding=8,
        borderwidth=0
    )
    style.map(
        "Accent.TButton",
        background=[("active", PRIMARY_HOVER)]
    )

    style.configure("TSeparator", background=PRIMARY)


def load_logo(path, width=160):
    """Carga y redimensiona un logo para mostrarlo en la cabecera."""
    try:
        img = Image.open(path)
        w_percent = width / img.width
        h_size = int(float(img.height) * float(w_percent))
        img = img.resize((width, h_size), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"⚠️ No se pudo cargar el logo '{path}': {e}")
        return None


def get_downloads_dir() -> Path:
    """
    Devuelve la carpeta de Descargas del usuario de forma razonablemente
    portable. En Ubuntu suele ser ~/Downloads.
    """
    home = Path.home()
    downloads = home / "Downloads"
    if downloads.exists():
        return downloads
    # fallback típico en sistemas en español
    downloads_es = home / "Descargas"
    if downloads_es.exists():
        return downloads_es
    # último recurso: home
    return home


def procesar_todas(nominas_dir, annual_payments):
    """
    Procesa todas las nóminas.
    - OUTPUT_DIR se fija automáticamente a ~/Downloads/mis_nominas
    Devuelve: (df, output_dir)
    """
    nominas_dir = Path(nominas_dir)

    downloads_dir = get_downloads_dir()
    import uuid
    random_code = str(uuid.uuid4())
    output_dir = downloads_dir / f"mis_nominas_{random_code}"
    output_dir.mkdir(parents=True, exist_ok=True)

    nomina_core.NOMINAS_DIR = nominas_dir
    nomina_core.OUTPUT_DIR = output_dir
    nomina_core.ANNUAL_PAYMENTS = annual_payments

    # Procesa todas las nóminas y genera JSON/CSV en output_dir
    df = nomina_core.run_all_nominas()

    return df, output_dir


def mostrar_graficos_en_ventana(parent: tk.Tk, figs_with_titles):
    """
    Crea una ventana hija con los gráficos matplotlib embebidos en pestañas.
    Cada pestaña lleva su propia barra de navegación (zoom, pan, guardar, etc.).
    figs_with_titles: lista de (titulo, figura)
    """
    if not figs_with_titles:
        return

    win = tk.Toplevel(parent)
    win.title("Gráficos de nóminas")
    win.configure(bg=BG)
    win.geometry("900x600")

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True)

    for title, fig in figs_with_titles:
        # Frame para cada pestaña
        tab_frame = ttk.Frame(notebook)
        notebook.add(tab_frame, text=title)

        # Frame para la barra de herramientas
        toolbar_frame = ttk.Frame(tab_frame)
        toolbar_frame.pack(side="top", fill="x")

        # Frame para el canvas
        canvas_frame = ttk.Frame(tab_frame)
        canvas_frame.pack(side="top", fill="both", expand=True)

        canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
        canvas.draw()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill="both", expand=True)

        # Barra de herramientas específica de este canvas
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()


# <<< NUEVO: ventana de ayuda
def mostrar_ayuda(parent: tk.Tk):
    """Muestra una ventana con información de ayuda sobre la aplicación."""
    win = tk.Toplevel(parent)
    win.title("Ayuda - Lector de Nóminas")
    win.configure(bg=BG)
    win.geometry("620x420")

    frame = ttk.Frame(win, padding=15)
    frame.pack(fill="both", expand=True)

    titulo = ttk.Label(
        frame,
        text="¿Cómo usar el Lector de Nóminas?",
        style="Header.TLabel"
    )
    titulo.grid(row=0, column=0, sticky="w", pady=(0, 10))

    # Texto de ayuda con scrollbar
    text_frame = ttk.Frame(frame)
    text_frame.grid(row=1, column=0, sticky="nsew")

    ayuda_texto = tk.Text(
        text_frame,
        wrap="word",
        bg=BG,
        fg=TEXT,
        relief="flat",
        font=("Segoe UI", 10)
    )

    ayuda_contenido = """
1. ¿Qué hace la aplicación?
   • Lee todas las nóminas en PDF de una carpeta.
   • Extrae la información relevante (conceptos, totales, líquido, etc.).
   • Genera ficheros JSON y un CSV consolidado con todos los meses.
   • Muestra gráficos interactivos con la evolución de tu salario y totales.

2. Pasos para usarla
   1) Pulsa en el botón 📂 y selecciona la carpeta que contiene tus nóminas en PDF.
      - No es necesario elegir los ficheros uno a uno, solo la carpeta.
   2) Indica el número de pagas anuales (por defecto 14).
   3) Pulsa el botón "Procesar todas las nóminas".
   4) Espera a que termine el procesamiento (verás una barra de progreso).
   5) Al finalizar:
      • En tu carpeta de Descargas se creará la carpeta "mis_nominas" con:
        - JSON individuales por nómina.
        - Un CSV llamado "nominas_completo_normalizado.csv".
      • Se abrirá una ventana con gráficos interactivos.

3. Carpeta de salida
   • Windows / Ubuntu en inglés:
       ~/Downloads/mis_nominas
   • Sistemas en español (si existe):
       ~/Descargas/mis_nominas
   • Si no existe ninguna de las dos, se usará tu carpeta de usuario.

4. Gráficos
   • Cada pestaña corresponde a un gráfico distinto:
       - Salario Base.
       - Salario Bruto Anual.
       - Totales de nómina.
   • Debajo de cada gráfico tienes una barra de herramientas:
       - Lupa: zoom.
       - Mano: desplazar (pan).
       - Casa: volver a la vista inicial.
       - Disquete: guardar el gráfico como imagen.
   • Al pasar el ratón por un punto verás un cuadro con:
       - El concepto.
       - La fecha.
       - El importe en euros.

5. Notas
   • La aplicación no modifica tus PDFs originales.
   • Toda la información generada se guarda localmente en tu ordenador.
   • Si vuelves a ejecutar el proceso, se sobrescribirá la información previa
     en la carpeta "mis_nominas".
    """.strip()

    ayuda_texto.insert("1.0", ayuda_contenido)
    ayuda_texto.configure(state="disabled")

    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=ayuda_texto.yview)
    ayuda_texto.configure(yscrollcommand=scrollbar.set)

    ayuda_texto.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    text_frame.rowconfigure(0, weight=1)
    text_frame.columnconfigure(0, weight=1)

    # Que la ventana de ayuda también sea redimensionable
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)


def main():
    root = tk.Tk()
    root.title("Lector de nóminas")
    root.resizable(False, False) 

    # ICONO DE VENTANA
    try:
        icon_img = tk.PhotoImage(file=resource_path("assets/logo_atp_cuadrado.png"))
        root.iconphoto(False, icon_img)
    except Exception:
        print("ℹ️ No se pudo cargar el icono desde assets/logo_atp_cuadrado.png")

    configure_modern_style(root)

    # <<< NUEVO: barra de menú con opción Ayuda
    menubar = tk.Menu(root)
    helpmenu = tk.Menu(menubar, tearoff=0)
    helpmenu.add_command(label="Cómo funciona", command=lambda: mostrar_ayuda(root))
    menubar.add_cascade(label="Ayuda", menu=helpmenu)
    root.config(menu=menubar)
    # >>> fin menú ayuda


    main_frame = ttk.Frame(root, padding=20)
    main_frame.grid(row=0, column=0, sticky="nsew")

    # --- Hacer root y main_frame responsive ---
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)

    # Las 3 columnas del formulario
    for col in range(3):
        main_frame.columnconfigure(col, weight=1)

    # Da algo de peso a las filas “inferiores” para que haya expansión vertical
    # (puedes ajustar estos numbers según te guste el comportamiento)
    main_frame.rowconfigure(6, weight=1)  # barra de progreso
    main_frame.rowconfigure(7, weight=1)  # label de estado

    main_frame.grid(row=0, column=0, sticky="nsew")

    # LOGO SUPERIOR
    logo = load_logo(resource_path("assets/logo.png"), width=180)
    if logo:
        lbl_logo = ttk.Label(main_frame, image=logo, background=BG)
        lbl_logo.image = logo
        lbl_logo.grid(row=0, column=0, columnspan=3, pady=(0, 10))

    # CABECERA
    ttk.Label(
        main_frame,
        text="Lector de nóminas",
        style="Header.TLabel"
    ).grid(row=1, column=0, columnspan=3, pady=(0, 20))

    # CARPETA DE NÓMINAS
    ttk.Label(main_frame, text="Carpeta de nóminas (PDF):").grid(
        row=2, column=0, sticky="w", pady=10
    )
    entry_nominas = ttk.Entry(main_frame, width=45)
    entry_nominas.grid(row=2, column=1, pady=10, sticky="we")

    def elegir_nominas():
        carpeta = filedialog.askdirectory(title="Selecciona carpeta de nóminas")
        if carpeta:
            entry_nominas.delete(0, tk.END)
            entry_nominas.insert(0, carpeta)

    ttk.Button(
        main_frame, text="📂", command=elegir_nominas, style="Accent.TButton"
    ).grid(row=2, column=2, padx=5, pady=10)

    # Nº PAGAS
    ttk.Label(main_frame, text="Nº pagas anuales:").grid(
        row=3, column=0, sticky="w", pady=10
    )
    entry_pagas = ttk.Entry(main_frame, width=10)
    entry_pagas.insert(0, "14")
    entry_pagas.grid(row=3, column=1, sticky="w", pady=10)

    # SEPARADOR
    ttk.Separator(main_frame).grid(
        row=4, column=0, columnspan=3, sticky="ew", pady=10
    )

    # BOTÓN PRINCIPAL
    btn_run = ttk.Button(
        main_frame,
        text="Procesar todas las nóminas",
        style="Accent.TButton",
        width=30
    )
    btn_run.grid(row=5, column=0, columnspan=3, pady=(10, 5), sticky="we")

    # SPINNER
    progress = ttk.Progressbar(
        main_frame,
        mode="indeterminate",
        length=220
    )
    progress.grid(row=6, column=0, columnspan=3, pady=(5, 0), sticky="we")
    progress.grid_remove()

    # LABEL DE ESTADO
    status_label = ttk.Label(
        main_frame,
        text="",
        style="Status.TLabel",
        wraplength=420,
        anchor="center",
        justify="center"
    )
    status_label.grid(row=7, column=0, columnspan=3, pady=(8, 0), sticky="we")

    def on_procesar_todas():
        nominas_dir = entry_nominas.get().strip()

        try:
            annual_payments = int(entry_pagas.get().strip())
        except ValueError:
            status_label.config(
                text="⚠️ Número de pagas inválido.",
                foreground="red"
            )
            return

        if not nominas_dir:
            status_label.config(
                text="⚠️ Debe indicar la carpeta de nóminas.",
                foreground="red"
            )
            return

        # Preparar UI
        btn_run.config(state="disabled")
        status_label.config(
            text="⏳ Procesando nóminas, por favor espera...",
            foreground=TEXT
        )
        progress.grid()
        progress.start(10)

        result = {"df": None, "error": None, "output_dir": None}

        def worker():
            # Solo cálculo en hilo secundario
            try:
                df_local, output_dir_local = procesar_todas(
                    nominas_dir, annual_payments
                )
                result["df"] = df_local
                result["output_dir"] = output_dir_local
            except Exception as e:
                result["error"] = str(e)

            # Volver al hilo principal para tocar la UI y matplotlib
            root.after(0, on_finish)

        def on_finish():
            progress.stop()
            progress.grid_remove()
            btn_run.config(state="normal")

            if result["error"]:
                status_label.config(
                    text=f"❌ Error procesando las nóminas:\n{result['error']}",
                    foreground="red"
                )
            else:
                output_dir = result["output_dir"]
                status_label.config(
                    text=(
                        "✅ Procesamiento completado.\n"
                        f"Puedes descargar la carpeta con los resultados desde:\n{output_dir}"
                    ),
                    foreground="green"
                )
                df = result["df"]
                if df is not None:
                    figs = nomina_core.build_matplotlib_figures(df)
                    if figs:
                        mostrar_graficos_en_ventana(root, figs)

        threading.Thread(target=worker, daemon=True).start()

    btn_run.config(command=on_procesar_todas)

    # CENTRAR VENTANA
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()

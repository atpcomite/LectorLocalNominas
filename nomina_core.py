# nomina_core.py
"""
Módulo con la lógica de lectura y procesamiento de nóminas.
Este fichero debe contener el código que tenías en el notebook:
- NOMINAS_DIR, OUTPUT_DIR, ANNUAL_PAYMENTS
- COLS y demás constantes
- funciones auxiliares (parseo de líneas, normalización, etc.)
- run_extraction(pdf_path)
- run_all_nominas()
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from unidecode import unidecode
import pandas as pd

import matplotlib.pyplot as plt
import seaborn as sns
import mplcursors
import matplotlib.dates as mdates


# Estilo global de seaborn
sns.set_theme(
    style="whitegrid",
    rc={
        "axes.facecolor": "#ffffff",
        "figure.facecolor": "#ffffff",
    }
)


# Estos valores los puede sobreescribir la GUI antes de llamar a run_all_nominas/run_extraction
NOMINAS_DIR = Path("nominas")          # carpeta con todas las nóminas PDF
OUTPUT_DIR = Path("salidas_nomina")    # carpeta de salida de JSON/CSV/TXT
#OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ANNUAL_PAYMENTS = 14  # nº de pagas anuales para el cálculo del salario bruto anual

# Límites de columna (start, end) -> end exclusivo (tus offsets validados)
COLS = {
    "cuantia":     (0, 12),   # CUANTIA
    "precio":      (12, 23),  # PRECIO
    "codigo":      (23, 30),  # CODIGO
    "concepto":    (30, 71),  # CONCEPTO
    "devengos":    (71, 81),  # DEVENGOS
    "deducciones": (81, 120), # DEDUCCIONES
}

DED_CODES = {"994", "995", "996", "997"}

REQUIRED_KEYS = {"cuantia", "precio", "concepto", "devengos", "deducciones"}

TOTAL_TITLES = [
    "REM. TOTAL",
    "P.P.EXTRAS",
    "BASE S.S.",
    "BASE A.T. Y DES.",
    "BASE I.R.P.F.",
    "T. DEVENGADO",
    "T.  A DEDUCIR",
]

DEC_TOKEN = re.compile(r"[\dx\.]{1,20},\d{2}")

# =========================
# FUNCIONES AUXILIARES
# =========================
def normalize(s: str) -> str:
    s = unidecode(s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def normalize_concept(s: str) -> str:
    t = normalize(s)
    t = t.replace("* ", "*")
    return t

def slice_col(line: str, start: int, end: int) -> str:
    if len(line) < end:
        line = line.ljust(end)
    return line[start:end]

def preview_with_ruler(lines: List[str], n: int = 10) -> str:
    max_len = max((len(ln) for ln in lines[:n]), default=120)
    rule_dec = "".join(str((i // 10) % 10) for i in range(max_len))
    rule_uni = "".join(str(i % 10) for i in range(max_len))
    cutline = [" "] * max_len
    for _, (a, b) in COLS.items():
        if a < max_len: cutline[a] = "|"
        if b - 1 < max_len: cutline[b - 1] = "|"
    header = [
        "Regla decenas: " + rule_dec,
        "Regla unidades:" + rule_uni,
        "Cortes columnas:" + "".join(cutline),
        f"Cortes: {COLS}",
        ""
    ]
    sample = []
    for i, ln in enumerate(lines[:n], 1):
        sample.append(f"[{i:02d}] {ln.rstrip()}")
    return "\n".join(header + sample)

# =========================
# EURO helpers + conceptos objetivo "Bruto anual"
# =========================
TARGET_CONCEPTS_RAW = {
    "*Salario Base",
    "*Plus Convenio",
    "*Antigüedad",
    "*mejora absorbible",
    "*mejora absobible",
    "*Mejora Voluntaria",
    "*retribución flexible exenta",
    "*retribucion flexible no exenta",
}
TARGET_CONCEPTS = {normalize_concept(x) for x in TARGET_CONCEPTS_RAW}

def parse_euro_es(s: Optional[str]) -> float:
    if not s:
        return 0.0
    t = s.replace("x", "0").replace("X", "0")
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except Exception:
        return 0.0

def format_euro_es(v: float) -> str:
    s = f"{v:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s

# =========================
# LECTURA DEL PDF
# =========================
def read_pdf_text_pages(pdf_path: str) -> List[str]:
    pages_text = []
    try:
        from pdfminer.high_level import extract_text
        full = extract_text(pdf_path) or ""
        parts = [p for p in full.split("\x0c") if p is not None]
        if len(parts) > 1:
            pages_text = parts
        else:
            raise RuntimeError("pdfminer no separó páginas, uso pdfplumber")
    except Exception:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for p in pdf.pages:
                    t = p.extract_text(x_tolerance=1, y_tolerance=1) or ""
                    pages_text.append(t)
        except Exception:
            pages_text = []
    return pages_text

# =========================
# EXTRACCIÓN DE MES Y AÑO
# =========================
MONTH_MAP = {
    "ENE": 1, "ENERO": 1, "FEB": 2, "FEBRERO": 2, "MAR": 3, "MARZO": 3,
    "ABR": 4, "ABRIL": 4, "MAY": 5, "MAYO": 5, "JUN": 6, "JUNIO": 6,
    "JUL": 7, "JULIO": 7, "AGO": 8, "AGOSTO": 8, "SEP": 9, "SEPT": 9, "SEPTIEMBRE": 9,
    "OCT": 10, "OCTUBRE": 10, "NOV": 11, "NOVIEMBRE": 11, "DIC": 12, "DICIEMBRE": 12,
}
MONTH_NAME_ES = {
    1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
    7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"
}

def _to_year4(y: int) -> int:
    if y < 100:
        return 2000 + y
    return y

def extract_month_year(pages_text: List[str]) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    full = "\n".join(pages_text)

    m = re.search(r"(\d{1,2})\s+([A-ZÁÉÍÓÚÜ]{3,})\s+(\d{2,4})\s+a\s+(\d{1,2})\s+([A-ZÁÉÍÓÚÜ]{3,})\s+(\d{2,4})", full)
    if m:
        mon_abbr = unidecode(m.group(5)).upper()
        yy = int(m.group(6))
        if mon_abbr in MONTH_MAP:
            mon_num = MONTH_MAP[mon_abbr]
            return MONTH_NAME_ES[mon_num], _to_year4(yy), mon_num

    m2 = re.search(r"(?:FECHA|PERIODO).*?\b([A-ZÁÉÍÓÚÜ]{3,})\b\s+(\d{2,4})", full, flags=re.IGNORECASE|re.DOTALL)
    if m2:
        mon = unidecode(m2.group(1)).upper()
        yy = int(m2.group(2))
        if mon in MONTH_MAP:
            mon_num = MONTH_MAP[mon]
            return MONTH_NAME_ES[mon_num], _to_year4(yy), mon_num

    m3 = re.search(r"\b([A-ZÁÉÍÓÚÜ]{3,})\b", full)
    if m3:
        mon = unidecode(m3.group(1)).upper()
        if mon in MONTH_MAP:
            mon_num = MONTH_MAP[mon]
            return MONTH_NAME_ES[mon_num], None, mon_num

    return None, None, None

def make_period_key(year: Optional[int], month_num: Optional[int]) -> Optional[str]:
    if year and month_num:
        return f"{year:04d}-{month_num:02d}"
    return None

# =========================
# DETECCIÓN DE TABLAS Y TOTALES
# =========================
def find_stacked_header_block(lines_raw: List[str], window: int = 25) -> Optional[int]:
    lines_norm = [normalize(l) for l in lines_raw]
    n = len(lines_norm)
    for i in range(n):
        seen = set()
        last_idx = i
        for j in range(i, min(i + window, n)):
            tok = lines_norm[j]
            for key in REQUIRED_KEYS:
                if tok == key:
                    seen.add(key)
                    last_idx = j
            if seen == REQUIRED_KEYS:
                return last_idx + 1
    return None

def find_table_block_in_page(page_text: str, page_idx: int) -> str:
    if not page_text.strip():
        return ""
    (OUTPUT_DIR / f"debug_text_page_{page_idx+1}.txt").write_text(page_text, encoding="utf-8")

    lines_raw = page_text.splitlines()
    start_idx = find_stacked_header_block(lines_raw, window=25)

    if start_idx is None:
        lines_norm = [normalize(l) for l in lines_raw]
        for i, ln in enumerate(lines_norm):
            if all(k in ln for k in REQUIRED_KEYS):
                start_idx = i + 1
                break
    if start_idx is None:
        return ""

    end_markers = [
        "sigue en siguiente hoja",
        "base s. s.",
        "fecha sello empresa",
        "determinacion de las b.",
        "nif.",
        "base i.r.p.f.",
    ]
    lines_norm = [normalize(l) for l in lines_raw]
    end_idx = None
    for j in range(start_idx, len(lines_norm)):
        if any(m in lines_norm[j] for m in end_markers):
            end_idx = j
            break
    if end_idx is None:
        end_idx = len(lines_raw)

    return "\n".join(lines_raw[start_idx:end_idx])

def find_totals_in_page(page_text: str) -> Optional[Dict[str, Optional[str]]]:
    if not page_text.strip():
        return None

    lines_raw = page_text.splitlines()
    lines_norm = [normalize(l) for l in lines_raw]

    needed_norm = [normalize(t) for t in TOTAL_TITLES]
    title_idxs: List[int] = [i for i, ln in enumerate(lines_norm) if ln in needed_norm]
    if not title_idxs:
        return None

    top = max(min(title_idxs) - 15, 0)
    bot = min(max(title_idxs) + 15, len(lines_raw))

    stop_markers = {"fecha", "sello empresa", "percepciones salariales", "percepciones no salariales", "determinacion de las b.", "nif."}

    for k in range(top, bot):
        if any(m in lines_norm[k] for m in stop_markers):
            continue
        found = DEC_TOKEN.findall(lines_raw[k])
        if len(found) >= len(TOTAL_TITLES):
            return dict(zip(TOTAL_TITLES, found[:len(TOTAL_TITLES)]))

    tokens: List[str] = []
    for k in range(top, bot):
        if any(m in lines_norm[k] for m in stop_markers):
            continue
        found = DEC_TOKEN.findall(lines_raw[k])
        if found:
            tokens.extend(found)
            if len(tokens) >= len(TOTAL_TITLES):
                return dict(zip(TOTAL_TITLES, tokens[:len(TOTAL_TITLES)]))
    return None

def find_liquido_en_page(page_text: str) -> Optional[str]:
    if not page_text.strip():
        return None
    lines_raw = page_text.splitlines()
    lines_norm = [normalize(l) for l in lines_raw]
    idxs = [i for i, ln in enumerate(lines_norm) if "liquido a percibir" in ln]
    if not idxs:
        return None
    for idx in idxs:
        top = max(0, idx - 5)
        candidates = []
        for k in range(top, idx):
            found = DEC_TOKEN.findall(lines_raw[k])
            if found:
                candidates.extend(found)
        if candidates:
            return candidates[-1]
    return None

def parse_fixed_line(line: str) -> Dict[str, Optional[str]]:
    s = line.rstrip("\n")
    row: Dict[str, Optional[str]] = {}
    for k, (a, b) in COLS.items():
        row[k.capitalize()] = slice_col(s, a, b).strip() or None
    if (row.get("Codigo") in DED_CODES) and row.get("Devengos") and not row.get("Deducciones"):
        row["Deducciones"] = row["Devengos"]
        row["Devengos"] = None
    return row

# =========================
# GUARDADO JSON
# =========================
def save_hist_json_list(path: Path, data: List[Dict]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ================================================
# 3️⃣ Función principal: procesar UN PDF
#    (copia aquí tu run_extraction original)
# ================================================

def run_extraction(pdf_path: str):
    """
    Procesa una única nómina PDF.

    Esta implementación debe ser la misma que tenías en el notebook:
    - lee el PDF (read_pdf_text_pages)
    - localiza el bloque de tabla en cada página
    - convierte cada línea en un dict con parse_line_to_row
    - acumula filas en all_rows
    - calcula SALARIO BRUTO ANUAL usando ANNUAL_PAYMENTS
    - genera un JSON (y/o CSV/TXT) en OUTPUT_DIR
    """
    pdf_path = Path(pdf_path)
    pages = read_pdf_text_pages(str(pdf_path))
    if not pages:
        print(f"⚠️ No se pudo leer el PDF: {pdf_path}")
        return

    month_name, year4, mon_num = extract_month_year(pages)
    period_key = make_period_key(year4, mon_num)

    all_rows: List[Dict[str, Optional[str]]] = []
    pages_with_blocks = 0
    found_999 = False
    totals_row: Optional[Dict[str, Optional[str]]] = None
    liquido_val: Optional[str] = None

    for pi, page_text in enumerate(pages):
        if found_999:
            break

        block = find_table_block_in_page(page_text, page_idx=pi)
        if block.strip():
            pages_with_blocks += 1
            page_lines = [ln for ln in block.splitlines() if ln.strip()]
            (OUTPUT_DIR / f"preview_ruler_p{pi+1}.txt").write_text(
                preview_with_ruler(page_lines, n=12), encoding="utf-8"
            )
            for ln in page_lines:
                row = parse_fixed_line(ln)
                if not any(row.get(k) for k in ["Cuantia", "Precio", "Codigo", "Concepto", "Devengos", "Deducciones"]):
                    continue
                all_rows.append(row)
                codigo = (row.get("Codigo") or "").strip()
                if codigo == "999":
                    found_999 = True
                    break

        if totals_row is None:
            maybe_totals = find_totals_in_page(page_text)
            if maybe_totals:
                totals_row = maybe_totals

        if liquido_val is None:
            liquido = find_liquido_en_page(page_text)
            if liquido:
                liquido_val = liquido

    bruto_mensual_sum = 0.0
    for r in all_rows:
        concepto_norm = normalize_concept(r.get("Concepto") or "")
        if concepto_norm in TARGET_CONCEPTS:
            importe = parse_euro_es(r.get("Devengos"))
            bruto_mensual_sum += importe

    bruto_anual_val = bruto_mensual_sum * ANNUAL_PAYMENTS

    if totals_row is None:
        totals_row = {k: None for k in TOTAL_TITLES}
    totals_row["LIQUIDO A PERCIBIR"] = liquido_val
    totals_row["SALARIO BRUTO ANUAL"] = format_euro_es(bruto_anual_val) if bruto_anual_val else None

    print("\n===== RESUMEN NÓMINA =====")
    print(f"Archivo             : {pdf_path.name}")
    print(f"Mes                 : {month_name or '-'}")
    print(f"Año                 : {year4 or '-'}")
    print(f"Líneas extraídas    : {len(all_rows)}  |  Páginas con tabla: {pages_with_blocks}")

    # === Guardado JSON con el mismo nombre que el PDF ===
    json_name = pdf_path.stem + ".json"
    json_path = OUTPUT_DIR / json_name

    data = {
        "archivo_pdf": pdf_path.name,
        "period": month_name,
        "year": year4,
        "period_key": period_key,
        "totales": totals_row,
        "lineas": all_rows,
    }

    save_hist_json_list(json_path, [data])
    print(f"✅ JSON guardado en: {json_path}\n")


# ===============================================================
# 🔎 Utilidades de análisis: cargar JSON y crear DataFrame
# ===============================================================

def parse_euro(val):
    """
    Convierte '1.234,56' -> 1234.56 (float).
    Devuelve None si no se puede convertir.
    """
    if not val:
        return None
    val = str(val).replace(".", "").replace(",", ".")
    try:
        return float(val)
    except Exception:
        return None


def normalize_concepto(name: str) -> str:
    """
    Normaliza el nombre del concepto y agrupa prefijos comunes.
    Es la misma lógica que usabas en el notebook.
    """
    if not name:
        return None
    name = name.strip()
    name = re.sub(r"[*]+", "", name)
    name = re.sub(r"\s+", " ", name)
    name = name.replace(".", "").strip()
    name = name.title()

    # --- Agrupaciones personalizadas ---
    if re.match(r"(?i)^tributacion i.?r.?p.?f", name):
        return "Tributacion Irpf"
    if re.match(r"(?i)^cotizacion cont.?comu", name):
        return "Cotizacion Contcomu"

    return name


def build_dataframe_from_jsons(data_dir = None) -> pd.DataFrame:
    """
    Carga todos los JSON de nóminas y construye un DataFrame con:
    - totales principales (totales)
    - columnas dinámicas por concepto (líneas de devengos/deducciones)

    data_dir:
        Carpeta de donde leer los JSON. Por defecto, OUTPUT_DIR.

    Devuelve:
        df (pandas.DataFrame)
    """
    # ===============================================================
    # 1️⃣ Cargar todos los JSON
    # ===============================================================
    if data_dir is None:
        # Por defecto usamos la misma carpeta donde guardamos las salidas
        data_dir = OUTPUT_DIR

    data_dir = Path(data_dir)
    files = sorted(data_dir.glob("*.json"))

    print(f"📂 Archivos JSON encontrados en '{data_dir}': {len(files)}")

    all_data: list[dict] = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                content = json.load(fh)
                if isinstance(content, list):
                    all_data.extend(content)
                else:
                    all_data.append(content)
        except Exception as e:
            print(f"⚠️ Error leyendo {f}: {e}")

    print(f"✅ Nóminas cargadas: {len(all_data)}")

    # ===============================================================
    # 3️⃣ Crear lista de registros para el DataFrame
    # ===============================================================
    records: list[dict] = []

    for item in all_data:
        tot = item.get("totales", {}) or {}
        rec: dict = {
            # si en tus JSON tienes estos campos, puedes descomentarlos:
            # "archivo_pdf": item.get("archivo_pdf"),
            # "period": item.get("period"),
            # "year": item.get("year"),
            "period_key": item.get("period_key"),
        }

        # Totales principales (convertimos a float)
        for k, v in tot.items():
            rec[k] = parse_euro(v)

        # fecha a partir de period_key (ej: "2024-01")
        rec["fecha"] = pd.to_datetime(item.get("period_key"), errors="coerce")

        # Procesar líneas (conceptos)
        for ln in item.get("lineas", []):
            concepto = normalize_concepto(ln.get("Concepto"))
            dev = ln.get("Devengos")
            ded = ln.get("Deducciones")

            if not concepto:
                continue

            valor = None
            if dev:
                valor = parse_euro(dev)
            elif ded:
                valor = -parse_euro(ded)

            if valor is not None:
                rec[concepto] = rec.get(concepto, 0) + valor

        records.append(rec)

    # ===============================================================
    # 4️⃣ Crear DataFrame final
    # ===============================================================
    df = pd.DataFrame(records)

    if "fecha" in df.columns:
        df = df.sort_values("fecha").reset_index(drop=True)

    print(f"\n✅ DataFrame final con totales + conceptos: {df.shape}")

    # ===============================================================
    # 5️⃣ Mostrar columnas dinámicas añadidas
    # ===============================================================
    extra_cols = sorted(
        [
            c
            for c in df.columns
            if c not in ["archivo_pdf", "period", "year", "period_key", "fecha"]
        ]
    )
    print(f"\n📊 Columnas ({len(df.columns)}):")
    print(df.columns.values)
    print("\n📊 Columnas dinámicas de conceptos:")
    print(extra_cols)

    return df




def run_all_nominas(csv_name: str = "nominas_completo_normalizado.csv") -> pd.DataFrame:
    """
    Procesa todas las nóminas PDF que haya en NOMINAS_DIR, genera los JSON
    individuales, construye un DataFrame consolidado y exporta el CSV final.

    Parámetros
    ----------
    csv_name : str
        Nombre del archivo CSV que se guardará en OUTPUT_DIR.

    Devuelve
    --------
    df : pandas.DataFrame
        DataFrame consolidado con todos los periodos.
    """
    # ==============================
    # 1️⃣ Procesar todos los PDFs
    # ==============================
    if not NOMINAS_DIR.exists():
        raise FileNotFoundError(f"La carpeta de nóminas no existe: {NOMINAS_DIR}")

    pdfs = sorted(
        p for p in NOMINAS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )

    if not pdfs:
        raise FileNotFoundError(f"No se encontraron archivos PDF en: {NOMINAS_DIR}")

    print(f"📄 Encontrados {len(pdfs)} PDFs en '{NOMINAS_DIR}':")
    for pdf in pdfs:
        print(f"➡️ Procesando {pdf.name}...")
        run_extraction(str(pdf))

    print(f"\n✅ Procesamiento de PDFs completado. JSONs individuales en: {OUTPUT_DIR}")

    # ==============================
    # 2️⃣ Construir DataFrame
    # ==============================
    df = build_dataframe_from_jsons(data_dir=OUTPUT_DIR)

    if df.empty:
        raise ValueError("No se han podido generar datos a partir de los JSON de nóminas.")

    # ==============================
    # 3️⃣ Exportar CSV consolidado
    # ==============================
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / csv_name
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"💾 Archivo CSV guardado: {csv_path}")

    return df


import matplotlib.dates as mdates

import mplcursors
import matplotlib.dates as mdates

PRIMARY = "#a72e56"
PRIMARY_LIGHT = "#c25077"   # color complementario suave
TEXT_LIGHT = "#ffffff"      # texto blanco

def _add_hover_to_axes(ax):
    """
    Añade tooltips con estilo personalizado a las líneas del gráfico.
    Tooltips:
    - color de fondo acorde al tema (#a72e56)
    - borde redondeado
    - sombra suave
    - texto blanco
    - formateo bonito de fechas e importes
    """
    if not ax.lines:
        return

    cursor = mplcursors.cursor(ax.lines, hover=True)

    @cursor.connect("add")
    def on_add(sel):
        line = sel.artist
        label = line.get_label()

        # Coordenadas del punto
        x, y = sel.target

        # Convertir fecha si es numérica
        try:
            x_dt = mdates.num2date(x)
            x_str = x_dt.strftime("%Y-%m-%d")
        except Exception:
            x_str = str(x)

        try:
            y_str = f"{float(y):,.2f} €"
        except Exception:
            y_str = str(y)

        # ====== Construcción del texto ======
        sel.annotation.set_text(
            f"{label}\n"
            f"{x_str}\n"
            f"{y_str}"
        )

        ann = sel.annotation

        # ====== Estilos bonitos ======
        ann.get_bbox_patch().set(
            boxstyle="round,pad=0.35",
            fc=TEXT_LIGHT,          # fondo
            ec=PRIMARY_LIGHT,    # borde
            alpha=0.95,
            linewidth=1.5
        )

        ann.set_fontsize(9)
        ann.set_color(PRIMARY)
        ann.set_rotation(0)





def build_matplotlib_figures(df: pd.DataFrame):
    """
    Crea figuras de matplotlib/seaborn a partir del DataFrame de nóminas.
    Devuelve una lista de (titulo, figura) listas para incrustar en Tkinter.
    Cada gráfico tiene hover con tooltip sobre los puntos.
    """
    figs = []

    # Estilo seaborn global
    sns.set_theme(
        style="whitegrid",
        rc={
            "axes.facecolor": "#ffffff",
            "figure.facecolor": "#ffffff",
        }
    )

    palette_main = "#a72e56"
    palette_totals = sns.color_palette("rocket", n_colors=6)

    # 1) Salario Base
    if "fecha" in df.columns and "Salario Base" in df.columns:
        fig1, ax1 = plt.subplots(figsize=(8, 4))
        sns.lineplot(
            data=df,
            x="fecha",
            y="Salario Base",
            marker="o",
            ax=ax1,
            color=palette_main,
            label="Salario Base"
        )
        ax1.set_title("Evolución del Salario Base", fontsize=12, fontweight="semibold")
        ax1.set_xlabel("Fecha")
        ax1.set_ylabel("€")
        ax1.tick_params(axis="x", rotation=45)
        ax1.grid(alpha=0.2)
        fig1.tight_layout()

        _add_hover_to_axes(ax1)
        figs.append(("Salario Base", fig1))

    # 2) Salario bruto anual
    if "fecha" in df.columns and "SALARIO BRUTO ANUAL" in df.columns:
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        sns.lineplot(
            data=df,
            x="fecha",
            y="SALARIO BRUTO ANUAL",
            marker="o",
            ax=ax2,
            color=palette_main,
            label="Salario Bruto Anual"
        )
        ax2.set_title("Evolución del Salario Bruto Anual", fontsize=12, fontweight="semibold")
        ax2.set_xlabel("Fecha")
        ax2.set_ylabel("€")
        ax2.tick_params(axis="x", rotation=45)
        ax2.grid(alpha=0.2)
        fig2.tight_layout()

        _add_hover_to_axes(ax2)
        figs.append(("Salario Bruto Anual", fig2))

    # 3) Totales en una sola figura
    if "fecha" in df.columns:
        totales_cols = [
            "REM. TOTAL",
            "BASE S.S.",
            "BASE A.T. Y DES.",
            "BASE I.R.P.F.",
            "T. DEVENGADO",
            "LIQUIDO A PERCIBIR",
        ]
        cols_presentes = [c for c in totales_cols if c in df.columns]
        if cols_presentes:
            fig3, ax3 = plt.subplots(figsize=(9, 5))
            for idx, col in enumerate(cols_presentes):
                color = palette_totals[idx % len(palette_totals)]
                sns.lineplot(
                    data=df,
                    x="fecha",
                    y=col,
                    marker="o",
                    ax=ax3,
                    label=col,
                    color=color
                )
            ax3.set_title("Evolución de los totales de nómina", fontsize=12, fontweight="semibold")
            ax3.set_xlabel("Fecha")
            ax3.set_ylabel("€")
            ax3.tick_params(axis="x", rotation=45)
            ax3.grid(alpha=0.2)
            ax3.legend(title="Concepto", fontsize=8)
            fig3.tight_layout()

            _add_hover_to_axes(ax3)
            figs.append(("Totales", fig3))

    return figs






# Este módulo está pensado para ser usado desde app_nominas.py,
# así que no hace falta el if __name__ == "__main__".

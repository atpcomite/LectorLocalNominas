# Ayuda: Mis Nóminas - Procesador de nóminas en PDF

## 1. ¿Qué hace la aplicación?

- Lee **todas las nóminas en PDF** de una carpeta.
- Extrae la **información relevante** (conceptos, totales, líquido, etc.).
- Genera ficheros **JSON** y un **CSV consolidado** con todos los meses.
- Muestra **gráficos interactivos** con la evolución de tu salario y totales.

---

## 2. Pasos para usarla

1. Pulsa el botón 📂 y selecciona la **carpeta** que contiene tus nóminas en PDF.  
   - No es necesario elegir los ficheros uno a uno, solo la carpeta.
2. Indica el **número de pagas anuales** (por defecto **14**).
3. Pulsa el botón **"Procesar todas las nóminas"**.
4. Espera a que termine el procesamiento (verás una **barra de progreso**).
5. Al finalizar:
   - En tu carpeta de **Descargas** se creará la carpeta **`mis_nominas`** con:
     - JSON individuales por nómina.
     - Un CSV llamado **`nominas_completo_normalizado.csv`**.
   - Se abrirá una ventana con **gráficos interactivos**.

---

## 3. Carpeta de salida

La aplicación intenta guardar los resultados en:

- Windows / Ubuntu en inglés:  
  `~/Downloads/mis_nominas`
- Sistemas en español (si existe):  
  `~/Descargas/mis_nominas`

Si no existe ninguna de las dos, se usará tu **carpeta de usuario**.

---

## 4. Gráficos

- Cada pestaña corresponde a un gráfico distinto:
  - Salario Base.
  - Salario Bruto Anual.
  - Totales de nómina.
- Debajo de cada gráfico tienes una barra de herramientas:
  - **Lupa**: zoom.
  - **Mano**: desplazar (pan).
  - **Casa**: volver a la vista inicial.
  - **Disquete**: guardar el gráfico como imagen.
- Al pasar el ratón por un punto verás un cuadro con:
  - El concepto.
  - La fecha.
  - El importe en euros.

---

## 5. Notas

- La aplicación **no modifica** tus PDFs originales.
- Toda la información generada se guarda **localmente** en tu ordenador.
- Si vuelves a ejecutar el proceso, se **sobrescribirá** la información previa en la carpeta **`mis_nominas`**.


# Ejecutar en modo desarrollo en Windows

## 1) Abrir CMD en la carpeta del proyecto

```cmd
cd "c:\Users\albac\Desktop\Utils\app_nominas"
```

## 2) Crear y activar entorno virtual 

```cmd
py -m venv .venv
\.venv\Scripts\activate.bat
```

## 3) Instalar dependencias

```cmd
py -m pip install -r requirements.txt
```

## 4) Ejecutar la aplicación

```cmd
py app_nominas.py
```

---

## Uso rápido dentro de la app

1. Pulsa **📂** y selecciona la carpeta con tus nóminas en PDF.
2. Revisa el número de pagas anuales (por defecto: **14**).
3. Pulsa **Procesar todas las nóminas**.

Los resultados se guardan en una carpeta tipo `mis_nominas_<uuid>` dentro de **Descargas**.

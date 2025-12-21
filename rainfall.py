import tkinter as tk
from tkinter import messagebox
import pandas as pd
from pathlib import Path
from io import StringIO
import sys
import re

def limpiar_datos(data):
    """Limpia y normaliza los datos de entrada con formato español"""
    data = data.strip()
    
    # 1. Normalizar AM/PM español a inglés
    data = re.sub(r'\bp\.\s*m\.', 'PM', data, flags=re.IGNORECASE)
    data = re.sub(r'\ba\.\s*m\.', 'AM', data, flags=re.IGNORECASE)
    
    # 2. Procesar línea por línea
    lines = data.split('\n')
    processed_lines = []
    
    for line in lines:
        if not line.strip():
            continue
        
        # Extraer timestamp (está entre comillas)
        match = re.match(r'^"([^"]+)"(.*)$', line)
        if match:
            timestamp = match.group(1)
            rest_of_line = match.group(2)
            
            # 3. Eliminar separadores de miles (puntos entre números)
            # Ejemplo: 1.392,410 -> 1392,410
            rest_of_line = re.sub(r'(\d+)\.(\d{3})', r'\1\2', rest_of_line)
            
            # 4. Reemplazar comas decimales por puntos
            # Ejemplo: 884,750 -> 884.750
            rest_of_line = re.sub(r'(\d+),(\d+)', r'\1.\2', rest_of_line)
            
            # Reconstruir línea
            processed_line = f'"{timestamp}"{rest_of_line}'
            processed_lines.append(processed_line)
        else:
            # Línea de encabezados
            processed_lines.append(line)
    
    return '\n'.join(processed_lines)

def read_data(data):
    # Limpiar y normalizar datos
    data = limpiar_datos(data)
    
    data_io = StringIO(data)

    # Leer datos
    df = pd.read_csv(data_io, skiprows=0, sep=',', 
                     encoding='utf-8', engine='python')
    
    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip().str.strip('"').str.strip()
    
    # Separa Timestamp en Fecha y Hora
    df[['Fecha', 'Hora']] = df['Timestamp'].str.split(',', expand=True) 
    df['Fecha'] = df['Fecha'].str.strip('" ').str.strip() 
    df['Hora'] = df['Hora'].str.strip('" ').str.strip()
    
    # Convertir columna Fecha
    df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d/%m/%Y')
    
    # Convertir columna Hora con manejo de múltiples formatos
    def convertir_hora(hora_str):
        """Intenta convertir la hora usando diferentes formatos"""
        formatos = [
            '%I:%M:%S %p',  # Formato 12 horas con AM/PM (ej: "08:30:00 PM")
            '%H:%M:%S',     # Formato 24 horas (ej: "20:30:00")
            '%I:%M:%S%p',   # Formato 12 horas sin espacio (ej: "08:30:00PM")
        ]
        
        for formato in formatos:
            try:
                return pd.to_datetime(hora_str, format=formato).time()
            except:
                continue
        
        raise ValueError(f"No se pudo convertir la hora: '{hora_str}'. Formatos soportados: HH:MM:SS o HH:MM:SS AM/PM")
    
    try:
        df['Hora'] = df['Hora'].apply(convertir_hora)
    except ValueError as e:
        messagebox.showerror("Error de formato", str(e))
        raise

    # Eliminar columnas innecesarias
    columns_to_drop = ['Timestamp']
    if 'CS320_Temp_Avg' in df.columns:
        columns_to_drop.append('CS320_Temp_Avg')
    
    new_df = df.drop(columns=columns_to_drop)
    
    # Reorganiza las columnas
    column_order = ['Fecha', 'Hora'] + [col for col in new_df.columns if col not in ['Fecha', 'Hora']] 
    new_df = new_df[column_order]
   
    return new_df

def concatenate_columns(new_df):
    """Concatena columnas seleccionadas en formato SQL."""
    def format_value(value):
        if pd.isna(value):
            return "NULL"
        elif isinstance(value, pd.Timestamp):
            return f"'{value.strftime('%Y-%m-%d')}'"
        elif isinstance(value, str):
            return f"'{value}'"
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            return f"'{value}'"

    concatenated_values = new_df.apply(
        lambda row: '(' + ','.join([format_value(val) for val in row]) + ')', axis=1
    )
    
    sql_query = ',\n'.join(concatenated_values) + ';'
    return sql_query

def save_to_txt(content, file_name):
    """Exporta el contenido generado a un archivo .txt con codificación utf-8."""
    with open(file_name, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\nArchivo guardado en: {file_name}")

def get_unique_filename(file_path):
    """Genera un nombre de archivo único con formato CONCAT_1, CONCAT_2, etc."""
    counter = 1
    while file_path.exists():
        file_path = file_path.with_name(f'CONCAT_{counter}{file_path.suffix}')
        counter += 1
    return file_path

# ========================================================
# INTERFAZ GRÁFICA CON TKINTER
# ========================================================

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Concatenar Precipitaciones")
        self.geometry("900x700")
        self.label = tk.Label(self, text="Pegar datos aquí:", font=("Cambria math", 16))
        self.label.pack(pady=0)
        
        # Cuadro de texto para pegar los datos
        self.text_box = tk.Text(self, height=30, width=100)
        self.text_box.pack(pady=10)
        
        button_frame = tk.Frame(self, height=5, border=2) 
        button_frame.pack(pady=10)

        # Botón para procesar los datos pegados
        self.process_button = tk.Button(
            button_frame, text="Concatenar", 
            font=("cambria math", 12), 
            width=10, 
            height=2,
            background="lightblue",
            command=self.process_data
        )
        self.process_button.pack(side=tk.LEFT, padx=20, pady=10) 

        # Botón para borrar el contenido
        self.clear_button = tk.Button(
            button_frame, text="Borrar", 
            font=("cambria math", 12), 
            width=10, 
            height=2,
            command=self.clear_content
        )
        self.clear_button.pack(side=tk.LEFT, padx=20, pady=10)

        # Botón para salir
        self.exit_button = tk.Button(
            button_frame, text="Salir", 
            font=("cambria math", 12), 
            width=10,
            height=2,
            command=self.exit_app
        )
        self.exit_button.pack(side=tk.LEFT, padx=20, pady=10)

    def process_data(self):
        """Procesa los datos pegados en el campo de texto."""
        data = self.text_box.get("1.0", "end-1c")

        if data.strip():
            try:
                # Convertir los datos pegados en un DataFrame
                df = read_data(data)

                # Ordenar de más antiguo a más reciente
                df = df.sort_values(by=['Fecha', 'Hora'])

                # Detectamos todas las columnas del DataFrame
                columns = df.columns.tolist()

                if not columns:
                    messagebox.showerror("Error", "No se detectaron columnas en los datos.")
                    return
                
                # Concatenar las columnas
                sql_query = concatenate_columns(df)

                # Exportar a archivo
                if getattr(sys, 'frozen', False):
                    output_folder = Path(sys.executable).parent
                else:
                    output_folder = Path(__file__).parent
                
                file_counter = len(list(output_folder.glob("Precip*.txt"))) + 1
                file_name = f'Precip_{file_counter}.txt'
                full_path = Path(output_folder) / file_name

                unique_file_path = get_unique_filename(full_path)
                save_to_txt(sql_query, unique_file_path)
                messagebox.showinfo("Éxito", f"Datos procesados y exportados correctamente.\n\nArchivo guardado en:\n{unique_file_path}")
            
            except Exception as e:
                messagebox.showerror("Error al procesar", f"Ocurrió un error:\n\n{str(e)}")
        else:
            messagebox.showerror("Error", "Por favor, pega los datos en el cuadro de texto.")

    def clear_content(self):
        """Borra el contenido del cuadro de texto."""
        self.text_box.delete("1.0", "end")
    
    def exit_app(self):
        self.destroy()

# ========================================================
# EJECUCIÓN DE LA APLICACIÓN
# ========================================================

if __name__ == "__main__":
    app = Application()
    app.mainloop()
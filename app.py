from datetime import datetime, date
import io
import os
import sqlite3
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st

st.set_page_config(
    page_title="Zestawienie Materiałów i Zakupów",
    page_icon="🛒",
    layout="wide",
)

DB_NAME = "zestawienie_materialow.db"

FONT_NAME = "Helvetica"
FONT_BOLD_NAME = "Helvetica-Bold"

try:
  if os.path.exists("Roboto.ttf"):
    pdfmetrics.registerFont(TTFont("Roboto", "Roboto.ttf"))
    FONT_NAME = "Roboto"
    if os.path.exists("Roboto-Bold.ttf"):
      pdfmetrics.registerFont(TTFont("Roboto-Bold", "Roboto-Bold.ttf"))
      FONT_BOLD_NAME = "Roboto-Bold"
    else:
      FONT_BOLD_NAME = "Roboto"
except Exception:
  pass


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS zestawienia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            client_name TEXT,
            order_date TEXT,
            notes TEXT
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS pozycje_materialowe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zestawienie_id INTEGER,
            producent TEXT,
            kategoria TEXT,
            nazwa_materialu TEXT,
            symbol_katalogowy TEXT,
            ilosc REAL,
            jednostka TEXT,
            uwagi TEXT,
            FOREIGN KEY (zestawienie_id) REFERENCES zestawienia (id) ON DELETE CASCADE
        )
    """)
  try:
    cursor.execute("ALTER TABLE pozycje_materialowe ADD COLUMN producent TEXT;")
  except sqlite3.OperationalError:
    pass
  try:
    cursor.execute("ALTER TABLE pozycje_materialowe ADD COLUMN uwagi TEXT;")
  except sqlite3.OperationalError:
    pass

  conn.commit()
  conn.close()


init_db()


def get_catalog_suggestion(producent, nazwa):
  n = nazwa.lower()
  if producent == "Schneider Electric":
    if "b16" in n and "1p" in n:
      return "Schneider A9K24116"
    if "b10" in n and "1p" in n:
      return "Schneider A9K24110"
    if "c20" in n and "3p" in n:
      return "Schneider A9K24320"
    if "b16" in n and "3p" in n:
      return "Schneider A9K24316"
    if "rcbo" in n:
      return "Schneider EZ9D15616"
    if "różnicow" in n:
      return "Schneider A9R64440"
    if "ochronnik" in n or "b+c" in n:
      return "Schneider PRD1"
    if "główny" in n or "odłącznik" in n:
      return "Schneider SB340"
  elif producent == "Eaton":
    if "b16" in n and "1p" in n:
      return "Eaton PLSM-B16/1"
    if "b10" in n and "1p" in n:
      return "Eaton PLSM-B10/1"
    if "c20" in n and "3p" in n:
      return "Eaton PLSM-C20/3"
    if "b16" in n and "3p" in n:
      return "Eaton PLSM-B16/3"
    if "rcbo" in n:
      return "Eaton PKPM2-16/1N/B/003-A"
    if "różnicow" in n:
      return "Eaton PFIM-40/4/003-A"
    if "ochronnik" in n or "b+c" in n:
      return "Eaton SPCT2-335/4"
  elif producent == "Hager":
    if "b16" in n and "1p" in n:
      return "Hager MBN116"
    if "b10" in n and "1p" in n:
      return "Hager MBN110"
    if "c20" in n and "3p" in n:
      return "Hager MCN320"
    if "b16" in n and "3p" in n:
      return "Hager MBN316"
    if "różnicow" in n:
      return "Hager CD440J"
    if "obudowa" in n or "rozdzielnica" in n:
      return "Hager FW424FT"
  return None


class NumberedCanvas(canvas.Canvas):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._saved_page_states = []

  def showPage(self):
    self._saved_page_states.append(dict(self.__dict__))
    self._startPage()

  def save(self):
    num_pages = len(self._saved_page_states)
    for state in self._saved_page_states:
      self.__dict__.update(state)
      self.draw_page_number(num_pages)
      super().showPage()
    super().save()

  def draw_page_number(self, page_count):
    self.saveState()
    self.setFont(FONT_NAME, 8)
    self.setFillColorRGB(0.3, 0.3, 0.3)
    txt = f"Strona {self._pageNumber} z {page_count}  |  Zestawienie materiałowe"
    self.drawRightString(A4[0] - 2 * cm, 1.5 * cm, txt)
    self.restoreState()


def generate_pdf(client_data, materials_data):
  buffer = io.BytesIO()
  doc = SimpleDocTemplate(
      buffer,
      pagesize=A4,
      rightMargin=1.5 * cm,
      leftMargin=1.5 * cm,
      topMargin=2 * cm,
      bottomMargin=2.0 * cm,
  )

  story = []
  styles = getSampleStyleSheet()

  title_style = ParagraphStyle(
      'DocTitle', parent=styles['Heading1'], fontName=FONT_BOLD_NAME, fontSize=18, leading=22, textColor='#1e293b', spaceAfter=6
  )
  subtitle_style = ParagraphStyle(
      'DocSubtitle', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10, leading=14, textColor='#64748b'
  )
  section_header = ParagraphStyle(
      'SectionHeader', parent=styles['Heading2'], fontName=FONT_BOLD_NAME, fontSize=12, leading=16, textColor='#0f172a', spaceBefore=10, spaceAfter=6
  )
  cell_style = ParagraphStyle(
      'CellText', parent=styles['Normal'], fontName=FONT_NAME, fontSize=8, leading=11, textColor='#1e293b'
  )
  cell_header_style = ParagraphStyle(
      'CellHeaderText', parent=styles['Normal'], fontName=FONT_BOLD_NAME, fontSize=8, leading=11, textColor='#ffffff'
  )
  cell_right = ParagraphStyle('CellRight', parent=cell_style, alignment=2)
  cell_header_right = ParagraphStyle('CellHeaderRight', parent=cell_header_style, alignment=2)

  story.append(Paragraph("Zestawienie Materiałów do Zakupu", title_style))
  story.append(Paragraph(f"Data generowania: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
  story.append(Spacer(1, 0.4 * cm))
  story.append(HRFlowable(width='100%', thickness=1.5, color='#cbd5e1', spaceAfter=15))

  info_data = [
      [Paragraph("<b>Nazwa zlecenia / Obiekt:</b>", cell_style), Paragraph(client_data['project_name'], cell_style), Paragraph("<b>Data:</b>", cell_style), Paragraph(str(client_data['date']), cell_style)],
      [Paragraph("<b>Inwestor / Klient:</b>", cell_style), Paragraph(client_data['client_name'], cell_style), Paragraph("<b>Uwagi:</b>", cell_style), Paragraph(client_data['notes'] or "Brak", cell_style)],
  ]
  info_table = Table(info_data, colWidths=[4.0 * cm, 6.0 * cm, 2.5 * cm, 5.5 * cm])
  info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
  story.append(info_table)
  story.append(Spacer(1, 0.5 * cm))

  story.append(Paragraph("Lista wymaganych aparatów i materiałów", section_header))

  table_content = [[
      Paragraph("<b>Lp.</b>", cell_header_style),
      Paragraph("<b>Producent</b>", cell_header_style),
      Paragraph("<b>Kategoria</b>", cell_header_style),
      Paragraph("<b>Nazwa / Model elementu</b>", cell_header_style),
      Paragraph("<b>Symbol katalogowy</b>", cell_header_style),
      Paragraph("<b>Ilość</b>", cell_header_right),
      Paragraph("<b>Jedn.</b>", cell_header_style),
      Paragraph("<b>Uwagi / Przeznaczenie</b>", cell_header_style),
  ]]

  for idx, row in enumerate(materials_data, 1):
    table_content.append([
        Paragraph(str(idx), cell_style),
        Paragraph(str(row['Producent']), cell_style),
        Paragraph(str(row['Kategoria']), cell_style),
        Paragraph(str(row['Nazwa materiału']), cell_style),
        Paragraph(str(row['Symbol katalogowy']), cell_style),
        Paragraph(f"{row['Ilość']:.2f}", cell_right),
        Paragraph(str(row['Jednostka']), cell_style),
        Paragraph(str(row['Uwagi']), cell_style),
    ])

  materials_table = Table(table_content, colWidths=[0.8 * cm, 2.2 * cm, 2.2 * cm, 3.8 * cm, 2.8 * cm, 1.1 * cm, 1.1 * cm, 3.8 * cm])
  materials_table.setStyle(TableStyle([
      ('BACKGROUND', (0, 0), (-1, 0), '#334155'),
      ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
      ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
      ('TOPPADDING', (0, 0), (-1, -1), 4),
      ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
      ('GRID', (0, 0), (-1, -1), 0.5, '#cbd5e1'),
      ('ROWBACKGROUNDS', (0, 1), (-1, -1), ['#ffffff', '#f8fafc']),
  ]))
  story.append(materials_table)

  doc.build(story, canvasmaker=NumberedCanvas)
  buffer.seek(0)
  return buffer.getvalue()


st.title("🛒 Zestawienie Materiałów i Zakupów")

st.sidebar.header("📁 Baza Zestawień")


def get_all_zestawienia():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT id, project_name, client_name, order_date FROM zestawienia ORDER BY id DESC")
  rows = cursor.fetchall()
  conn.close()
  return rows


zest_list = get_all_zestawienia()
zest_options = {"Nowe zestawienie / Szablon domyślny": None}
for z in zest_list:
  zest_options[f"[{z[0]}] {z[1]} ({z[2]}) - {z[3]}"] = z[0]

selected_zest_label = st.sidebar.selectbox("Wybierz zapisane zestawienie:", list(zest_options.keys()))
selected_zest_id = zest_options[selected_zest_label]

if selected_zest_id is not None:
  if st.sidebar.button("🗑️ Usuń to zestawienie z bazy", type="primary", width="stretch"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM zestawienia WHERE id = ?", (selected_zest_id,))
    cursor.execute("DELETE FROM pozycje_materialowe WHERE zestawienie_id = ?", (selected_zest_id,))
    conn.commit()
    conn.close()
    st.sidebar.success("Zestawienie zostało usunięte!")
    st.session_state['loaded_zest_id'] = None
    st.rerun()

default_materials_template = [
    {"Producent": "Hager", "Kategoria": "Obudowa", "Nazwa materiału": "Rozdzielnica podtynkowa FW424FT", "Symbol katalogowy": "Hager FW424FT", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Główna rozdzielnica wnękowa"},
    {"Producent": "Schneider Electric", "Kategoria": "Ochrona", "Nazwa materiału": "Ochronnik przepięciowy Klasy I+II (B+C)", "Symbol katalogowy": "Schneider PRD1", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Ochrona przepięciowa i piorunowa"},
    {"Producent": "Schneider Electric", "Kategoria": "Zasilanie główne", "Nazwa materiału": "Wyłącznik główny / odłącznik izolacyjny", "Symbol katalogowy": "Schneider SB340", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Główny odłącznik prądu"},
    {"Producent": "Schneider Electric", "Kategoria": "Pomiar / Kontrola", "Nazwa materiału": "Cyfrowy wskaźnik napięcia 3-fazowy", "Symbol katalogowy": "LED 3F", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Bieżący podgląd napięcia na fazach"},
    {"Producent": "Eaton", "Kategoria": "Siła / Ogrzewanie", "Nazwa materiału": "Wyłącznik nadprądowy C20 (3P)", "Symbol katalogowy": "Eaton PLSM-C20/3", "Ilość": 2.0, "Jednostka": "szt.", "Uwagi": "Zasilanie pompy ciepła, gniazdo siłowe"},
    {"Producent": "Eaton", "Kategoria": "Siła / Kuchnia", "Nazwa materiału": "Wyłącznik nadprądowy B16 (3P)", "Symbol katalogowy": "Eaton PLSM-B16/3", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Płyta indukcyjna"},
    {"Producent": "Schneider Electric", "Kategoria": "Aparatura RCBO", "Nazwa materiału": "RCBO 1P+N, B16, 30mA, Typ A", "Symbol katalogowy": "Schneider EZ9D15616", "Ilość": 7.0, "Jednostka": "szt.", "Uwagi": "Lodówka, pralka, suszarka, piekarnik"},
    {"Producent": "Eaton", "Kategoria": "Różnicówki główne", "Nazwa materiału": "Wyłącznik różnicowoprądowy 40A 4P 30mA", "Symbol katalogowy": "Eaton PFIM-40/4/003-A", "Ilość": 3.0, "Jednostka": "szt.", "Uwagi": "Główne różnicówki dla grup gniazd"},
    {"Producent": "Eaton", "Kategoria": "Nadprądowe (Gniazda)", "Nazwa materiału": "Wyłącznik nadprądowy B16 (1P)", "Symbol katalogowy": "Eaton PLSM-B16/1", "Ilość": 12.0, "Jednostka": "szt.", "Uwagi": "Gniazda ogólne, kotłownia, alarm"},
    {"Producent": "Eaton", "Kategoria": "Nadprądowe (Światło)", "Nazwa materiału": "Wyłącznik nadprądowy B10 (1P)", "Symbol katalogowy": "Eaton PLSM-B10/1", "Ilość": 12.0, "Jednostka": "szt.", "Uwagi": "Oświetlenie wewnętrzne i zewnętrzne"},
    {"Producent": "Schneider Electric", "Kategoria": "Akcesoria", "Nazwa materiału": "Szyna grzebieniowa widłowa 3F oraz 1F", "Symbol katalogowy": "Szyna grzebieniowa", "Ilość": 1.0, "Jednostka": "kpl.", "Uwagi": "Do mostkowania aparatów w rzędach"},
    {"Producent": "Hager", "Kategoria": "Akcesoria", "Nazwa materiału": "Przewód montażowy LgY 10 mm²", "Symbol katalogowy": "LgY 10mm²", "Ilość": 5.0, "Jednostka": "m", "Uwagi": "Żółto-zielony, niebieski, czarny"},
]

if 'loaded_zest_id' not in st.session_state:
  st.session_state['loaded_zest_id'] = None

if selected_zest_id != st.session_state['loaded_zest_id']:
  st.session_state['loaded_zest_id'] = selected_zest_id
  if selected_zest_id is not None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT project_name, client_name, order_date, notes FROM zestawienia WHERE id = ?", (selected_zest_id,))
    z_data = cursor.fetchone()

    cursor.execute("SELECT producent, kategoria, nazwa_materialu, symbol_katalogowy, ilosc, jednostka, uwagi FROM pozycje_materialowe WHERE zestawienie_id = ?", (selected_zest_id,))
    p_data = cursor.fetchall()
    conn.close()

    if z_data:
      st.session_state['project_name'] = z_data[0]
      st.session_state['client_name'] = z_data[1]
      try:
        st.session_state['order_date'] = datetime.strptime(z_data[2], "%Y-%m-%d").date()
      except:
        st.session_state['order_date'] = datetime.now().date()
      st.session_state['notes'] = z_data[3]

      loaded_mats = []
      for p in p_data:
        loaded_mats.append({
            "Producent": p[0] or "Schneider Electric",
            "Kategoria": p[1],
            "Nazwa materiału": p[2],
            "Symbol katalogowy": p[3],
            "Ilość": p[4],
            "Jednostka": p[5],
            "Uwagi": p[6]
        })
      st.session_state['materials_list'] = loaded_mats
      st.rerun()
  else:
    st.session_state['project_name'] = "Instalacja elektryczna - Dom jednorodzinny"
    st.session_state['client_name'] = "Radek Rutka"
    st.session_state['order_date'] = datetime.now().date()
    st.session_state['notes'] = "Zestawienie aparatury modułowej (Schneider, Hager, Eaton)."
    st.session_state['materials_list'] = default_materials_template
    st.rerun()

if 'project_name' not in st.session_state:
  st.session_state['project_name'] = "Instalacja elektryczna - Dom jednorodzinny"
if 'client_name' not in st.session_state:
  st.session_state['client_name'] = "Radek Rutka"
if 'order_date' not in st.session_state:
  st.session_state['order_date'] = datetime.now().date()
if 'notes' not in st.session_state:
  st.session_state['notes'] = "Zestawienie aparatury modułowej (Schneider, Hager, Eaton)."
if 'materials_list' not in st.session_state:
  st.session_state['materials_list'] = default_materials_template

st.subheader("1. Informacje o projekcie / zleceniu")
col1, col2, col3 = st.columns(3)

with col1:
  project_name = st.text_input("Nazwa zlecenia / Obiekt", value=st.session_state['project_name'])
  client_name = st.text_input("Inwestor / Klient", value=st.session_state['client_name'])

with col2:
  order_date = st.date_input("Data zestawienia", value=st.session_state['order_date'])

with col3:
  notes = st.text_area("Uwagi do zamówienia", value=st.session_state['notes'], height=68)

st.divider()

st.subheader("2. Tabela materiałów, zabezpieczeń i aparatury")
st.markdown("Wybierz producenta i wpisz nazwę aparatu – symbol katalogowy dopasuje się automatycznie.")

df_materials = pd.DataFrame(st.session_state['materials_list'])

if 'Producent' not in df_materials.columns:
  df_materials['Producent'] = "Schneider Electric"
if 'Kategoria' not in df_materials.columns:
  df_materials['Kategoria'] = "Zabezpieczenia"
if 'Nazwa materiału' not in df_materials.columns:
  df_materials['Nazwa materiału'] = ""
if 'Symbol katalogowy' not in df_materials.columns:
  df_materials['Symbol katalogowy'] = ""
if 'Ilość' not in df_materials.columns:
  df_materials['Ilość'] = 1.0
if 'Jednostka' not in df_materials.columns:
  df_materials['Jednostka'] = "szt."
if 'Uwagi' not in df_materials.columns:
  df_materials['Uwagi'] = ""

edited_df = st.data_editor(
    df_materials,
    num_rows="dynamic",
    width="stretch",
    column_config={
        "Producent": st.column_config.SelectboxColumn("Producent", options=["Schneider Electric", "Hager", "Eaton", "Inny"], required=True, width="medium"),
        "Kategoria": st.column_config.TextColumn("Kategoria / Obwód", required=True, width="medium"),
        "Nazwa materiału": st.column_config.TextColumn("Nazwa / Model elementu", required=True, width="large"),
        "Symbol katalogowy": st.column_config.TextColumn("Symbol katalogowy", required=False, width="medium"),
        "Ilość": st.column_config.NumberColumn("Ilość", min_value=0.0, format="%.2f", step=1.0),
        "Jednostka": st.column_config.SelectboxColumn("Jedn.", options=["szt.", "m", "op.", "kpl."], required=True),
        "Uwagi": st.column_config.TextColumn("Uwagi / Przeznaczenie", required=False, width="large"),
    },
)

# Automatyczne nadpisywanie symbolu katalogowego przy zmianie producenta lub nazwy
for i, row in edited_df.iterrows():
  if pd.isna(row['Producent']) or row['Producent'] == "":
    edited_df.at[i, 'Producent'] = "Schneider Electric"
  if pd.isna(row['Kategoria']) or row['Kategoria'] == "":
    edited_df.at[i, 'Kategoria'] = "Ogólne"
  if pd.isna(row['Nazwa materiału']):
    edited_df.at[i, 'Nazwa materiału'] = ""

  prod = edited_df.at[i, 'Producent']
  nazwa = edited_df.at[i, 'Nazwa materiału']

  if nazwa.strip() != "":
    suggested_sym = get_catalog_suggestion(prod, nazwa)
    if suggested_sym:
      edited_df.at[i, 'Symbol katalogowy'] = suggested_sym

  if pd.isna(row['Ilość']) or row['Ilość'] == "":
    edited_df.at[i, 'Ilość'] = 1.0
  if pd.isna(row['Jednostka']) or row['Jednostka'] == "":
    edited_df.at[i, 'Jednostka'] = "szt."
  if pd.isna(row['Uwagi']):
    edited_df.at[i, 'Uwagi'] = ""

st.session_state['materials_list'] = edited_df.to_dict('records')

st.divider()

col_btn1, col_btn2 = st.columns(2)

with col_btn1:
  if st.button("💾 Zapisz zestawienie w bazie danych", type="secondary", width="stretch"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if selected_zest_id is not None:
      cursor.execute(
          """UPDATE zestawienia SET project_name=?, client_name=?, order_date=?, notes=? WHERE id=?""",
          (project_name, client_name, order_date.strftime("%Y-%m-%d"), notes, selected_zest_id),
      )
      cursor.execute("DELETE FROM pozycje_materialowe WHERE zestawienie_id = ?", (selected_zest_id,))
      zest_id = selected_zest_id
    else:
      cursor.execute(
          """INSERT INTO zestawienia (project_name, client_name, order_date, notes) VALUES (?, ?, ?, ?)""",
          (project_name, client_name, order_date.strftime("%Y-%m-%d"), notes),
      )
      zest_id = cursor.lastrowid

    for row in st.session_state['materials_list']:
      if str(row['Nazwa materiału']).strip() != "":
        cursor.execute(
            """INSERT INTO pozycje_materialowe (zestawienie_id, producent, kategoria, nazwa_materialu, symbol_katalogowy, ilosc, jednostka, uwagi) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (zest_id, row['Producent'], row['Kategoria'], row['Nazwa materiału'], row['Symbol katalogowy'], float(row['Ilość']), row['Jednostka'], row['Uwagi']),
        )

    conn.commit()
    conn.close()
    st.success("Zestawienie materiałowe zostało zapisane w bazie!")
    st.rerun()

with col_btn2:
  if st.button("📄 Generuj zestawienie w formacie PDF", type="primary", width="stretch"):
    if edited_df.empty:
      st.warning("Dodaj przynajmniej jedną pozycję materiałową przed wygenerowaniem PDF.")
    else:
      client_data = {
          "project_name": project_name,
          "client_name": client_name,
          "date": order_date,
          "notes": notes,
      }

      pdf_bytes = generate_pdf(client_data, st.session_state['materials_list'])

      st.success("Zestawienie PDF zostało wygenerowane pomyślnie!")
      st.download_button(
          label="📥 Pobierz listę zakupową (PDF)",
          data=pdf_bytes,
          file_name=f"Zestawienie_Materialow_{project_name.replace(' ', '_')}.pdf",
          mime="application/pdf",
          width="stretch",
      )

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

# Konfiguracja strony
st.set_page_config(
    page_title="Zestawienie Materiałów i Zakupów",
    page_icon="🛒",
    layout="wide",
)

DB_NAME = "zestawienie_materialow.db"

# Rejestracja czcionki Roboto z repozytorium dla polskich znaków w PDF
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


# Inicjalizacja bazy danych SQLite
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
            kategoria TEXT,
            nazwa_materialu TEXT,
            symbol_katalogowy TEXT,
            ilosc REAL,
            jednostka TEXT,
            FOREIGN KEY (zestawienie_id) REFERENCES zestawienia (id) ON DELETE CASCADE
        )
    """)
  conn.commit()
  conn.close()


init_db()


# Klasa do numerowania stron w PDF
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
    footer_text = (
        f"Strona {self._pageNumber} z {page_count}  |  Zestawienie materiałowe"
        " wygenerowane elektronicznie"
    )
    self.drawRightString(A4[0] - 2 * cm, 1.5 * cm, footer_text)
    self.restoreState()


# Funkcja generująca PDF z zestawieniem materiałów
def generate_pdf(client_data, materials_data):
  buffer = io.BytesIO()
  doc = SimpleDocTemplate(
      buffer,
      pagesize=A4,
      rightMargin=2 * cm,
      leftMargin=2 * cm,
      topMargin=2 * cm,
      bottomMargin=2.0 * cm,
  )

  story = []
  styles = getSampleStyleSheet()

  title_style = ParagraphStyle(
      'DocTitle',
      parent=styles['Heading1'],
      fontName=FONT_BOLD_NAME,
      fontSize=18,
      leading=22,
      textColor='#1e293b',
      spaceAfter=6,
  )

  subtitle_style = ParagraphStyle(
      'DocSubtitle',
      parent=styles['Normal'],
      fontName=FONT_NAME,
      fontSize=10,
      leading=14,
      textColor='#64748b',
  )

  section_header = ParagraphStyle(
      'SectionHeader',
      parent=styles['Heading2'],
      fontName=FONT_BOLD_NAME,
      fontSize=12,
      leading=16,
      textColor='#0f172a',
      spaceBefore=10,
      spaceAfter=6,
  )

  cell_style = ParagraphStyle(
      'CellText',
      parent=styles['Normal'],
      fontName=FONT_NAME,
      fontSize=9,
      leading=12,
      textColor='#1e293b',
  )

  cell_header_style = ParagraphStyle(
      'CellHeaderText',
      parent=styles['Normal'],
      fontName=FONT_BOLD_NAME,
      fontSize=9,
      leading=12,
      textColor='#ffffff',
  )

  cell_right = ParagraphStyle('CellRight', parent=cell_style, alignment=2)
  cell_header_right = ParagraphStyle(
      'CellHeaderRight', parent=cell_header_style, alignment=2
  )

  # Nagłówek dokumentu
  story.append(Paragraph("Zestawienie Materiałów do Zakupu", title_style))
  story.append(
      Paragraph(
          f"Data generowania: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
          subtitle_style,
      )
  )
  story.append(Spacer(1, 0.4 * cm))
  story.append(
      HRFlowable(
          width='100%', thickness=1.5, color='#cbd5e1', spaceAfter=15
      )
  )

  # Dane zlecenia
  info_data = [
      [
          Paragraph("<b>Nazwa zlecenia / Obiekt:</b>", cell_style),
          Paragraph(client_data['project_name'], cell_style),
          Paragraph("<b>Data:</b>", cell_style),
          Paragraph(str(client_data['date']), cell_style),
      ],
      [
          Paragraph("<b>Inwestor / Klient:</b>", cell_style),
          Paragraph(client_data['client_name'], cell_style),
          Paragraph("<b>Uwagi:</b>", cell_style),
          Paragraph(client_data['notes'] or "Brak", cell_style),
      ],
  ]

  info_table = Table(info_data, colWidths=[4.0 * cm, 6.0 * cm, 2.5 * cm, 4.5 * cm])
  info_table.setStyle(
      TableStyle([
          ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
      ])
  )
  story.append(info_table)
  story.append(Spacer(1, 0.5 * cm))

  # Tabela materiałów
  story.append(Paragraph("Lista wymaganych aparatów i materiałów", section_header))

  table_content = [[
      Paragraph("<b>Lp.</b>", cell_header_style),
      Paragraph("<b>Kategoria / Obwód</b>", cell_header_style),
      Paragraph("<b>Nazwa / Opis materiału</b>", cell_header_style),
      Paragraph("<b>Symbol katalogowy</b>", cell_header_style),
      Paragraph("<b>Ilość</b>", cell_header_right),
      Paragraph("<b>Jedn.</b>", cell_header_style),
  ]]

  for idx, row in enumerate(materials_data, 1):
    table_content.append([
        Paragraph(str(idx), cell_style),
        Paragraph(str(row['Kategoria']), cell_style),
        Paragraph(str(row['Nazwa materiału']), cell_style),
        Paragraph(str(row['Symbol katalogowy']), cell_style),
        Paragraph(f"{row['Ilość']:.2f}", cell_right),
        Paragraph(str(row['Jednostka']), cell_style),
    ])

  materials_table = Table(
      table_content, colWidths=[1.0 * cm, 3.5 * cm, 5.5 * cm, 4.0 * cm, 1.5 * cm, 1.5 * cm]
  )
  materials_table.setStyle(
      TableStyle([
          ('BACKGROUND', (0, 0), (-1, 0), '#334155'),
          ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('TOPPADDING', (0, 0), (-1, -1), 5),
          ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
          ('GRID', (0, 0), (-1, -1), 0.5, '#cbd5e1'),
          ('ROWBACKGROUNDS', (0, 1), (-1, -1), ['#ffffff', '#f8fafc']),
      ])
  )
  story.append(materials_table)

  doc.build(story, canvasmaker=NumberedCanvas)
  buffer.seek(0)
  return buffer.getvalue()


# Interfejs aplikacji Streamlit
st.title("🛒 Zestawienie Materiałów i Zakupów")

# Sidebar - Baza zapisanych zestawień
st.sidebar.header("📁 Baza Zestawień")


def get_all_zestawienia():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT id, project_name, client_name, order_date FROM zestawienia ORDER BY id DESC")
  rows = cursor.fetchall()
  conn.close()
  return rows


zest_list = get_all_zestawienia()
zest_options = {"Nowe zestawienie / Wyczyść formularz": None}
for z in zest_list:
  zest_options[f"[{z[0]}] {z[1]} ({z[2]}) - {z[3]}"] = z[0]

selected_zest_label = st.sidebar.selectbox("Wybierz zapisane zestawienie:", list(zest_options.keys()))
selected_zest_id = zest_options[selected_zest_label]

if selected_zest_id is not None:
  if st.sidebar.button("🗑️ Usuń to zestawienie z bazy", type="primary"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM zestawienia WHERE id = ?", (selected_zest_id,))
    cursor.execute("DELETE FROM pozycje_materialowe WHERE zestawienie_id = ?", (selected_zest_id,))
    conn.commit()
    conn.close()
    st.sidebar.success("Zestawienie zostało usunięte!")
    st.session_state['loaded_zest_id'] = None
    st.rerun()

# Stan sesji
if 'loaded_zest_id' not in st.session_state:
  st.session_state['loaded_zest_id'] = None

if selected_zest_id != st.session_state['loaded_zest_id']:
  st.session_state['loaded_zest_id'] = selected_zest_id
  if selected_zest_id is not None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT project_name, client_name, order_date, notes FROM zestawienia WHERE id = ?", (selected_zest_id,))
    z_data = cursor.fetchone()

    cursor.execute("SELECT kategoria, nazwa_materialu, symbol_katalogowy, ilosc, jednostka FROM pozycje_materialowe WHERE zestawienie_id = ?", (selected_zest_id,))
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
            "Kategoria": p[0],
            "Nazwa materiału": p[1],
            "Symbol katalogowy": p[2],
            "Ilość": p[3],
            "Jednostka": p[4]
        })
      st.session_state['materials_list'] = loaded_mats
      st.rerun()
  else:
    st.session_state['project_name'] = "Instalacja elektryczna - Rozdzielnica główna"
    st.session_state['client_name'] = "Radek Rutka"
    st.session_state['order_date'] = datetime.now().date()
    st.session_state['notes'] = "Zestawienie aparatury modułowej Schneider Easy9."
    st.session_state['materials_list'] = [
        {"Kategoria": "Ochronniki", "Nazwa materiału": "Ochronnik przepięciowy Klasy I+II (B+C)", "Symbol katalogowy": "Schneider PRD1", "Ilość": 1.0, "Jednostka": "szt."},
        {"Kategoria": "Zabezpieczenia", "Nazwa materiału": "Wyłącznik nadprądowy 1P B16", "Symbol katalogowy": "Schneider Easy9 EZ9F34116", "Ilość": 10.0, "Jednostka": "szt."},
        {"Kategoria": "Zabezpieczenia", "Nazwa materiału": "Wyłącznik różnicowoprądowy 4P 40A 30mA", "Symbol katalogowy": "Schneider Easy9 EZ9R54440", "Ilość": 2.0, "Jednostka": "szt."},
    ]
    st.rerun()

if 'project_name' not in st.session_state:
  st.session_state['project_name'] = "Instalacja elektryczna - Rozdzielnica główna"
if 'client_name' not in st.session_state:
  st.session_state['client_name'] = "Radek Rutka"
if 'order_date' not in st.session_state:
  st.session_state['order_date'] = datetime.now().date()
if 'notes' not in st.session_state:
  st.session_state['notes'] = "Zestawienie aparatury modułowej Schneider Easy9."
if 'materials_list' not in st.session_state:
  st.session_state['materials_list'] = [
      {"Kategoria": "Ochronniki", "Nazwa materiału": "Ochronnik przepięciowy Klasy I+II (B+C)", "Symbol katalogowy": "Schneider PRD1", "Ilość": 1.0, "Jednostka": "szt."},
      {"Kategoria": "Zabezpieczenia", "Nazwa materiału": "Wyłącznik nadprądowy 1P B16", "Symbol katalogowy": "Schneider Easy9 EZ9F34116", "Ilość": 10.0, "Jednostka": "szt."},
      {"Kategoria": "Zabezpieczenia", "Nazwa materiału": "Wyłącznik różnicowoprądowy 4P 40A 30mA", "Symbol katalogowy": "Schneider Easy9 EZ9R54440", "Ilość": 2.0, "Jednostka": "szt."},
  ]

# Sekcja 1: Dane zlecenia
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

# Sekcja 2: Tabela materiałów
st.subheader("2. Tabela materiałów i aparatury")
st.markdown("Wprowadź kategorie obwodów, nazwy materiałów oraz symbole katalogowe (np. Schneider Easy9, PRD1).")

df_materials = pd.DataFrame(st.session_state['materials_list'])
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

edited_df = st.data_editor(
    df_materials,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Kategoria": st.column_config.TextColumn("Kategoria / Obwód", required=True, width="medium"),
        "Nazwa materiału": st.column_config.TextColumn("Nazwa / Opis materiału", required=True, width="large"),
        "Symbol katalogowy": st.column_config.TextColumn("Symbol katalogowy (np. Easy9)", required=False, width="medium"),
        "Ilość": st.column_config.NumberColumn("Ilość", min_value=0.0, format="%.2f", step=1.0),
        "Jednostka": st.column_config.SelectboxColumn("Jedn.", options=["szt.", "m", "op.", "kpl."], required=True),
    },
)

# Walidacja i czyszczenie danych
for i, row in edited_df.iterrows():
  if pd.isna(row['Kategoria']) or row['Kategoria'] == "":
    edited_df.at[i, 'Kategoria'] = "Ogólne"
  if pd.isna(row['Nazwa materiału']):
    edited_df.at[i, 'Nazwa materiału'] = ""
  if pd.isna(row['Symbol katalogowy']):
    edited_df.at[i, 'Symbol katalogowy'] = ""
  if pd.isna(row['Ilość']) or row['Ilość'] == "":
    edited_df.at[i, 'Ilość'] = 1.0
  if pd.isna(row['Jednostka']) or row['Jednostka'] == "":
    edited_df.at[i, 'Jednostka'] = "szt."

st.session_state['materials_list'] = edited_df.to_dict('records')

st.divider()

# Przyciski akcji: Zapis do bazy oraz Generowanie PDF
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
  if st.button("💾 Zapisz zestawienie w bazie danych", type="secondary", use_container_width=True):
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
            """INSERT INTO pozycje_materialowe (zestawienie_id, kategoria, nazwa_materialu, symbol_katalogowy, ilosc, jednostka) VALUES (?, ?, ?, ?, ?, ?)""",
            (zest_id, row['Kategoria'], row['Nazwa materiału'], row['Symbol katalogowy'], float(row['Ilość']), row['Jednostka']),
        )

    conn.commit()
    conn.close()
    st.success("Zestawienie materiałowe zostało zapisane w bazie!")
    st.rerun()

with col_btn2:
  if st.button("📄 Generuj zestawienie w formacie PDF", type="primary", use_container_width=True):
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
          use_container_width=True,
      )

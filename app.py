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


# Inicjalizacja bazy danych SQLite z uwzględnieniem kolumny producenta
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
      rightMargin=1.5 * cm,
      leftMargin=1.5 * cm,
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
      fontSize=8,
      leading=11,
      textColor='#1e293b',
  )

  cell_header_style = ParagraphStyle(
      'CellHeaderText',
      parent=styles['Normal'],
      fontName=FONT_BOLD_NAME,
      fontSize=8,
      leading=11,
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

  info_table = Table(info_data, colWidths=[4.0 * cm, 6.0 * cm, 2.5 * cm, 5.5 * cm])
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

  materials_table = Table(
      table_content, colWidths=[0.8 * cm, 2.2 * cm, 2.2 * cm, 3.8 * cm, 2.8 * cm, 1.1 * cm, 1.1 * cm, 3.8 * cm]
  )
  materials_table.setStyle(
      TableStyle([
          ('BACKGROUND', (0, 0), (-1, 0), '#334155'),
          ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('TOPPADDING', (0, 0), (-1, -1), 4),
          ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
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

# Domyślny szablon materiałów z przypisanymi producentami
default_materials_template = [
    {"Producent": "Hager", "Kategoria": "Obudowa", "Nazwa materiału": "Rozdzielnica podtynkowa FW424FT (4x24M, drzwi metalowe)", "Symbol katalogowy": "Hager FW424FT", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Główna rozdzielnica wnękowa"},
    {"Producent": "Schneider Electric", "Kategoria": "Ochrona", "Nazwa materiału": "Ochronnik przepięciowy Klasy I+II (B+C)", "Symbol katalogowy": "Schneider PRD1", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Ochrona przepięciowa i piorunowa"},
    {"Producent": "Schneider Electric", "Kategoria": "Zasilanie główne", "Nazwa materiału": "Wyłącznik główny / odłącznik izolacyjny SB340 (3P, 40A)", "Symbol katalogowy": "Schneider SB340", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Główny odłącznik prądu"},
    {"Producent": "Schneider Electric", "Kategoria": "Pomiar / Kontrola", "Nazwa materiału": "Cyfrowy wskaźnik napięcia 3-fazowy (woltomierz LED)", "Symbol katalogowy": "LED 3F", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Bieżący podgląd napięcia na fazach"},
    {"Producent": "Eaton", "Kategoria": "Siła / Ogrzewanie", "Nazwa materiału": "Wyłącznik nadprądowy C20 (3P)", "Symbol katalogowy": "Eaton PLSM-C20/3", "Ilość": 2.0, "Jednostka": "szt.", "Uwagi": "Zasilanie pompy ciepła, gniazdo siłowe garaż"},
    {"Producent": "Eaton", "Kategoria": "Siła / Kuchnia", "Nazwa materiału": "Wyłącznik nadprądowy B16 (3P)", "Symbol katalogowy": "Eaton PLSM-B16/3", "Ilość": 1.0, "Jednostka": "szt.", "Uwagi": "Płyta indukcyjna"},
    {"Producent": "Schneider Electric", "Kategoria": "Aparatura RCBO", "Nazwa materiału": "RCBO 1P+N, B16, 30mA, Typ A", "Symbol katalogowy": "Schneider EZ9D15616", "Ilość": 7.0, "Jednostka": "szt.", "Uwagi": "Lodówka, pralka, suszarka, piekarnik, zmywarka, łazienka, altana"},
    {"Producent": "Eaton", "Kategoria": "Różnicówki główne", "Nazwa materiału": "Wyłącznik różnicowoprądowy (40A, 4P, 30mA, Typ A)", "Symbol katalogowy": "Eaton PFIM-40/4/003-A", "Ilość": 3.0, "Jednostka": "szt.", "Uwagi": "Główne różnicówki dla grup gniazd i oświetlenia"},
    {"Producent": "Eaton", "Kategoria": "Nadprądowe (Gniazda)", "Nazwa materiału": "Wyłącznik nadprądowy B16 (1P)", "Symbol katalogowy": "Eaton PLSM-B16/1", "Ilość": 12.0, "Jednostka": "szt.", "Uwagi": "Gniazda ogólne, kotłownia, bramy i alarm"},
    {"Producent": "Eaton", "Kategoria": "Nadprądowe (Światło)", "Nazwa materiału": "Wyłącznik nadprądowy B10 (1P)", "Symbol katalogowy": "Eaton PLSM-B10/1", "Ilość": 12.0, "Jednostka": "szt.", "Uwagi": "Oświetlenie wewnętrzne i zewnętrzne"},
    {"Producent": "Schneider Electric", "Kategoria": "Akcesoria", "Nazwa materiału": "Szyna grzebieniowa widłowa 3F oraz 1F", "Symbol katalogowy": "Szyna grzebieniowa", "Ilość": 1.0, "Jednostka": "kpl.", "Uwagi": "Do mostkowania aparatów w rzędach"},
    {"Producent": "Hager", "Kategoria": "Akcesoria", "Nazwa materiału": "Przewód montażowy LgY 10 mm²", "Symbol katalogowy": "LgY 10mm²", "Ilość": 5.0, "Jednostka": "m", "Uwagi": "Żółto-zielony, niebieski, czarny"}
]

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
st.subheader("2. Tabela materiałów, zabezpieczeń i aparatury")
st.markdown("Wybierz producenta, kategorię obwodu, wpisz nazwę, symbol katalogowy oraz uwagi.")

df_materials = pd.DataFrame(st.session_state['materials_list'])
if 'Producent' not in df_materials.columns:
  df_materials['Producent'] = "Schneider Electric"
if 'Kategoria' not in df_materials.columns:
  df_materials['Kategoria'] = "Zabezpieczenia"
if 'Nazwa materiału' not in df_materials

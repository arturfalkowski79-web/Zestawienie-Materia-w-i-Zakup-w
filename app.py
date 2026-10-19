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
    {"Producent": "Schneider Electric", "Kategoria": "Aparatura RCBO", "Nazwa materiału": "RCBO 1P+N, B16, 30mA, Typ A", "Symbol katalogowy": "Schneider EZ9D15616", "Ilość": 7.0, "Jednostka": "szt.", "Uwagi": "Lodówka, pralka, suszarka, piekarnik, zmywarka, łazienka"},
    {"Producent": "Eaton", "Kategoria": "Różnicówki główne", "Nazwa materiału": "Wyłącznik różnicowoprądowy 40A 4P 30mA", "Symbol katalogowy": "Eaton PFIM-40/4/003-A", "Ilość": 3.0, "Jednostka": "szt.", "Uwagi": "Główne różnicówki dla grup gniazd i oświetlenia"},
    {"Producent": "Eaton", "Kategoria": "Nadprądowe (Gniazda)", "Nazwa materiału": "Wyłącznik nadprądowy B16 (1P)", "Symbol katalogowy":

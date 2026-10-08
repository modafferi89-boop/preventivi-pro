import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


def crea_template_preventivi():
  # Crea un nuovo workbook e seleziona il foglio attivo
  wb = openpyxl.Workbook()
  ws = wb.active
  ws.title = "Preventivo e Margini"

  # Assicura che la griglia sia visibile
  ws.views.sheetView[0].showGridLines = True

  # Definizione stili e colori (Palette professionale grigio/blu scuro)
  font_titolo = Font(name="Calibri", size=16, bold=True, color="1F497D")
  font_sezione = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
  font_label = Font(name="Calibri", size=11, bold=True)
  font_testo = Font(name="Calibri", size=11)
  font_totale = Font(name="Calibri", size=12, bold=True, color="000000")

  fill_sezione = PatternFill(
      start_color="1F497D", end_color="1F497D", fill_type="solid"
  )
  fill_input = PatternFill(
      start_color="F2F2F2", end_color="F2F2F2", fill_type="solid"
  )

  bordo_sottile = Border(
      left=Side(style="thin", color="D9D9D9"),
      right=Side(style="thin", color="D9D9D9"),
      top=Side(style="thin", color="D9D9D9"),
      bottom=Side(style="thin", color="D9D9D9"),
  )
  bordo_doppio = Border(
      top=Side(style="thin", color="000000"),
      bottom=Side(style="double", color="000000"),
  )

  # 1. Titolo del Foglio
  ws["B2"] = "CALCOLATORE PREVENTIVI & MARGINI"
  ws["B2"].font = font_titolo

  # 2. Dati del Professionista (Intestazione)
  ws["B4"] = "DATI PROFESSIONISTA"
  ws["B4"].font = font_sezione
  ws["B4"].fill = fill_sezione
  ws.merge_cells("B4:D4")

  campi_professionista = [
      ("Professionista:", "Vincenzo Modafferi"),
      ("Partita IVA:", "Inserisci P.IVA"),
      (
          "Recapito:",
          "+39 33334582365",
      ),  # Formattato direttamente con prefisso
      ("Contatti / Email:", "tuamail@email.com"),
  ]

  for i, (etichetta, val_default) in enumerate(campi_professionista, start=5):
    ws[f"B{i}"] = etichetta
    ws[f"B{i}"].font = font_label
    ws[f"C{i}"] = val_default
    ws[f"C{i}"].font = font_testo
    ws[f"C{i}"].fill = fill_input
    ws[f"B{i}"].border = bordo_sottile
    ws[f"C{i}"].border = bordo_sottile
    if etichetta == "Recapito:":
      ws[f"C{i}"].number_format = '"+39" #,##0'
      ws[f"C{i}"].alignment = Alignment(horizontal="left")

  # 3. Sezione Dati Cliente e Progetto
  ws["B10"] = "DATI CLIENTE E PROGETTO"
  ws["B10"].font = font_sezione
  ws["B10"].fill = fill_sezione
  ws.merge_cells("B10:D10")

  campi_cliente = [
      ("Cliente:", "Inserisci nome cliente"),
      ("Progetto:", "Nome del servizio o prodotto"),
      ("Data:", "GG/MM/AAAA"),
      ("Validità preventivo:", "30 giorni dalla data"),
  ]

  for i, (etichetta, placeholder) in enumerate(campi_cliente, start=11):
    ws[f"B{i}"] = etichetta
    ws[f"B{i}"].font = font_label
    ws[f"C{i}"] = placeholder
    ws[f"C{i}"].font = font_testo
    ws[f"C{i}"].fill = fill_input
    ws[f"B{i}"].border = bordo_sottile
    ws[f"C{i}"].border = bordo_sottile

  # 4. Sezione Costi e Calcoli
  ws["B16"] = "ANALISI COSTI E CALCOLO PREZZO"
  ws["B16"].font = font_sezione
  ws["B16"].fill = fill_sezione
  ws.merge_cells("B16:D16")

  righe_calcolo = [
      ("Ore stimate di lavoro", 15),
      ("Costo orario (€)", 35.00),
      ("Costi vivi / Materiali (€)", 50.00),
      ("Margine di guadagno desiderato (%)", 0.30),
  ]

  for i, (desc, val_default) in enumerate(righe_calcolo, start=17):
    ws[f"B{i}"] = desc
    ws[f"B{i}"].font = font_label
    ws[f"C{i}"] = val_default
    ws[f"C{i}"].font = font_testo
    ws[f"C{i}"].fill = fill_input
    ws[f"B{i}"].border = bordo_sottile
    ws[f"C{i}"].border = bordo_sottile
    if " (%)" in desc:
      ws[f"C{i}"].number_format = "0%"
    elif " (€)" in desc:
      ws[f"C{i}"].number_format = "#,##0.00 €"
    else:
      ws[f"C{i}"].number_format = "#,##0"

  # 5. Riepilogo / Output Finale con Formule
  ws["B22"] = "RIEPILOGO PREVENTIVO"
  ws["B22"].font = font_sezione
  ws["B22"].fill = fill_sezione
  ws.merge_cells("B22:D22")

  ws["B23"] = "Subtotale Lavorazione"
  ws["C23"] = "=(C17*C18)+C19"

  ws["B24"] = "Utile Stimato"
  ws["C24"] = "=C23*C20"

  ws["B25"] = "Subtotale Complessivo"
  ws["C25"] = "=C23+C24"

  ws["B26"] = "Sconto applicato (%)"
  ws["C26"] = 0.00

  ws["B27"] = "Totale Imponibile"
  ws["C27"] = "=C25*(1-C26)"

  ws["B28"] = "IVA (22%)"
  ws["C28"] = "=C27*0.22"

  ws["B29"] = "TOTALE COMPLESSIVO"
  ws["C29"] = "=C27+C28"

  for r in range(23, 30):
    ws[f"B{r}"].font = font_label
    ws[f"C{r}"].font = font_testo
    ws[f"B{r}"].border = bordo_sottile
    ws[f"C{r}"].border = bordo_sottile
    if r == 26:
      ws[f"C{r}"].number_format = "0%"
      ws[f"C{r}"].fill = fill_input
    else:
      ws[f"C{r}"].number_format = "#,##0.00 €"

  ws["B29"].font = font_totale
  ws["C29"].font = font_totale
  ws["B29"].border = bordo_doppio
  ws["C29"].border = bordo_doppio

  # 6. Condizioni di Pagamento
  ws["B31"] = "CONDIZIONI E TERMINI DI PAGAMENTO"
  ws["B31"].font = font_sezione
  ws["B31"].fill = fill_sezione
  ws.merge_cells("B31:D31")

  condizioni = [
      ("Modalità di pagamento:", "Bonifico Bancario"),
      ("Termini di pagamento:", "30% acconto, saldo a fine lavori"),
      ("Note / Consegna:", "Consegna prevista entro 15 giorni lavorativi"),
  ]

  for i, (etichetta, val) in enumerate(condizioni, start=32):
    ws[f"B{i}"] = etichetta
    ws[f"B{i}"].font = font_label
    ws[f"C{i}"] = val
    ws[f"C{i}"].font = font_testo
    ws[f"C{i}"].fill = fill_input
    ws[f"B{i}"].border = bordo_sottile
    ws[f"C{i}"].border = bordo_sottile

  ws.column_dimensions["A"].width = 4
  ws.column_dimensions["B"].width = 38
  ws.column_dimensions["C"].width = 25

  nome_file = "Calcolatore_Preventivi_Pro.xlsx"
  wb.save(nome_file)
  print(f"File generato con successo: {nome_file}")


if __name__ == "__main__":
  crea_template_preventivi()
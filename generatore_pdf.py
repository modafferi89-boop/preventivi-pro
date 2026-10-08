import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def crea_pdf_preventivo(dati: dict, calcoli: dict, filename="ultimo_preventivo.pdf"):
    static_dir = "static"
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    filepath = os.path.join(static_dir, filename)
    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []

    styles = getSampleStyleSheet()

    # Stili personalizzati
    style_header_destro = ParagraphStyle(
        'HeaderDestro',
        parent=styles['Normal'],
        alignment=2,  # Allineato a destra
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )

    style_titolo = ParagraphStyle(
        'TitoloPreventivo',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=15
    )

    style_etichetta = ParagraphStyle(
        'EtichettaMeta',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b')
    )

    style_valore = ParagraphStyle(
        'ValoreMeta',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1e293b')
    )

    style_totale_finale = ParagraphStyle(
        'TotaleFinale',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )

    # 1. Intestazione in alto a destra (Dati Professionista)
    prof_nome = dati.get('professionista', 'Vincenzo Modafferi')
    prof_piva = f"P.IVA: {dati.get('partita_iva')}" if dati.get('partita_iva') else ""
    prof_recapito = f"Tel: {dati.get('recapito')}" if dati.get('recapito') else ""
    prof_email = f"Email: {dati.get('email')}" if dati.get('email') else ""

    testo_header = f"<b>{prof_nome}</b><br/>{prof_piva}<br/>{prof_recapito}<br/>{prof_email}"
    story.append(Paragraph(testo_header, style_header_destro))
    story.append(Spacer(1, 20))

    # 2. Titolo del documento
    story.append(Paragraph("PREVENTIVO DI SPESA", style_titolo))

    # 3. Informazioni Cliente e Progetto (Tabella compatta)
    meta_data = [
        [Paragraph("Cliente:", style_etichetta), Paragraph(dati.get('cliente', ''), style_valore)],
        [Paragraph("Progetto:", style_etichetta), Paragraph(dati.get('progetto', ''), style_valore)],
        [Paragraph("Data:", style_etichetta), Paragraph(dati.get('data') or "Data odierna", style_valore)],
        [Paragraph("Validità:", style_etichetta), Paragraph(dati.get('validita', '30 giorni dalla data'), style_valore)]
    ]

    t_meta = Table(meta_data, colWidths=[80, 450])
    t_meta.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 20))

    # 4. Tabella Dettaglio Economico
    righe_tabella = [
        [Paragraph("<b>Descrizione Voce</b>", styles['Normal']), Paragraph("<b>Importo</b>", styles['Normal'])]
    ]

    # Recupero sicuro delle ore e del costo orario (controlla sia in calcoli che in dati)
    raw_ore = calcoli.get('ore_lavoro', dati.get('ore_lavoro', 0))
    if isinstance(raw_ore, float) and raw_ore.is_integer():
        ore = int(raw_ore)
    else:
        ore = raw_ore

    costo_orario = calcoli.get('costo_orario', dati.get('costo_orario', 0))
    sub_lav = calcoli.get('subtotale_lavorazione', raw_ore * costo_orario)

    righe_tabella.append([
        Paragraph(f"Subtotale Lavorazione ({ore} ore a {costo_orario:.2f} €/h)", styles['Normal']),
        Paragraph(f"{sub_lav:.2f} €", styles['Normal'])
    ])

    # Voci extra dinamiche
    voci_extra = calcoli.get('voci_extra', [])
    for voce in voci_extra:
        righe_tabella.append([
            Paragraph(f"Spesa Extra: {voce['descrizione']}", styles['Normal']),
            Paragraph(f"{voce['importo']:.2f} €", styles['Normal'])
        ])

    # Riga vuota di separazione
    righe_tabella.append([Paragraph("&nbsp;", styles['Normal']), Paragraph("&nbsp;", styles['Normal'])])

    # Subtotale Complessivo
    sub_compl = calcoli.get('subtotale_complessivo', 0)
    righe_tabella.append([Paragraph("<b>Subtotale Complessivo</b>", styles['Normal']),
                          Paragraph(f"<b>{sub_compl:.2f} €</b>", styles['Normal'])])

    # Sconto (se applicato)
    sconto_imp = calcoli.get('sconto_valore', 0)
    if sconto_imp > 0:
        righe_tabella.append(
            [Paragraph("Sconto Applicato", styles['Normal']), Paragraph(f"-{sconto_imp:.2f} €", styles['Normal'])])

    # Totale Imponibile
    imponibile = calcoli.get('totale_imponibile', 0)
    righe_tabella.append([Paragraph("<b>Totale Imponibile</b>", styles['Normal']),
                          Paragraph(f"<b>{imponibile:.2f} €</b>", styles['Normal'])])

    # IVA (22%)
    iva = calcoli.get('iva', 0)
    righe_tabella.append(
        [Paragraph("<b>IVA (22%)</b>", styles['Normal']), Paragraph(f"<b>{iva:.2f} €</b>", styles['Normal'])])

    # Totale Complessivo Finale
    totale_fin = calcoli.get('totale_complessivo_finale', calcoli.get('totale_finale', 0))

    righe_tabella.append([Paragraph("TOTALE COMPLESSIVO FINALE", style_totale_finale),
                          Paragraph(f"{totale_fin:.2f} €", style_totale_finale)])

    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1e3a8a')),
        ('TOPPADDING', (0, -1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
    ]

    t_economico = Table(righe_tabella, colWidths=[380, 150])
    t_economico.setStyle(TableStyle(t_style))

    story.append(t_economico)

    doc.build(story)
    return filepath
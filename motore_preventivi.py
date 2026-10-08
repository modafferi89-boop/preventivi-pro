def calcola_preventivo(ore_lavoro, costo_orario, margine_percentuale, sconto_percentuale, voci_extra=None):
    subtotale_lavorazione = ore_lavoro * costo_orario
    utile_stimato = subtotale_lavorazione * (margine_percentuale / 100.0)

    # Somma eventuali voci di spesa extra personalizzate
    totale_voci_extra = 0.0
    dettaglio_voci_extra = []
    if voci_extra:
        for voce in voci_extra:
            importo = float(voce.get("importo", 0))
            totale_voci_extra += importo
            dettaglio_voci_extra.append({"descrizione": voce.get("descrizione", "Spesa extra"), "importo": importo})

    subtotale_complessivo = subtotale_lavorazione + utile_stimato + totale_voci_extra

    sconto_valore = subtotale_complessivo * (sconto_percentuale / 100.0)
    totale_imponibile = subtotale_complessivo - sconto_valore

    iva = totale_imponibile * 0.22  # IVA al 22%
    totale_finale = totale_imponibile + iva

    return {
        "subtotale_lavorazione": round(subtotale_lavorazione, 2),
        "utile_stimato": round(utile_stimato, 2),
        "voci_extra": dettaglio_voci_extra,
        "totale_voci_extra": round(totale_voci_extra, 2),
        "subtotale_complessivo": round(subtotale_complessivo, 2),
        "sconto_valore": round(sconto_valore, 2),
        "totale_imponibile": round(totale_imponibile, 2),
        "iva": round(iva, 2),
        "totale_finale": round(totale_finale, 2),
        "totale_complessivo_finale": round(totale_finale, 2)
    }
import csv
import os
import re
import sys
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import requests

# Nome del file CSV di output unificato
FILE_CSV_MAPS = "contatti_estratti_maps.csv"

# Header per le richieste HTTP ai siti web
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def estrai_email_da_sito(url):
  """Visita il sito web dell'attività e cerca indirizzi email."""
  emails = set()
  try:
    response = requests.get(url, headers=HEADERS, timeout=8)
    if response.status_code == 200:
      soup = BeautifulSoup(response.text, "html.parser")
      for a in soup.find_all("a", href=True):
        if "mailto:" in a["href"]:
          email = a["href"].replace("mailto:", "").split("?")[0].strip()
          if email:
            emails.add(email)

      pattern_email = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
      trovate = re.findall(pattern_email, response.text)
      for email in trovate:
        if not any(
            email.lower().endswith(ext)
            for ext in [
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".js",
                ".css",
                ".webp",
                ".svg",
            ]
        ):
          emails.add(email)
  except:
    pass
  return list(emails)


def main():
  # 1. Se passato da riga di comando lo usa, altrimenti lo chiede nel terminale
  if len(sys.argv) >= 2:
    query_ricerca = sys.argv[1]
  else:
    print("\n--------------------------------------------------")
    query_ricerca = input(
        "🔎 Inserisci la categoria e la località (es. parrucchieri Reggio"
        " Calabria): "
    ).strip()
    if not query_ricerca:
      query_ricerca = "parrucchieri Reggio Calabria"  # Default di emergenza

  print(f"\n==============================================")
  print(
      f"🚀 Avvio ricerca silenziosa (senza browser visibile) per:"
      f" '{query_ricerca}'..."
  )
  print(f"==============================================")

  # Inizializza o prepara il file CSV con intestazione (se non esiste)
  file_esiste = os.path.exists(FILE_CSV_MAPS)
  csv_file = open(
      FILE_CSV_MAPS, mode="a", newline="", encoding="utf-8-sig"
  )
  fieldnames = [
      "Categoria Ricerca",
      "Nome Attività",
      "Telefono",
      "Email",
      "Sito Web",
      "Link Google Maps",
  ]
  writer = csv.DictWriter(csv_file, fieldnames=fieldnames, delimiter=";")
  if not file_esiste:
    writer.writeheader()

  with sync_playwright() as p:
    # headless=True fa girare tutto in background senza aprire finestre grafiche
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    url_maps = f"https://www.google.com/maps/search/{query_ricerca.replace(' ', '+')}"
    page.goto(url_maps)

    # Gestione cookie
    try:
      page.click('button:has-text("Accetta tutto")', timeout=3000)
    except:
      pass

    try:
      page.wait_for_selector('a[href*="/maps/place/"]', timeout=10000)
    except:
      print(f"⚠️ Nessun risultato trovato per '{query_ricerca}'.")
      browser.close()
      csv_file.close()
      return

    # Scorrimento della pagina per caricare i risultati in background
    print("🔄 Estrazione risultati in corso nel terminale...")
    for _ in range(4):
      try:
        feed = page.locator('div[role="feed"]')
        if feed.count() > 0:
          feed.evaluate("node => node.scrollBy(0, 1000)")
        else:
          page.mouse.wheel(0, 1500)
        time.sleep(2)
      except:
        pass

    # Raccolta dei link delle schede
    elementi = page.locator('a[href*="/maps/place/"]').all()
    urls_schede = []
    visti_urls = set()
    for el in elementi:
      try:
        href = el.get_attribute("href")
        if href and href not in visti_urls:
          visti_urls.add(href)
          urls_schede.append(href)
      except:
        continue

    print(
        f"📊 Trovate {len(urls_schede)} schede. Elaborazione dati su terminale..."
    )

    # Analisi delle schede (prime 15 per sessione)
    for index, url_scheda in enumerate(urls_schede[:15], start=1):
      try:
        print(f"   -> Analisi {index}/{min(len(urls_schede), 15)}...")
        page.goto(url_scheda)
        time.sleep(2)

        # Nome attività
        nome_attivita = "N/D"
        try:
          nome_attivita = page.locator("h1").inner_text(timeout=3000)
        except:
          pass

        # Telefono
        telefono = "N/D"
        try:
          tel_element = page.locator('button[data-item-id^="phone:tel:"]')
          if tel_element.count() > 0:
            aria_label = tel_element.get_attribute("aria-label")
            if aria_label:
              telefono = aria_label.split(":")[-1].strip()
        except:
          pass

        # Sito Web
        sito_web = "N/D"
        try:
          sito_element = page.locator('a[data-item-id="authority"]')
          if sito_element.count() > 0:
            sito_web = sito_element.get_attribute("href")
        except:
          pass

        # Ricerca email
        lista_email = []
        try:
          page_text = page.locator("body").inner_text()
          pattern_email = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
          for em in re.findall(pattern_email, page_text):
            if not any(
                x in em
                for x in [
                    "google",
                    "gstatic",
                    "sentry",
                    "schema",
                    "w3.org",
                    "example",
                ]
            ):
              lista_email.append(em)
        except:
          pass

        if sito_web != "N/D":
          for em in estrai_email_da_sito(sito_web):
            if em not in lista_email:
              lista_email.append(em)

        stringa_email = (
            ", ".join(set(lista_email)) if lista_email else "Non trovata"
        )

        print(
            f"      ✅ [{nome_attivita}] | Tel: {telefono} | Email:"
            f" {stringa_email}"
        )

        # Scrittura immediata nel CSV
        writer.writerow({
            "Categoria Ricerca": query_ricerca,
            "Nome Attività": nome_attivita,
            "Telefono": telefono,
            "Email": stringa_email,
            "Sito Web": sito_web,
            "Link Google Maps": url_scheda,
        })
        csv_file.flush()

      except Exception as e:
        print(f"      ⚠️ Errore sulla scheda: {e}")
        continue

    browser.close()
    csv_file.close()

  print(f"\n==============================================")
  print(f"🎉 RICERCA COMPLETATA!")
  print(f"📂 Dati salvati puliti nel file: '{FILE_CSV_MAPS}'")
  print(f"==============================================")


if __name__ == "__main__":
  main()
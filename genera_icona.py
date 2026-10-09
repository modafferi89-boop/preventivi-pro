from PIL import Image, ImageDraw, ImageFont

# Crea un'immagine quadrata 512x512 con sfondo trasparente
img = Image.new('RGBA', (512, 512), (255, 255, 255, 0))
draw = ImageDraw.Draw(img)

# 1. Disegna il rettangolo arrotondato principale in colore indaco (#6366f1)
# Coordinate centrate e proporzionate per vista frontale
box_x_min, box_y_min = 50, 45
box_x_max, box_y_max = 462, 472
draw.rounded_rectangle([box_x_min, box_y_min, box_x_max, box_y_max], radius=50, fill="#6366f1")

# 2. Disegna l'icona del documento (foglio bianco) in vista frontale
doc_x_min, doc_y_min = 200, 120
doc_x_max, doc_y_max = 312, 270
draw.rectangle([doc_x_min, doc_y_min, doc_x_max, doc_y_max], fill="white")
# Angolo piegato del foglio (geometrico, frontale)
polygon_points = [(266, 120), (312, 166), (312, 120)]
draw.polygon(polygon_points, fill="#e0e7ff")

# Linee di testo stilizzate sul documento
draw.rectangle([220, 155, 270, 165], fill="#6366f1")
draw.rectangle([220, 180, 290, 190], fill="#6366f1")

# 3. Simbolo del dollaro ($) al centro del documento
draw.ellipse([235, 210, 275, 250], fill="#6366f1")
# Dettagli del dollaro in bianco
draw.rectangle([252, 205, 258, 255], fill="white")
draw.rectangle([242, 217, 268, 227], fill="white")
draw.rectangle([242, 233, 268, 243], fill="white")

# 4. Aggiunta della scritta "Preventivi Pro" in basso (bianco)
try:
    # Prova a caricare un font solido e pulito
    font = ImageFont.truetype("arial.ttf", 36)
except IOError:
    # Fallback al font di default se Arial non è trovato
    font = ImageFont.load_default()

text = "Preventivi Pro"
bbox = draw.textbbox((0, 0), text, font=font)
text_width = bbox[2] - bbox[0]
# Centra il testo orizzontalmente
x_text = (512 - text_width) / 2
y_text = 335
draw.text((x_text, y_text), text, fill="white", font=font)

# Salva l'icona nella cartella static
img.save('static/icon-512.png', 'PNG')
print("Icona frontale e professionale ricreata con successo in static/icon-512.png")
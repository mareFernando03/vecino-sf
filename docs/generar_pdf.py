"""Genera el PDF de un informe desde docs/<nombre>.md con Edge headless.

Uso: python docs/generar_pdf.py informe-geo-maps [salida.pdf]
Requiere `pip install markdown` y Microsoft Edge.
Los comentarios <!-- TODO ... --> se muestran como recuadros "PENDIENTE" para que un
borrador no pueda confundirse con la versión final.
"""
import re
import subprocess
import sys
from pathlib import Path

import markdown

DOCS = Path(__file__).resolve().parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
args = sys.argv[1:]
tp = args.pop(0) if args and not args[0].lower().endswith(".pdf") else "informe-geo-maps"
salida = Path(args[0]) if args else DOCS / f"{tp}.pdf"

md = (DOCS / f"{tp}.md").read_text(encoding="utf-8")
pendientes = re.findall(r"<!--\s*TODO(.*?)-->", md, flags=re.S)
md = re.sub(r"<!--\s*TODO[:,]?\s*(.*?)-->",
            lambda m: f'<div class="pendiente"><b>PENDIENTE:</b> {" ".join(m.group(1).split())}</div>',
            md, flags=re.S)
cuerpo = markdown.markdown(md, extensions=["tables", "fenced_code", "md_in_html"])

css = """
@page { size: A4; margin: 18mm 17mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1b1b1b; }
h1 { font-size: 18pt; margin: 0 0 8px; }
h2, h3 { break-after: avoid; }
h2 { font-size: 13.5pt; margin: 20px 0 6px; border-bottom: 1px solid #ccc; padding-bottom: 3px; }
h3 { font-size: 11.5pt; margin: 14px 0 4px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9.5pt; }
th, td { border: 1px solid #bbb; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f4f4f4; padding: 0 2px; }
pre { background: #f4f4f4; padding: 8px; font-size: 8.5pt; }
hr { border: 0; border-top: 1px solid #ccc; }
.capturas { display: flex; flex-wrap: wrap; gap: 10px 3.5%; }
.capturas figure { width: 31%; margin: 0 0 8px; break-inside: avoid; }
.capturas img { width: 100%; border: 1px solid #ccc; }
figure.ancha { margin: 10px 0; break-inside: avoid; text-align: center; }
figure.ancha img { max-width: 100%; max-height: 90mm; border: 1px solid #ccc; }
figure.grande { break-before: page; }
figure.grande img { width: 100%; max-height: 195mm; }
figcaption { font-size: 8.5pt; color: #555; text-align: center; margin-top: 3px; }
blockquote { margin: 8px 0; padding: 6px 10px; border-left: 4px solid #3b6fb6; background: #eef3fa; }
blockquote p { margin: 0; }
.pendiente { background: #fff3b0; border: 1px solid #e0b000; padding: 6px 8px; margin: 8px 0; font-size: 9.5pt; }
"""
html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<base href="{DOCS.as_uri()}/"><style>{css}</style></head><body>{cuerpo}</body></html>"""
tmp = DOCS.parent / "build" / f"{tp.lower()}.html"
tmp.parent.mkdir(exist_ok=True)
tmp.write_text(html, encoding="utf-8")

# Perfil propio: si Edge ya está abierto, sin esto el pedido se lo lleva esa ventana y no imprime.
import tempfile
perfil = tempfile.mkdtemp(prefix="edge-pdf-")
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={perfil}",
                f"--print-to-pdf={salida}", tmp.as_uri()], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
import time
antes = time.time()
for _ in range(60):                       # Edge puede terminar de escribir después de salir
    if salida.exists() and salida.stat().st_mtime >= antes - 120:
        break
    time.sleep(0.5)
print(salida, f"({len(pendientes)} pendientes)")

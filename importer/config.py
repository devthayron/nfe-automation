import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Pasta raiz dos XMLs. Defina XML_ROOT no .env (veja .env.example).
_xml_root = os.getenv("XML_ROOT")
XML_ROOT = Path(_xml_root) if _xml_root else None

# Só estes anos são importados. Ex.: ANOS=2025,2026
ANOS = {int(ano) for ano in os.getenv("ANOS", "2025,2026").split(",") if ano.strip()}

BATCH_SIZE = 300  # arquivos por lote (e por commit)
CANCELED_SUFFIX = "_CANCELADA"

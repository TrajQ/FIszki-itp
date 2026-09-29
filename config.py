import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-niebezpieczny-klucz-zmien-w-produkcji")
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Limit rozmiaru wgrywanego pliku (np. PDF w module fiszki) — granica systemu.
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    GUS_BDL_API_KEY = os.environ.get("GUS_BDL_API_KEY", "")

    # ETAP 64: usługa WMS z archiwalnymi ortofotomapami (Kronika zmian w MPZP).
    # Lata Warsztat odczytuje z GetCapabilities tej usługi — adres można
    # zmienić tutaj, jeśli GUGiK go przeniesie.
    ORTO_ARCHIWALNA_WMS = os.environ.get(
        "ORTO_ARCHIWALNA_WMS", "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolutionTime"
    )

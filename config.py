"""
Configuration settings for the grant documentation crawler.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Database tables
BANDI_TABLE = "bandi"

# Request settings
REQUEST_TIMEOUT = 60  # seconds, increased for thorough processing
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Retry settings
MAX_RETRIES = 5  # increased for reliability
RETRY_BACKOFF = 2  # seconds

# PDF processing
PDF_DOWNLOAD_DIR = "downloads/pdfs"
MAX_PDF_SIZE = 30 * 1024 * 1024  # 30 MB, increased for comprehensive PDFs

# Grant information search terms (in Italian)
SEARCH_TERMS = [
    "bando", "contributo", "finanziamento", "sovvenzione", "agevolazione",
    "scadenza", "deadline", "termine", "presentazione", "domanda",
    "beneficiari", "destinatari", "requisiti", "ammissibilità", "eligibilità",
    "documentazione", "allegati", "modulistica", "documenti", "certificazioni",
    "fondo", "misura", "intervento", "programma", "progetto",
    "spese", "costi", "ammissibili", "finanziabili", "contributo",
    "istruttoria", "valutazione", "punteggio", "criteri", "graduatoria",
    "erogazione", "rendicontazione", "liquidazione", "saldo", "anticipo",
    "visura", "camerale", "bilanci", "ula", "dipendenti",
    "brevetto", "patent", "concessione", "titolo", "invention",
    "servizi", "specialistici", "preventivi", "quotation", "valorizzazione"
]

# Important sections to look for
IMPORTANT_SECTIONS = [
    "oggetto", "finalità", "obiettivi", "beneficiari", "destinatari",
    "requisiti", "documentazione", "allegati", "modalità", "presentazione",
    "scadenza", "termine", "dotazione", "finanziaria", "contributo",
    "agevolazione", "spese", "ammissibili", "istruttoria", "valutazione",
    "erogazione", "rendicontazione", "contatti", "informazioni", "faq"
]

# PDF link patterns
PDF_LINK_PATTERNS = [
    r'.*\.pdf$',
    r'.*document.*\.pdf',
    r'.*allegat.*\.pdf',
    r'.*modulistic.*\.pdf',
    r'.*bando.*\.pdf',
    r'.*avviso.*\.pdf',
    r'.*decreto.*\.pdf',
    r'.*circolare.*\.pdf',
    r'.*istruzion.*\.pdf',
    r'.*guid.*\.pdf',
    r'.*regolament.*\.pdf'
]

# Important PDF types to prioritize
PRIORITY_PDF_PATTERNS = [
    'bando', 'avviso', 'decreto', 'documenti', 'allegat', 'modulistic', 
    'istruzion', 'guid', 'faq', 'regolament'
]
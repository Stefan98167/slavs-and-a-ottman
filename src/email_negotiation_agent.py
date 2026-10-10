import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 1. Konfiguration & Pfad-Setup
# ---------------------------------------------------------------------------
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("\n[ERROR] OPENAI_API_KEY fehlt in der .env-Datei.")
    print("Bitte trage deinen OpenAI-Key in .env ein: OPENAI_API_KEY=sk-...\n")
    sys.exit(1)

client = OpenAI(api_key=api_key)

# Dynamische Pfadermittlung: Findet data/ unabhängig vom Ausführungsort
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir_candidate = os.path.join(BASE_DIR, "data")

if os.path.exists(data_dir_candidate):
    PENDING_FILE = os.path.join(data_dir_candidate, "pending_briefs.json")
    ANSWERED_FILE = os.path.join(data_dir_candidate, "answered_briefs.json")
else:
    # Fallback für flache Ordnerstruktur im Projekt-Root
    PENDING_FILE = os.path.join(BASE_DIR, "pending_briefs.json")
    ANSWERED_FILE = os.path.join(BASE_DIR, "answered_briefs.json")

# ---------------------------------------------------------------------------
# 2. Pydantic-Schema & System-Prompt
# ---------------------------------------------------------------------------
class SupplierEmailOutput(BaseModel):
    subject: str = Field(description="Präzise Betreffzeile inklusive Lieferanten-ID")
    email_body: str = Field(description="Vollständiger B2B-E-Mail-Text mit Konditionen und Call-to-Action")
    internal_summary: str = Field(description="Kompakte interne Zusammenfassung der Trade-offs")

SYSTEM_PROMPT = """Du bist ein autonomer Einkaufs- und Verhandlungsagent im B2B-Bereich.
Erstelle eine professionelle, strukturierte Verhandlungs-E-Mail basierend streng auf dem übergebenen JSON-Brief.

Regeln:
1. STRIKTE FAKTIENTREUE: Keine Zahlen, Preise oder Fristen erfinden, die nicht im Brief stehen.
2. OPTIONEN DARSTELLEN: Alle im JSON definierten Term-Packages vollständig und mit ihren genauen Konditionen auflisten.
3. BELEGE ZITIEREN: Freigegebene Evidenzen und Index-Referenzen (z. B. PPI-Kennungen) wörtlich im Text erwähnen.
4. KOSTENAUFSCHLÜSSELUNG: Explizit eine detaillierte Kostenaufschlüsselung (Cost Breakdown) vom Lieferanten anfordern.
"""

# ---------------------------------------------------------------------------
# 3. I/O Hilfsfunktionen
# ---------------------------------------------------------------------------
def load_json(filepath: str) -> list:
    if not os.path.exists(filepath):
        return []
    try:
        # utf-8-sig fängt eventuelle Windows PowerShell BOMs ab
        with open(filepath, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warnung] Konnte {filepath} nicht einlesen: {e}")
        return []

def save_json(filepath: str, data: list):
    # Stellt sicher, dass das übergeordnete Verzeichnis existiert
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# 4. Pipeline-Ausführung mit Human-in-the-Loop Review
# ---------------------------------------------------------------------------
def process_briefs():
    pending_briefs = load_json(PENDING_FILE)
    if not pending_briefs:
        print(f"Keine offenen Briefs in '{PENDING_FILE}' gefunden.")
        return

    answered_briefs = load_json(ANSWERED_FILE)
    remaining_briefs = []

    print(f"\nStarte Verarbeitung: {len(pending_briefs)} Brief(s) gefunden.")
    print(f"Arbeite mit Eingabe-Datei: {PENDING_FILE}\n")

    for i, brief in enumerate(pending_briefs, start=1):
        supplier_id = brief.get("supplier_id", "Unbekannt")
        print("=" * 70)
        print(f"[{i}/{len(pending_briefs)}] Generiere Angebot für: {supplier_id}...")

        try:
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Verhandlungsbrief:\n{json.dumps(brief, indent=2, ensure_ascii=False)}"}
                ],
                response_format=SupplierEmailOutput,
                temperature=0.2,
            )
            email_output = completion.choices[0].message.parsed

            # --- Review-Ansicht im Terminal ---
            print("\n" + "-" * 25 + " ENTWURF ZUR FREIGABE " + "-" * 25)
            print(f"BETREFF:\n{email_output.subject}\n")
            print(f"TEXT:\n{email_output.email_body}\n")
            print(f"INTERNE BEGRÜNDUNG:\n{email_output.internal_summary}")
            print("-" * 72)

            freigabe = input("\n>> Möchtest du diese E-Mail freigeben und archivieren? (j/n): ").strip().lower()

            if freigabe in ["j", "ja", "y", "yes"]:
                answered_entry = {
                    "supplier_id": supplier_id,
                    "processed_at": datetime.now().isoformat(),
                    "original_brief": brief,
                    "generated_email": {
                        "subject": email_output.subject,
                        "body": email_output.email_body,
                        "internal_summary": email_output.internal_summary
                    }
                }
                answered_briefs.append(answered_entry)
                print(f"-> Bestätigt: E-Mail für {supplier_id} wird archiviert.")
            else:
                print(f"-> Abgelehnt: Brief für {supplier_id} verbleibt in der Warteschlange.")
                remaining_briefs.append(brief)

        except Exception as e:
            print(f"-> Fehler bei {supplier_id}: {e}")
            remaining_briefs.append(brief)

    # Aktualisiere beide Dateien
    save_json(ANSWERED_FILE, answered_briefs)
    save_json(PENDING_FILE, remaining_briefs)

    print("\n" + "=" * 70)
    print("Verarbeitung abgeschlossen:")
    print(f" - Beantwortete / Archivierte Briefs: {len(answered_briefs)} in {ANSWERED_FILE}")
    print(f" - Verbleibende offene Briefs:       {len(remaining_briefs)} in {PENDING_FILE}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    process_briefs()
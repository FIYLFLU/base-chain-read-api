from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import csv
import io

# --- NOUVEL IMPORT POUR X402 ---
from x402.fastapi.middleware import require_payment

app = FastAPI(
    title="OFAC Sanctions Screener API",
    description="Vérifie si un nom ou une entité figure sur la liste des sanctions de l'OFAC.",
    version="1.0.0"
)

# --- NOUVEAU MIDDLEWARE DE PAIEMENT ---
# ⚠️ REMPLACE l'adresse ci-dessous par la tienne (celle de ton wallet sur le réseau Base)
app.middleware("http")(
    require_payment(
        price="0.005",  # Le prix en USDC par requête
        pay_to_address="0x7F63FAeb5f7fe0Ab54809c82f8d88CB0dc320D90", 
        path="/screen" # On protège uniquement la route /screen
    )
)
app = FastAPI(
    title="OFAC Sanctions Screener API",
    description="Vérifie si un nom ou une entité figure sur la liste des sanctions de l'OFAC.",
    version="1.0.0"
)

# --- Modèles de données ---
class ScreenRequest(BaseModel):
    entity_name: str
    threshold: float = 0.8 # Seuil de correspondance (0 à 1)

class ScreenResponse(BaseModel):
    match: bool
    entity_searched: str
    matched_name: str = None
    program: str = None
    risk_score: float

# --- Base de données locale (Mock pour le test) ---
# En production, on téléchargerait la vraie liste depuis treasury.gov
SANCTIONS_LIST = [
    {"name": "Vladimir Putin", "program": "RUSSIA-EO14024"},
    {"name": "Kim Jong Un", "program": "DPRK"},
    {"name": "Osama Bin Laden", "program": "SDGT"},
    {"name": "Saddam Hussein", "program": "IRAQ2"}
]

@app.get("/")
def read_root():
    return {"status": "online", "service": "OFAC Screener", "price_per_request": "0.005 USDC"}

@app.post("/screen", response_model=ScreenResponse)
def screen_entity(request: ScreenRequest):
    """
    Endpoint principal appelé par les agents IA.
    """
    search_name = request.entity_name.lower().strip()
    if not search_name:
        raise HTTPException(status_code=400, detail="Le nom ne peut pas être vide.")

    # Simulation d'un algorithme de matching (dans la réalité, on utiliserait RapidFuzz ou Levenshtein)
    best_match = None
    highest_score = 0.0

    for entry in SANCTIONS_LIST:
        target_name = entry["name"].lower()
        
        # Logique simple : si le nom recherché est contenu dans le nom cible (ou vice-versa)
        if search_name in target_name or target_name in search_name:
            score = 0.95 # Score de confiance élevé
        elif search_name == target_name:
            score = 1.0
        else:
            score = 0.0

        if score > highest_score:
            highest_score = score
            best_match = entry

    # On vérifie si le score dépasse le seuil demandé par l'agent
    if best_match and highest_score >= request.threshold:
        return ScreenResponse(
            match=True,
            entity_searched=request.entity_name,
            matched_name=best_match["name"],
            program=best_match["program"],
            risk_score=highest_score
        )
    
    return ScreenResponse(
        match=False,
        entity_searched=request.entity_name,
        risk_score=highest_score
    )

# --- Pour lancer le serveur ---
if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 9999))
    uvicorn.run(app, host="0.0.0.0", port=port)

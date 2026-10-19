from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from x402.fastapi.middleware import require_payment
from x402.types import TokenAmount, TokenAsset

app = FastAPI(
    title="OFAC Sanctions Screener API",
    description="Vérifie si un nom figure sur la liste des sanctions de l'OFAC.",
    version="1.0.0"
)

# --- CONFIGURATION DU PAIEMENT (USDC sur Base) ---
# Adresse du contrat USDC sur le réseau Base Mainnet
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# On utilise TokenAmount pour spécifier explicitement l'actif
price_info = TokenAmount(
    amount="0.005",  # Prix en USDC
    asset=TokenAsset(address=USDC_BASE_ADDRESS)
)

# Application du middleware sur la route /screen
# discoverable=True active l'extension Bazaar
app.middleware("http")(
    require_payment(
        price=price_info,
        pay_to_address="0x7F63FAeb5f7fe0Ab54809c82f8d88CB0dc320D90", # Ton adresse
        path="/screen",
        description="OFAC Sanctions Screening",
        network="base", # Réseau principal (eip155:8453)
        max_deadline_seconds=300, # Équivalent de maxTimeoutSeconds
        discoverable=True # Active la découverte Bazaar
    )
)

# --- Modèles de données ---
class ScreenRequest(BaseModel):
    entity_name: str
    threshold: float = 0.8

class ScreenResponse(BaseModel):
    match: bool
    entity_searched: str
    matched_name: str = None
    program: str = None
    risk_score: float

SANCTIONS_LIST = [
    {"name": "Vladimir Putin", "program": "RUSSIA-EO14024"},
    {"name": "Kim Jong Un", "program": "DPRK"},
    {"name": "Osama Bin Laden", "program": "SDGT"},
    {"name": "Saddam Hussein", "program": "IRAQ2"}
]

# --- Routes ---

@app.get("/")
def read_root():
    return {"status": "online", "service": "OFAC Screener"}

@app.post("/screen", response_model=ScreenResponse)
def screen_entity(request: ScreenRequest):
    # Cette route est protégée par le middleware ci-dessus
    search_name = request.entity_name.lower().strip()
    if not search_name:
        raise HTTPException(status_code=400, detail="Le nom ne peut pas être vide.")

    best_match = None
    highest_score = 0.0

    for entry in SANCTIONS_LIST:
        target_name = entry["name"].lower()
        if search_name in target_name or target_name in search_name:
            score = 0.95 
        elif search_name == target_name:
            score = 1.0
        else:
            score = 0.0

        if score > highest_score:
            highest_score = score
            best_match = entry

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)

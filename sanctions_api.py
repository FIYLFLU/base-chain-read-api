from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from x402.fastapi.middleware import require_payment

app = FastAPI(
    title="OFAC Sanctions Screener API",
    description="Vérifie si un nom figure sur la liste des sanctions de l'OFAC.",
    version="1.0.0"
)

# Schéma d'entrée (ce que l'agent envoie)
input_schema = {
    "type": "object",
    "properties": {
        "entity_name": {"type": "string", "description": "Nom à vérifier"},
        "threshold": {"type": "number", "description": "Seuil de correspondance (0 à 1)", "default": 0.8}
    },
    "required": ["entity_name"]
}

# Schéma de sortie (ce que l'API renvoie)
output_schema = {
    "type": "object",
    "properties": {
        "match": {"type": "boolean"},
        "entity_searched": {"type": "string"},
        "matched_name": {"type": "string"},
        "program": {"type": "string"},
        "risk_score": {"type": "number"}
    }
}

# --- MIDDLEWARE DE PAIEMENT (syntaxe officielle) ---
app.middleware("http")(
    require_payment(
        price="0.005",                  # Prix en USDC
        pay_to_address="0x7F63FAeb5f7fe0Ab54809c82f8d88CB0dc320D90",
        path="/screen",
        network="base",                 # Réseau principal (pas testnet)
        description="OFAC Sanctions Screening",
        max_deadline_seconds=300,       # 5 minutes pour payer
        input_schema=input_schema,
        output_schema=output_schema,
        discoverable=True               # Active l'indexation Bazaar
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

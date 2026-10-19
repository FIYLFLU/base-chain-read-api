import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig, PaymentOption
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.extensions.bazaar import declare_discovery_extension, OutputConfig

app = FastAPI(title="OFAC Sanctions Screener API", version="1.0.0")

PAY_TO = os.getenv("X402_PAY_TO", "0x7F63FAeb5f7fe0Ab54809c82f8d88CB0dc320D90")
NETWORK = "eip155:8453"  # Base Mainnet
FACILITATOR_URL = "https://x402.org/facilitator"

# --- Schémas Bazaar (Input / Output) ---
input_schema = {
    "type": "object",
    "properties": {
        "entity_name": {"type": "string", "description": "Nom à vérifier"},
        "threshold": {"type": "number", "default": 0.8}
    },
    "required": ["entity_name"]
}

# L'extension Bazaar est déclarée avec la fonction en snake_case
bazaar_ext = declare_discovery_extension(
    input={"entity_name": "Vladimir Putin", "threshold": 0.8},
    input_schema=input_schema,
    output=OutputConfig(
        example={"match": True, "entity_searched": "Vladimir Putin", "risk_score": 0.95},
        schema={
            "type": "object",
            "properties": {
                "match": {"type": "boolean"},
                "entity_searched": {"type": "string"},
                "risk_score": {"type": "number"}
            }
        }
    )
)

# --- Configuration du Facilitator et du Serveur x402 ---
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)
server.register("eip155:*", ExactEvmServerScheme())

# --- Configuration de la Route Payante ---
routes = {
    "POST /screen": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                network=NETWORK,
                pay_to=PAY_TO,
                price="$0.005",
                extra={"name": "USDC", "version": "2"}
            )
        ],
        mime_type="application/json",
        description="OFAC Sanctions Screening",
        extensions=bazaar_ext  # On attache l'extension Bazaar ici
    )
}

# --- Ajout du Middleware ---
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)

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
            match=True, entity_searched=request.entity_name,
            matched_name=best_match["name"], program=best_match["program"],
            risk_score=highest_score
        )
    return ScreenResponse(match=False, entity_searched=request.entity_name, risk_score=highest_score)

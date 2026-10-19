from fastapi import HTTPException
from pydantic import BaseModel
from x402_fastapi_kit import PaymentApp, require_payment

app = PaymentApp()

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

@app.get("/")
def read_root():
    return {"status": "online", "service": "OFAC Screener"}

@app.post("/screen", response_model=ScreenResponse)
@require_payment(price="$0.005", description="OFAC Sanctions Screening") # <-- Le prix est ici
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

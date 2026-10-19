import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3
from dotenv import load_dotenv

from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, AuthHeaders
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig, PaymentOption
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.extensions.bazaar import declare_discovery_extension, OutputConfig

load_dotenv()

app = FastAPI(title="Base Chain Read API")

PAY_TO = os.getenv("PAY_TO_ADDRESS")
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))

# --- Classe d'authentification personnalisée pour CDP ---
CDP_API_KEY_SECRET = os.getenv("CDP_API_KEY_SECRET")

class CdpAuthProvider:
    async def get_auth_headers(self) -> AuthHeaders:
        return AuthHeaders(
            verify={"Authorization": f"Bearer {CDP_API_KEY_SECRET}"},
            settle={"Authorization": f"Bearer {CDP_API_KEY_SECRET}"},
            supported={}
        )

# --- Configuration du facilitateur CDP ---
facilitator = HTTPFacilitatorClient(
    FacilitatorConfig(
        url="https://api.cdp.coinbase.com/platform/v2/x402",
        auth_provider=CdpAuthProvider()
    )
)
server = x402ResourceServer(facilitator)
server.register("eip155:*", ExactEvmServerScheme())

# --- Schémas pour l'extension Bazaar ---
input_schema = {
    "type": "object",
    "properties": {
        "address": {"type": "string", "description": "Adresse du portefeuille à vérifier"}
    },
    "required": ["address"]
}

bazaar_ext = declare_discovery_extension(
    input={"address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"},
    input_schema=input_schema,
    output=OutputConfig(
        example={"address": "0x...", "token": "USDC", "balance": 100.0},
        schema={
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "token": {"type": "string"},
                "balance": {"type": "number"}
            }
        }
    )
)

# --- Configuration de la route payante ---
routes = {
    "POST /read-balance": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                network="eip155:8453",
                pay_to=PAY_TO,
                price="$0.003",
                extra={"name": "USDC", "version": "2"}
            )
        ],
        mime_type="application/json",
        description="Lit le solde USDC d'une adresse sur Base",
        extensions=bazaar_ext
    )
}

app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)

# --- Modèles ---
class BalanceRequest(BaseModel):
    address: str

# --- Routes ---
@app.get("/")
def read_root():
    return {"status": "online", "service": "Base Chain Read API"}

@app.post("/read-balance")
async def read_balance(request: BalanceRequest):
    try:
        if not w3.is_address(request.address):
            raise HTTPException(status_code=400, detail="Adresse invalide")
        usdc_address = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
        contract = w3.eth.contract(address=usdc_address, abi=abi)
        balance_wei = contract.functions.balanceOf(request.address).call()
        return {"address": request.address, "token": "USDC", "balance": balance_wei / 10**6}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/read-balance")
async def read_balance_get():
    return {"message": "Endpoint payant. Utilisez POST avec un corps JSON."}

@app.head("/read-balance")
async def read_balance_head():
    return {"message": "Endpoint payant. Utilisez POST."}

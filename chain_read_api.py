from fastapi import FastAPI, HTTPException
from fastapi_x402 import init_x402, pay
import os
from web3 import Web3
from pydantic import BaseModel

app = FastAPI(title="Base Chain Read API")

# --- Configuration ---
# Récupération de l'adresse de réception et de l'URL du RPC depuis les variables d'environnement
PAY_TO = os.getenv("PAY_TO_ADDRESS")
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org") # RPC public pour Base
w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))

# Initialisation de x402 (le middleware est ajouté automatiquement)
# On utilise "base-sepolia" pour les tests, on passera à "base" en production
init_x402(app, pay_to=PAY_TO, network="base")

# --- Modèle de données ---
class BalanceRequest(BaseModel):
    address: str

# --- Route protégée par le paiement ---
@app.post("/read-balance")
@pay("$0.003") # Prix de l'appel
async def read_balance(request: BalanceRequest):
    """
    Lit le solde USDC d'une adresse sur la blockchain Base.
    """
    try:
        # Vérification basique de l'adresse
        if not w3.is_address(request.address):
            raise HTTPException(status_code=400, detail="Adresse invalide")
        
        # Adresse du contrat USDC sur Base Mainnet
        usdc_address = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        # ABI minimal pour la fonction balanceOf
        abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
        
        contract = w3.eth.contract(address=usdc_address, abi=abi)
        balance_wei = contract.functions.balanceOf(request.address).call()
        balance_usdc = balance_wei / 10**6 # USDC a 6 décimales
        
        return {
            "address": request.address,
            "token": "USDC",
            "balance": balance_usdc
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Route gratuite pour tester que le serveur fonctionne ---
@app.get("/")
def read_root():
    return {"status": "online", "service": "Base Chain Read API"}

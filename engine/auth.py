from fastapi import Header, HTTPException
from config import settings


async def verify_engine_key(x_engine_key: str = Header(..., alias="X-ENGINE-KEY")):
    if x_engine_key != settings.ENGINE_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing ENGINE_KEY")
    return x_engine_key

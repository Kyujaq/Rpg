from fastapi import FastAPI
from db import engine
from models import Base
from routers import campaigns, events, dice, memory, turns

app = FastAPI(
    title="TTRPG Game Engine",
    version="0.1.0",
    docs_url="/docs",
)

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app.include_router(campaigns.router)
app.include_router(events.router)
app.include_router(dice.router)
app.include_router(memory.router)
app.include_router(turns.router)

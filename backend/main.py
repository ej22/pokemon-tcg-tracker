import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine
from models import Base
from routers import collection, prices, sets, portfolio, search, images, manual_cards
from scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting PokéTCG Tracker backend")
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()
    await engine.dispose()
    logger.info("Backend shutdown complete")


app = FastAPI(
    title="PokéTCG Tracker",
    description="Self-hosted Pokémon TCG collection tracker with CardMarket price caching",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(collection.router)
app.include_router(prices.router)
app.include_router(sets.router)
app.include_router(portfolio.router)
app.include_router(search.router)
app.include_router(images.router)
app.include_router(manual_cards.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}

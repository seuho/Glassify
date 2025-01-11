from fastapi import FastAPI
from uvicorn import Config, Server
from auth.routes import auth_router
from items.routes import items_router
import nest_asyncio
from database.connection import connect_to_mongo

nest_asyncio.apply()
app = FastAPI()

# Include Routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(items_router, prefix="/items", tags=["Items"])

# Startup and Shutdown Events
@app.on_event("startup")
async def startup():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown():
    pass

if __name__ == "__main__":
    port = 8000
    config = Config(app=app, host="127.0.0.1", port=port)
    server = Server(config=config)
    server.run()
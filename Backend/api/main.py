from fastapi import FastAPI, Request
from uvicorn import Config, Server
from api.auth.routes import auth_router
from api.items.routes import items_router
import nest_asyncio
from api.database.connection import connect_to_mongo, close_mongo_connection, client

nest_asyncio.apply()
app = FastAPI()

@app.get("/")
async def health_check():
    return {"status": "Healthy", "message": "The server is running and ready to accept requests."}

# Include Routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(items_router, prefix="/items", tags=["Items"])

# Middleware to ensure MongoDB connection
@app.middleware("http")
async def ensure_mongo_connection(request: Request, call_next):
    global client 
    if not client:
        await connect_to_mongo()
    response = await call_next(request)
    return response

# Shutdown Event
@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()

if __name__ == "__main__":
    port = 8000
    config = Config(app=app, host="127.0.0.1", port=port)
    server = Server(config=config)
    server.run()
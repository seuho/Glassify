from dotenv import load_dotenv
import os

load_dotenv("/Users/yashasvipamu/Documents/Web Applications/Glassify/Backend/config.env")

class Config:
    MONGO_URL = os.getenv("Mongo_url")
    SECRET_KEY = os.getenv("SECRET_KEY")

config = Config()

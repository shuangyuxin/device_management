import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-please-change-in-production')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///devices.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
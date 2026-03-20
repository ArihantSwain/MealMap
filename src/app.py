import os
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from routes import register_routes

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

register_routes(app)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)

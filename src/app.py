from flask import Flask, render_template
from routes import register_routes

app = Flask(__name__, template_folder="templates", static_folder="static")
register_routes(app)

@app.route("/")
def home():
    return render_template("base.html")

if __name__ == "__main__":
    app.run(debug=True)

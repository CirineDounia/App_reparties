from flask import Flask, jsonify
from flask_cors import CORS
from db import db

app = Flask(__name__)
CORS(app)

# --------------------------------------------------
# ROUTE POUR LE LOGIN (cas spécial, on garde)
# --------------------------------------------------
@app.route("/personnel/login/<login>", methods=["GET"])
def get_personnel_by_login(login):
    user = db.personnel.find_one(
        {"login": login},
        {
            "_id": 0,
            "password": 1,
            "ssn": 1,
            "nom_prenom": 1,
            "etat": 1,
            "service": 1,
            "role": 1
        }
    )

    if user is None:
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    return jsonify(user)


# --------------------------------------------------
# ROUTES D'ACCÈS BRUT AUX COLLECTIONS
# --------------------------------------------------

@app.route("/data/personnel", methods=["GET"])
def get_all_personnel():
    data = list(db.personnel.find({}, {"_id": 0}))
    return jsonify(data)


@app.route("/data/surveillance", methods=["GET"])
def get_all_surveillance():
    data = list(db.surveillance.find({}, {"_id": 0}))
    return jsonify(data)


@app.route("/data/articles", methods=["GET"])
def get_all_articles():
    data = list(db.articles.find({}, {"_id": 0}))
    return jsonify(data)


@app.route("/data/releves_sanitaires", methods=["GET"])
def get_all_releves_sanitaires():
    data = list(db.releves_sanitaires.find({}, {"_id": 0}))
    return jsonify(data)


@app.route("/data/operations_commerciales", methods=["GET"])
def get_all_operations_commerciales():
    data = list(db.operations_commerciales.find({}, {"_id": 0}))
    return jsonify(data)


if __name__ == "__main__":
    app.run(port=5001, debug=True)
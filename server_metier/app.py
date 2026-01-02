from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)

SERVER_DONNEES_URL = "http://localhost:5001"

BINOME_2_URL = "https://projet-app-rep.onrender.com"


@app.route("/", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        login = request.form["login"]
        password = request.form["password"]

        r = requests.get(f"{SERVER_DONNEES_URL}/personnel/login/{login}")

        if r.status_code != 200:
            error = "Utilisateur introuvable"
        else:
            user = r.json()

            if user["password"] != password:
                error = "Mot de passe incorrect"
            elif user["etat"] == "arret_maladie":
                error = "Accès refusé (arrêt maladie)"
            else:
                return redirect(
                    url_for(
                        "dashboard",
                        nom=user["nom_prenom"],
                        service=user["service"],
                        role=user.get("role", "employe")
                    )
                )

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    nom = request.args.get("nom")
    service = request.args.get("service")
    role = request.args.get("role")

    if not nom or not service:
        return redirect("/")

    # ================================================
    # RÉCUPÉRATION DES DONNÉES BRUTES
    # ================================================
    personnel = requests.get(f"{SERVER_DONNEES_URL}/data/personnel").json()
    surveillance = requests.get(f"{SERVER_DONNEES_URL}/data/surveillance").json()
    articles = requests.get(f"{SERVER_DONNEES_URL}/data/articles").json()
    releves_sanitaires = requests.get(f"{SERVER_DONNEES_URL}/data/releves_sanitaires").json()
    operations_commerciales = requests.get(f"{SERVER_DONNEES_URL}/data/operations_commerciales").json()

    # ================================================
    # CALCUL DES KPIs (LOGIQUE MÉTIER)
    # ================================================

    # KPI Achats : Nombre d'employés dans le service achats
    nb_employes_achats = len([p for p in personnel if p.get("service") == "achats"])

    # KPI Vente : Nombre de responsables en vente/commercial
    nb_resp_vente = len([
        p for p in personnel 
        if p.get("service") == "commercial" and p.get("role") == "responsable"
    ])

    # KPI Assistance : Zone avec le CO2 minimum
    zone_co_min = None
    co2_min_value = None
    if releves_sanitaires:
        zone_co_min_data = min(releves_sanitaires, key=lambda x: x.get("co2", float('inf')))
        zone_co_min = zone_co_min_data.get("zone")
        co2_min_value = zone_co_min_data.get("co2")

    # KPI Maintenance : Nombre de zones avec incendie actif
    incendies_actifs = len([
        z for z in surveillance 
        if z.get("detection_incendie") == "oui"
    ])

    # KPI R&D : Articles avec emballage déformé sans collision
    articles_deformes_sans_collision = len([
        a for a in articles 
        if a.get("etat_emballage") == "Déformé" and a.get("collisions") == 0
    ])

    # KPI Qualité : Articles avec emballage correct
    articles_emballage_correct = len([
        a for a in articles 
        if a.get("etat_emballage") == "Correct"
    ])

    # KPI Opérations commerciales : Nombre d'opérations en cours
    operations_en_cours = len([
        o for o in operations_commerciales 
        if o.get("etat") == "en cours"
    ])

    # ================================================
    # DRONE LE PLUS ANCIEN (API EXTERNE)
    # ================================================
    try:
        drone_plus_ancien = requests.get(
            "https://projet-app-rep.onrender.com/finance_gestion/drone/plus_ancien"
        ).json()
    except:
        drone_plus_ancien = None

    # ================================================
    # GRAPHIQUES (AGRÉGATIONS)
    # ================================================

    # GRAPHIQUE 1 : Répartition du personnel par service
    services_count = {}
    for p in personnel:
        service_name = p.get("service", "Inconnu")
        services_count[service_name] = services_count.get(service_name, 0) + 1
    
    personnel_services = [
        {"service": service_name, "total": count}
        for service_name, count in services_count.items()
    ]

    # GRAPHIQUE 2 : Répartition des articles par état d'emballage
    emballage_count = {}
    for a in articles:
        emballage = a.get("etat_emballage", "Inconnu")
        emballage_count[emballage] = emballage_count.get(emballage, 0) + 1
    
    articles_emballage = [
        {"emballage": emballage, "total": count}
        for emballage, count in emballage_count.items()
    ]

    # GRAPHIQUE 3 : CO2 moyen par zone
    zones_co2 = {}
    zones_count = {}
    
    for releve in releves_sanitaires:
        zone = releve.get("zone")
        co2 = releve.get("co2", 0)
        
        if zone not in zones_co2:
            zones_co2[zone] = 0
            zones_count[zone] = 0
        
        zones_co2[zone] += co2
        zones_count[zone] += 1
    
    co_zones = [
        {
            "zone": f"Zone {zone}",
            "co2": zones_co2[zone] / zones_count[zone]
        }
        for zone in sorted(zones_co2.keys())
    ]

    # GRAPHIQUE 4 : Incidents par type
    incident_incendie = len([
        z for z in surveillance 
        if z.get("detection_incendie") == "oui"
    ])
    
    incident_panne_drone = len([
        z for z in surveillance 
        if z.get("drones_panne", 0) > 0
    ])
    
    incident_audit = len([
        z for z in surveillance 
        if z.get("audit_conformite") == "non"
    ])
    
    incidents_types = {
        "labels": ["Incendie", "Panne drone", "Audit non conforme"],
        "values": [incident_incendie, incident_panne_drone, incident_audit]
    }

    try:
            # Appeler l'API du Binôme 2
            response = requests.get(f"{BINOME_2_URL}/general/formations", timeout=5)
            
            if response.status_code == 200:
                formations = response.json()
                print(formations)
                
                # Trouver celle avec le meilleur pourcentage_engagement
                if formations and len(formations) > 0:
                    formation_meilleure = max(
                        formations,
                        key=lambda f: f.get("pourcentage_engagement", 0)
                    )
                    
                    print(f"✅ Formation récupérée: {formation_meilleure.get('nom_formation')}")
        
    except Exception as e:
            print(f"⚠️ Erreur Binôme 2: {e}")
            
            # Si échec, données par défaut
            if not formation_meilleure:
                formation_meilleure = {
                    "nom_formation": "Service indisponible",
                    "pourcentage_engagement": 0,
                    "pourcentage_satisfaction": 0
                }
        

    # ================================================
    # PRÉPARATION DES DONNÉES POUR LE TEMPLATE
    # ================================================
    overview = {
        # KPIs
        "achats": {"nb_employes_achats": nb_employes_achats},
        "resp_vente": {"total": nb_resp_vente},
        "assistance": {"zone": zone_co_min, "co2": co2_min_value},
        "maintenance": {"incendies_actifs": incendies_actifs},
        "rd": {"articles_deformes_sans_collision": articles_deformes_sans_collision},
        "qualite": {"articles_emballage_correct": articles_emballage_correct},
        "operations": {"operations_en_cours": operations_en_cours},
        "formation_meilleure": formation_meilleure,
        # Drone externe
        "drone_plus_ancien": drone_plus_ancien,
        
        # Graphiques
        "personnel_services": personnel_services,
        "articles_emballage": articles_emballage,
        "co_zones": co_zones,
        "incidents_types": incidents_types
    }

    user = {
        "nom": nom,
        "service": service,
        "role": role
    }

    return render_template("dashboard.html", user=user, overview=overview)

# =====================================================
# PAGE ANALYSE PERSONNEL
# =====================================================
@app.route("/personnel/analyse")
def analyse_personnel():
    """Page d'analyse détaillée du personnel"""
    
    user = {
        "nom": request.args.get("nom"),
        "service": request.args.get("service"),
        "role": request.args.get("role")
    }
    
    if not user["nom"] or not user["service"]:
        return redirect("/")
    
    try:
        # Récupérer les données brutes du serveur de données
        personnel = requests.get(f"{SERVER_DONNEES_URL}/data/personnel").json()
                
        # KPI 1 : Nombre total d'employés
        total_employes = len(personnel)
        
        # KPI 2 : Employés actifs vs autres états
        employes_actifs = len([p for p in personnel if p.get("etat") == "actif"])
        
        # KPI 3 : Fréquence cardiaque moyenne
        freq_cardiaque_values = [p.get("freq_cardiaque", 0) for p in personnel if p.get("freq_cardiaque")]
        freq_cardiaque_moyenne = sum(freq_cardiaque_values) / len(freq_cardiaque_values) if freq_cardiaque_values else 0
        
        # KPI 4 : Nombre de responsables
        nb_responsables = len([p for p in personnel if p.get("role") == "responsable"])
        
        # Graphique 1 : Répartition par service
        services_count = {}
        for p in personnel:
            service = p.get("service", "Inconnu")
            services_count[service] = services_count.get(service, 0) + 1
        
        graphique_services = [
            {"service": service, "total": count}
            for service, count in services_count.items()
        ]
        
        # Graphique 2 : Répartition par pays
        pays_count = {}
        for p in personnel:
            pays = p.get("pays", "Inconnu")
            pays_count[pays] = pays_count.get(pays, 0) + 1
        
        graphique_pays = [
            {"pays": pays, "total": count}
            for pays, count in pays_count.items()
        ]
        
        # Graphique 3 : Répartition par état
        employes_maladie = len([p for p in personnel if p.get("etat") == "arret_maladie"])
        employes_conge = len([p for p in personnel if p.get("etat") == "conge"])
        
        graphique_etats = [
            {"etat": "Actif", "total": employes_actifs},
            {"etat": "Arrêt maladie", "total": employes_maladie},
            {"etat": "Congé", "total": employes_conge}
        ]
        
        # Graphique 4 : Responsables vs Employés par service
        responsables_par_service = {}
        employes_par_service = {}
        
        for p in personnel:
            service = p.get("service", "Inconnu")
            role = p.get("role", "employe")
            
            if role == "responsable":
                responsables_par_service[service] = responsables_par_service.get(service, 0) + 1
            else:
                employes_par_service[service] = employes_par_service.get(service, 0) + 1
        
        services_list = sorted(set(list(responsables_par_service.keys()) + list(employes_par_service.keys())))
        graphique_roles = {
            "services": services_list,
            "responsables": [responsables_par_service.get(s, 0) for s in services_list],
            "employes": [employes_par_service.get(s, 0) for s in services_list]
        }
        
        # Graphique 5 : Fréquence cardiaque par service
        freq_par_service = {}
        count_par_service = {}
        
        for p in personnel:
            service = p.get("service", "Inconnu")
            freq = p.get("freq_cardiaque", 0)
            if freq > 0:
                freq_par_service[service] = freq_par_service.get(service, 0) + freq
                count_par_service[service] = count_par_service.get(service, 0) + 1
        
        graphique_freq_cardiaque = [
            {
                "service": service,
                "moyenne": round(freq_par_service[service] / count_par_service[service], 1)
            }
            for service in freq_par_service.keys()
        ]
        
        # Alerte : Employés en arrêt maladie
        liste_maladie = [
            {
                "nom": p.get("nom_prenom"),
                "service": p.get("service"),
                "ssn": p.get("ssn")
            }
            for p in personnel if p.get("etat") == "arret_maladie"
        ]
        
        overview = {
            # KPIs
            "total_employes": total_employes,
            "employes_actifs": employes_actifs,
            "freq_cardiaque_moyenne": round(freq_cardiaque_moyenne, 1),
            "nb_responsables": nb_responsables,
            
            # Graphiques
            "graphique_services": graphique_services,
            "graphique_pays": graphique_pays,
            "graphique_etats": graphique_etats,
            "graphique_roles": graphique_roles,
            "graphique_freq_cardiaque": graphique_freq_cardiaque,
            
            # Alertes
            "liste_maladie": liste_maladie
        }
        
    except Exception as e:
        print(f"Erreur: {e}")
        overview = {}
    
    return render_template("personnel.html", overview=overview, user=user)

# =====================================================
# PAGE ANALYSE ARTICLES
# =====================================================
@app.route("/articles/analyse")
def analyse_articles():
    """
    Page d'analyse des articles
    INCLUT LE KPI A DEMANDÉ : Article ayant subi le moins de collisions
    """
    
    user = {
        "nom": request.args.get("nom"),
        "service": request.args.get("service"),
        "role": request.args.get("role")
    }
    
    if not user["nom"] or not user["service"]:
        return redirect("/")
    
    try:

        articles = requests.get(f"{SERVER_DONNEES_URL}/data/articles").json()
        personnel = requests.get(f"{SERVER_DONNEES_URL}/data/personnel").json()
        

        if articles:
            article_moins_collisions = min(articles, key=lambda x: x.get("collisions", 999))
        else:
            article_moins_collisions = None
        
        # KPI 1 : Nombre total d'articles
        total_articles = len(articles)
        
        # KPI 2 : Articles avec emballage correct
        articles_conformes = len([a for a in articles if a.get("etat_emballage") == "Correct"])
        
        # KPI 3 : Articles avec emballage déformé
        articles_deformes = len([a for a in articles if a.get("etat_emballage") == "Déformé"])
        
        # KPI 4 : Total des collisions
        total_collisions = sum(a.get("collisions", 0) for a in articles)
        
        # KPI 5 : Taux de conformité
        taux_conformite = (articles_conformes / total_articles * 100) if total_articles > 0 else 0
        
        # KPI 6 : Nombre d'articles sans collision
        articles_sans_collision = len([a for a in articles if a.get("collisions", 0) == 0])
        
        # Graphique 1 : État des emballages
        graphique_emballages = [
            {"etat": "Correct", "total": articles_conformes},
            {"etat": "Déformé", "total": articles_deformes}
        ]
        
        # Graphique 2 : Articles par zone
        articles_par_zone = {}
        for a in articles:
            zone = f"Zone {a.get('zone', 0)}"
            articles_par_zone[zone] = articles_par_zone.get(zone, 0) + 1
        
        graphique_zones = [
            {"zone": k, "total": v}
            for k, v in sorted(articles_par_zone.items())
        ]
        
        # Graphique 3 : Collisions par zone
        collisions_par_zone = {}
        for a in articles:
            zone = f"Zone {a.get('zone', 0)}"
            collisions_par_zone[zone] = collisions_par_zone.get(zone, 0) + a.get("collisions", 0)
        
        graphique_collisions_zones = [
            {"zone": k, "collisions": v}
            for k, v in sorted(collisions_par_zone.items())
        ]
        
        # Graphique 4 : État emballage par zone (Stacked Bar)
        zones_list = sorted(set(a.get('zone', 0) for a in articles))
        emballage_par_zone = {
            "zones": [f"Zone {z}" for z in zones_list],
            "correct": [],
            "deforme": []
        }
        
        for zone in zones_list:
            correct = len([a for a in articles if a.get('zone') == zone and a.get('etat_emballage') == 'Correct'])
            deforme = len([a for a in articles if a.get('zone') == zone and a.get('etat_emballage') == 'Déformé'])
            emballage_par_zone["correct"].append(correct)
            emballage_par_zone["deforme"].append(deforme)
        
        # Graphique 5 : Distribution des collisions
        collision_distribution = {}
        for a in articles:
            nb_collisions = a.get("collisions", 0)
            collision_distribution[nb_collisions] = collision_distribution.get(nb_collisions, 0) + 1
        
        graphique_distribution_collisions = [
            {"collisions": k, "nombre_articles": v}
            for k, v in sorted(collision_distribution.items())
        ]
        
        # Graphique 6 : Top responsables par nombre d'articles
        articles_par_responsable = {}
        for a in articles:
            resp = a.get("responsable", "Inconnu")
            articles_par_responsable[resp] = articles_par_responsable.get(resp, 0) + 1
        
        top_responsables = sorted(
            [{"responsable": k, "total": v} for k, v in articles_par_responsable.items()],
            key=lambda x: x["total"],
            reverse=True
        )[:10]
        
        # Enrichir avec les noms des responsables
        for resp_data in top_responsables:
            ssn = resp_data["responsable"]
            employe = next((p for p in personnel if p.get("ssn") == ssn), None)
            if employe:
                resp_data["nom"] = employe.get("nom_prenom", ssn)
            else:
                resp_data["nom"] = ssn
        
        # Articles avec le plus de collisions (à surveiller)
        articles_critiques = sorted(
            [a for a in articles if a.get("collisions", 0) > 0],
            key=lambda x: x.get("collisions", 0),
            reverse=True
        )[:5]
        
        # Enrichir avec le nom du responsable
        for article in articles_critiques:
            ssn = article.get("responsable", "Inconnu")
            employe = next((p for p in personnel if p.get("ssn") == ssn), None)
            if employe:
                article["responsable_nom"] = employe.get("nom_prenom", ssn)
            else:
                article["responsable_nom"] = ssn
        
        # Articles déformés sans collision (problème de qualité)
        articles_qualite_probleme = [
            a for a in articles 
            if a.get("etat_emballage") == "Déformé" and a.get("collisions", 0) == 0
        ]
        
        # Collision moyenne par article
        collision_moyenne = total_collisions / total_articles if total_articles > 0 else 0
        
        # Zone avec le plus de problèmes
        problemes_par_zone = {}
        for a in articles:
            zone = a.get("zone", 0)
            if a.get("etat_emballage") == "Déformé" or a.get("collisions", 0) > 0:
                problemes_par_zone[zone] = problemes_par_zone.get(zone, 0) + 1
        
        if problemes_par_zone:
            zone_plus_problemes = max(problemes_par_zone.items(), key=lambda x: x[1])
        else:
            zone_plus_problemes = None
        
        # Préparer les données pour le template
        overview = {
            # KPI PRINCIPAL DEMANDÉ
            "article_moins_collisions": article_moins_collisions,
            
            # Autres KPIs
            "total_articles": total_articles,
            "articles_conformes": articles_conformes,
            "articles_deformes": articles_deformes,
            "total_collisions": total_collisions,
            "taux_conformite": round(taux_conformite, 1),
            "articles_sans_collision": articles_sans_collision,
            "collision_moyenne": round(collision_moyenne, 2),
            
            # Graphiques
            "graphique_emballages": graphique_emballages,
            "graphique_zones": graphique_zones,
            "graphique_collisions_zones": graphique_collisions_zones,
            "emballage_par_zone": emballage_par_zone,
            "graphique_distribution_collisions": graphique_distribution_collisions,
            "top_responsables": top_responsables,
            
            # Alertes
            "articles_critiques": articles_critiques,
            "articles_qualite_probleme": articles_qualite_probleme,
            "zone_plus_problemes": zone_plus_problemes
        }
        
    except Exception as e:
        print(f"Erreur: {e}")
        overview = {}
    
    return render_template("articles.html", overview=overview, user=user)
# =====================================================
# PAGE ANALYSE Operations
# =====================================================
@app.route("/operations/analyse")
def analyse_operations():
    """
    Page d'analyse détaillée des opérations commerciales
    CORRIGÉ pour correspondre aux vrais champs MongoDB
    """
    
    user = {
        "nom": request.args.get("nom"),
        "service": request.args.get("service"),
        "role": request.args.get("role")
    }
    
    if not user["nom"] or not user["service"]:
        return redirect("/")
    
    try:
        # ========================================
        # RÉCUPÉRATION DES DONNÉES BRUTES
        # ========================================
        operations = requests.get(f"{SERVER_DONNEES_URL}/data/operations_commerciales").json()
        personnel = requests.get(f"{SERVER_DONNEES_URL}/data/personnel").json()
        
        # ========================================
        # KPIs PRINCIPAUX (CALCULS MÉTIER)
        # ========================================
        
        # KPI 1 : Nombre total d'opérations
        total_operations = len(operations)
        
        # KPI 2 : Marge totale dégagée (utiliser 'marge' au lieu de 'marge_degagee')
        marge_totale = sum(op.get("marge", 0) for op in operations)
        
        # KPI 3 : Distance totale parcourue (utiliser 'km' au lieu de 'km_parcourus')
        distance_totale = sum(op.get("km", 0) for op in operations)
        
        # KPI 4 : Meilleure opération (marge la plus élevée)
        if operations:
            meilleure_operation = max(operations, key=lambda x: x.get("marge", 0))
            # Enrichir avec le nom du responsable
            resp_ssn = meilleure_operation.get("responsable", "")
            employe = next((p for p in personnel if p.get("ssn") == resp_ssn), None)
            if employe:
                meilleure_operation["responsable_nom"] = employe.get("nom_prenom", resp_ssn)
            else:
                meilleure_operation["responsable_nom"] = resp_ssn
        else:
            meilleure_operation = None
        
        # KPI 5 : Marge moyenne par opération
        marge_moyenne = marge_totale / total_operations if total_operations > 0 else 0
        
        # KPI 6 : Distance moyenne par opération
        distance_moyenne = distance_totale / total_operations if total_operations > 0 else 0
        
        # ========================================
        # GRAPHIQUES (AGRÉGATIONS)
        # ========================================
        
        # Graphique 1 : Achats vs Ventes (Nombre)
        achats = len([op for op in operations if op.get("type") == "achat"])
        ventes = len([op for op in operations if op.get("type") == "vente"])
        
        graphique_types = [
            {"type": "Achats", "total": achats},
            {"type": "Ventes", "total": ventes}
        ]
        
        # Graphique 2 : Marge par type d'opération
        marge_achats = sum(op.get("marge", 0) for op in operations if op.get("type") == "achat")
        marge_ventes = sum(op.get("marge", 0) for op in operations if op.get("type") == "vente")
        
        graphique_marges = [
            {"type": "Achats", "marge": marge_achats},
            {"type": "Ventes", "marge": marge_ventes}
        ]
        
        # Graphique 3 : Top 10 responsables par marge
        marges_par_responsable = {}
        for op in operations:
            resp = op.get("responsable", "Inconnu")
            marge = op.get("marge", 0)
            marges_par_responsable[resp] = marges_par_responsable.get(resp, 0) + marge
        
        top_responsables = sorted(
            [{"responsable": k, "marge": v} for k, v in marges_par_responsable.items()],
            key=lambda x: x["marge"],
            reverse=True
        )[:10]
        
        # Enrichir avec les noms
        for resp_data in top_responsables:
            ssn = resp_data["responsable"]
            employe = next((p for p in personnel if p.get("ssn") == ssn), None)
            if employe:
                resp_data["nom"] = employe.get("nom_prenom", ssn)
            else:
                resp_data["nom"] = ssn
        
        # Graphique 4 : Distance parcourue par responsable (Top 10)
        distance_par_responsable = {}
        for op in operations:
            resp = op.get("responsable", "Inconnu")
            km = op.get("km", 0)
            distance_par_responsable[resp] = distance_par_responsable.get(resp, 0) + km
        
        top_distances = sorted(
            [{"responsable": k, "km": v} for k, v in distance_par_responsable.items()],
            key=lambda x: x["km"],
            reverse=True
        )[:10]
        
        # Enrichir avec les noms
        for dist_data in top_distances:
            ssn = dist_data["responsable"]
            employe = next((p for p in personnel if p.get("ssn") == ssn), None)
            if employe:
                dist_data["nom"] = employe.get("nom_prenom", ssn)
            else:
                dist_data["nom"] = ssn
        
        # Graphique 5 : Évolution des marges (30 dernières opérations)
        operations_recentes = sorted(operations, key=lambda x: x.get("id", 0), reverse=True)[:30]
        operations_recentes.reverse()  # Ordre chronologique
        
        graphique_evolution = [
            {
                "operation": f"Op {op.get('id', i)}",
                "marge": op.get("marge", 0)
            }
            for i, op in enumerate(operations_recentes, 1)
        ]
        
        # Graphique 6 : Opérations par responsable (nombre)
        ops_par_responsable = {}
        for op in operations:
            resp = op.get("responsable", "Inconnu")
            ops_par_responsable[resp] = ops_par_responsable.get(resp, 0) + 1
        
        top_ops_responsables = sorted(
            [{"responsable": k, "total": v} for k, v in ops_par_responsable.items()],
            key=lambda x: x["total"],
            reverse=True
        )[:10]
        
        # Enrichir avec les noms
        for ops_data in top_ops_responsables:
            ssn = ops_data["responsable"]
            employe = next((p for p in personnel if p.get("ssn") == ssn), None)
            if employe:
                ops_data["nom"] = employe.get("nom_prenom", ssn)
            else:
                ops_data["nom"] = ssn
        
        # ========================================
        # ANALYSES AVANCÉES
        # ========================================
        
        # Ratio Achats/Ventes (en nombre)
        ratio_achats_ventes = (achats / ventes * 100) if ventes > 0 else 0
        
        # Ratio marges Achats/Ventes
        ratio_marges = (marge_achats / marge_ventes * 100) if marge_ventes > 0 else 0
        
        # Responsable le plus actif
        if top_ops_responsables:
            responsable_plus_actif = top_ops_responsables[0]
        else:
            responsable_plus_actif = None
        
        # Opérations avec marges négatives (alertes)
        operations_marges_negatives = [
            op for op in operations if op.get("marge", 0) < 0
        ]
        
        # Enrichir avec les noms
        for op in operations_marges_negatives:
            ssn = op.get("responsable", "Inconnu")
            employe = next((p for p in personnel if p.get("ssn") == ssn), None)
            if employe:
                op["responsable_nom"] = employe.get("nom_prenom", ssn)
            else:
                op["responsable_nom"] = ssn
        
        # Top 5 opérations les plus rentables
        top_operations = sorted(
            operations,
            key=lambda x: x.get("marge", 0),
            reverse=True
        )[:5]
        
        # Enrichir avec les noms
        for op in top_operations:
            ssn = op.get("responsable", "Inconnu")
            employe = next((p for p in personnel if p.get("ssn") == ssn), None)
            if employe:
                op["responsable_nom"] = employe.get("nom_prenom", ssn)
            else:
                op["responsable_nom"] = ssn
        
        # Analyse mots-clés (les plus utilisés)
        mots_cles_responsable = {}
        mots_cles_client = {}
        
        for op in operations:
            mot_resp = op.get("mot_cle_responsable", "")
            mot_client = op.get("mot_cle_client", "")
            
            if mot_resp:
                mots_cles_responsable[mot_resp] = mots_cles_responsable.get(mot_resp, 0) + 1
            if mot_client:
                mots_cles_client[mot_client] = mots_cles_client.get(mot_client, 0) + 1
        
        top_mots_responsable = sorted(
            [{"mot": k, "count": v} for k, v in mots_cles_responsable.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:10]
        
        top_mots_client = sorted(
            [{"mot": k, "count": v} for k, v in mots_cles_client.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:10]
        
        # Analyse par état (si le champ existe)
        operations_par_etat = {}
        for op in operations:
            etat = op.get("etat", "inconnu")
            operations_par_etat[etat] = operations_par_etat.get(etat, 0) + 1
        
        # Préparer les données pour le template
        overview = {
            # KPIs Principaux
            "total_operations": total_operations,
            "marge_totale": round(marge_totale, 2),
            "distance_totale": round(distance_totale, 2),
            "meilleure_operation": meilleure_operation,
            "marge_moyenne": round(marge_moyenne, 2),
            "distance_moyenne": round(distance_moyenne, 2),
            
            # Ratios
            "ratio_achats_ventes": round(ratio_achats_ventes, 1),
            "ratio_marges": round(ratio_marges, 1),
            "nb_achats": achats,
            "nb_ventes": ventes,
            
            # Graphiques
            "graphique_types": graphique_types,
            "graphique_marges": graphique_marges,
            "top_responsables": top_responsables,
            "top_distances": top_distances,
            "graphique_evolution": graphique_evolution,
            "top_ops_responsables": top_ops_responsables,
            
            # Analyses
            "responsable_plus_actif": responsable_plus_actif,
            "operations_marges_negatives": operations_marges_negatives,
            "top_operations": top_operations,
            "top_mots_responsable": top_mots_responsable,
            "top_mots_client": top_mots_client,
            "operations_par_etat": operations_par_etat
        }
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        overview = {}
    
    return render_template("operations.html", overview=overview, user=user)

@app.route("/surveillance/analyse")
def analyse_surveillance():
    """
    Page d'analyse de la surveillance des zones
    """
    
    user = {
        "nom": request.args.get("nom"),
        "service": request.args.get("service"),
        "role": request.args.get("role")
    }
    
    if not user["nom"] or not user["service"]:
        return redirect("/")
    
    try:
        # ========================================
        # RÉCUPÉRATION DES DONNÉES BRUTES
        # ========================================
        surveillance = requests.get(f"{SERVER_DONNEES_URL}/data/surveillance").json()
        
        # ========================================
        # KPIs PRINCIPAUX (CALCULS MÉTIER)
        # ========================================
        
        # KPI 1 : Nombre de zones surveillées
        total_zones = len(surveillance)
        
        # KPI 2 : Zones avec incendie actif
        zones_incendie = len([z for z in surveillance if z.get("detection_incendie") == "oui"])
        
        # KPI 3 : Total drones actifs
        total_drones_actifs = sum(z.get("drones_actifs", 0) for z in surveillance)
        
        # KPI 4 : Total drones en panne
        total_drones_panne = sum(z.get("drones_panne", 0) for z in surveillance)
        
        # KPI 5 : Total drones en rechargement
        total_drones_rechargement = sum(z.get("drones_rechargement", 0) for z in surveillance)
        
        # KPI 6 : Zones conformes (audit)
        zones_conformes = len([z for z in surveillance if z.get("audit_conformite") == "oui"])
        taux_conformite = (zones_conformes / total_zones * 100) if total_zones > 0 else 0
        
        # KPI 7 : Taux opérationnel des drones
        total_drones = total_drones_actifs + total_drones_panne + total_drones_rechargement
        taux_operationnel = (total_drones_actifs / total_drones * 100) if total_drones > 0 else 0
        
        # ========================================
        # GRAPHIQUES (AGRÉGATIONS)
        # ========================================
        
        # Graphique 1 : Types d'incidents
        incident_incendie = zones_incendie
        incident_panne = len([z for z in surveillance if z.get("drones_panne", 0) > 0])
        incident_audit = len([z for z in surveillance if z.get("audit_conformite") == "non"])
        
        graphique_incidents = {
            "labels": ["Incendie", "Panne drone", "Audit non conforme"],
            "values": [incident_incendie, incident_panne, incident_audit]
        }
        
        # Graphique 2 : État des drones (global)
        graphique_drones = [
            {"etat": "Actifs", "total": total_drones_actifs},
            {"etat": "En panne", "total": total_drones_panne},
            {"etat": "En rechargement", "total": total_drones_rechargement}
        ]
        
        # Graphique 3 : Détection de formes
        formes_count = {}
        for z in surveillance:
            forme = z.get("detection_forme", "aucune")
            formes_count[forme] = formes_count.get(forme, 0) + 1
        
        graphique_formes = [
            {"forme": k, "total": v}
            for k, v in formes_count.items()
        ]
        
        # Graphique 4 : Zones par état de conformité
        graphique_conformite = [
            {"etat": "Conforme", "total": zones_conformes},
            {"etat": "Non conforme", "total": total_zones - zones_conformes}
        ]
        
        # Graphique 5 : Drones actifs par zone
        graphique_drones_zones = [
            {
                "zone": f"Zone {z.get('zone', 0)}",
                "actifs": z.get("drones_actifs", 0)
            }
            for z in sorted(surveillance, key=lambda x: x.get('zone', 0))
        ]
        
        # Graphique 6 : Comparaison drones (actifs vs panne) par zone
        zones_comparison = {
            "zones": [f"Zone {z.get('zone', 0)}" for z in sorted(surveillance, key=lambda x: x.get('zone', 0))],
            "actifs": [z.get("drones_actifs", 0) for z in sorted(surveillance, key=lambda x: x.get('zone', 0))],
            "panne": [z.get("drones_panne", 0) for z in sorted(surveillance, key=lambda x: x.get('zone', 0))]
        }
        
        # ========================================
        # ALERTES CRITIQUES
        # ========================================
        
        # Zones avec incendie
        zones_incendie_list = [
            {
                "zone": z.get("zone"),
                "drones_actifs": z.get("drones_actifs", 0),
                "detection_forme": z.get("detection_forme")
            }
            for z in surveillance if z.get("detection_incendie") == "oui"
        ]
        
        # Zones avec beaucoup de drones en panne (>= 2)
        zones_panne_critique = [
            {
                "zone": z.get("zone"),
                "drones_panne": z.get("drones_panne", 0),
                "drones_actifs": z.get("drones_actifs", 0),
                "total_drones": z.get("drones_actifs", 0) + z.get("drones_panne", 0) + z.get("drones_rechargement", 0)
            }
            for z in surveillance if z.get("drones_panne", 0) >= 2
        ]
        
        # Zones non conformes
        zones_non_conformes = [
            {
                "zone": z.get("zone"),
                "detection_forme": z.get("detection_forme"),
                "drones_actifs": z.get("drones_actifs", 0),
                "detection_incendie": z.get("detection_incendie")
            }
            for z in surveillance if z.get("audit_conformite") == "non"
        ]
        
        # Zones avec détection de forme suspecte
        zones_forme_suspecte = [
            {
                "zone": z.get("zone"),
                "detection_forme": z.get("detection_forme"),
                "drones_actifs": z.get("drones_actifs", 0)
            }
            for z in surveillance 
            if z.get("detection_forme") not in ["aucune", ""]
        ]
        
        # ========================================
        # STATISTIQUES AVANCÉES
        # ========================================
        
        # Zone avec le plus de drones
        if surveillance:
            zone_max_drones = max(surveillance, key=lambda x: x.get("drones_actifs", 0))
        else:
            zone_max_drones = None
        
        # Zone avec le moins de drones
        if surveillance:
            zone_min_drones = min(surveillance, key=lambda x: x.get("drones_actifs", 0))
        else:
            zone_min_drones = None
        
        # Nombre moyen de drones par zone
        moyenne_drones_actifs = total_drones_actifs / total_zones if total_zones > 0 else 0
        
        # Zones nécessitant une intervention urgente
        zones_urgentes = [
            z for z in surveillance
            if z.get("detection_incendie") == "oui" 
            or z.get("drones_panne", 0) >= 2
            or z.get("audit_conformite") == "non"
        ]
        
        # Préparer les données pour le template
        overview = {
            # KPIs Principaux
            "total_zones": total_zones,
            "zones_incendie": zones_incendie,
            "total_drones_actifs": total_drones_actifs,
            "total_drones_panne": total_drones_panne,
            "total_drones_rechargement": total_drones_rechargement,
            "taux_conformite": round(taux_conformite, 1),
            "taux_operationnel": round(taux_operationnel, 1),
            "zones_conformes": zones_conformes,
            
            # Graphiques
            "graphique_incidents": graphique_incidents,
            "graphique_drones": graphique_drones,
            "graphique_formes": graphique_formes,
            "graphique_conformite": graphique_conformite,
            "graphique_drones_zones": graphique_drones_zones,
            "zones_comparison": zones_comparison,
            
            # Alertes
            "zones_incendie_list": zones_incendie_list,
            "zones_panne_critique": zones_panne_critique,
            "zones_non_conformes": zones_non_conformes,
            "zones_forme_suspecte": zones_forme_suspecte,
            "zones_urgentes": zones_urgentes,
            
            # Statistiques
            "zone_max_drones": zone_max_drones,
            "zone_min_drones": zone_min_drones,
            "moyenne_drones_actifs": round(moyenne_drones_actifs, 1)
        }
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        overview = {}
    
    return render_template("surveillance.html", overview=overview, user=user)
@app.route("/sanitaire/analyse")
def analyse_sanitaire():
    """
    Page d'analyse des relevés sanitaires
    """
    
    user = {
        "nom": request.args.get("nom"),
        "service": request.args.get("service"),
        "role": request.args.get("role")
    }
    
    if not user["nom"] or not user["service"]:
        return redirect("/")
    
    try:
        # ========================================
        # RÉCUPÉRATION DES DONNÉES BRUTES
        # ========================================
        releves = requests.get(f"{SERVER_DONNEES_URL}/data/releves_sanitaires").json()
        
        # ========================================
        # KPIs PRINCIPAUX (CALCULS MÉTIER)
        # ========================================
        
        # KPI 1 : Nombre de zones surveillées
        zones_uniques = set(r.get("zone") for r in releves)
        total_zones = len(zones_uniques)
        
        # KPI 2 : Température moyenne
        temperatures = [r.get("temperature", 0) for r in releves if r.get("temperature")]
        temp_moyenne = sum(temperatures) / len(temperatures) if temperatures else 0
        
        # KPI 3 : Zone avec le meilleur CO2 (le plus bas)
        if releves:
            zone_meilleur_co2 = min(releves, key=lambda x: x.get("co2", 999))
        else:
            zone_meilleur_co2 = None
        
        # KPI 4 : Zone avec la meilleure qualité d'air (PM2.5 le plus bas)
        if releves:
            zone_meilleur_air = min(releves, key=lambda x: x.get("pm2_5", 999))
        else:
            zone_meilleur_air = None
        
        # KPI 5 : Humidité moyenne
        humidites = [r.get("humidite", 0) for r in releves if r.get("humidite")]
        humidite_moyenne = sum(humidites) / len(humidites) if humidites else 0
        
        # KPI 6 : Zones avec conditions optimales (temp 21-24°C ET humidité 45-55%)
        zones_optimales = len([
            r for r in releves 
            if 21 <= r.get("temperature", 0) <= 24 
            and 45 <= r.get("humidite", 0) <= 55
        ])
        
        # ========================================
        # GRAPHIQUES (AGRÉGATIONS)
        # ========================================
        
        # Graphique 1 : Température par zone
        temp_par_zone = {}
        count_par_zone = {}
        
        for r in releves:
            zone = r.get("zone")
            temp = r.get("temperature", 0)
            
            if zone not in temp_par_zone:
                temp_par_zone[zone] = 0
                count_par_zone[zone] = 0
            
            temp_par_zone[zone] += temp
            count_par_zone[zone] += 1
        
        graphique_temperature = [
            {
                "zone": f"Zone {zone}",
                "temperature": round(temp_par_zone[zone] / count_par_zone[zone], 1)
            }
            for zone in sorted(temp_par_zone.keys())
        ]
        
        # Graphique 2 : CO2 par zone
        co2_par_zone = {}
        co2_count = {}
        
        for r in releves:
            zone = r.get("zone")
            co2 = r.get("co2", 0)
            
            if zone not in co2_par_zone:
                co2_par_zone[zone] = 0
                co2_count[zone] = 0
            
            co2_par_zone[zone] += co2
            co2_count[zone] += 1
        
        graphique_co2 = [
            {
                "zone": f"Zone {zone}",
                "co2": round(co2_par_zone[zone] / co2_count[zone], 3)
            }
            for zone in sorted(co2_par_zone.keys())
        ]
        
        # Graphique 3 : Humidité par zone
        hum_par_zone = {}
        hum_count = {}
        
        for r in releves:
            zone = r.get("zone")
            hum = r.get("humidite", 0)
            
            if zone not in hum_par_zone:
                hum_par_zone[zone] = 0
                hum_count[zone] = 0
            
            hum_par_zone[zone] += hum
            hum_count[zone] += 1
        
        graphique_humidite = [
            {
                "zone": f"Zone {zone}",
                "humidite": round(hum_par_zone[zone] / hum_count[zone], 1)
            }
            for zone in sorted(hum_par_zone.keys())
        ]
        
        # Graphique 4 : Qualité de l'air (PM10 et PM2.5) par zone
        pm10_par_zone = {}
        pm25_par_zone = {}
        pm_count = {}
        
        for r in releves:
            zone = r.get("zone")
            pm10 = r.get("pm10", 0)
            pm25 = r.get("pm2_5", 0)
            
            if zone not in pm10_par_zone:
                pm10_par_zone[zone] = 0
                pm25_par_zone[zone] = 0
                pm_count[zone] = 0
            
            pm10_par_zone[zone] += pm10
            pm25_par_zone[zone] += pm25
            pm_count[zone] += 1
        
        zones_list = sorted(pm10_par_zone.keys())
        graphique_qualite_air = {
            "zones": [f"Zone {z}" for z in zones_list],
            "pm10": [round(pm10_par_zone[z] / pm_count[z], 3) for z in zones_list],
            "pm25": [round(pm25_par_zone[z] / pm_count[z], 3) for z in zones_list]
        }
        
        # Graphique 5 : Pression atmosphérique par zone
        pression_par_zone = {}
        pression_count = {}
        
        for r in releves:
            zone = r.get("zone")
            pression = r.get("pression", 0)
            
            if zone not in pression_par_zone:
                pression_par_zone[zone] = 0
                pression_count[zone] = 0
            
            pression_par_zone[zone] += pression
            pression_count[zone] += 1
        
        graphique_pression = [
            {
                "zone": f"Zone {zone}",
                "pression": round(pression_par_zone[zone] / pression_count[zone], 2)
            }
            for zone in sorted(pression_par_zone.keys())
        ]
        
        # Graphique 6 : Indicateurs comparatifs (min, max, moyenne)
        graphique_comparatif = {
            "temperature": {
                "min": round(min(temperatures), 1) if temperatures else 0,
                "max": round(max(temperatures), 1) if temperatures else 0,
                "moy": round(temp_moyenne, 1)
            },
            "humidite": {
                "min": round(min(humidites), 1) if humidites else 0,
                "max": round(max(humidites), 1) if humidites else 0,
                "moy": round(humidite_moyenne, 1)
            }
        }
        
        # ========================================
        # ALERTES ET ANALYSES
        # ========================================
        
        # Zones avec température élevée (>25°C)
        zones_temp_elevee = []
        for zone in zones_uniques:
            zone_releves = [r for r in releves if r.get("zone") == zone]
            temp_moy = sum(r.get("temperature", 0) for r in zone_releves) / len(zone_releves)
            if temp_moy > 25:
                zones_temp_elevee.append({
                    "zone": zone,
                    "temperature": round(temp_moy, 1)
                })
        
        # Zones avec CO2 élevé (>0.06)
        zones_co2_eleve = []
        for zone in zones_uniques:
            zone_releves = [r for r in releves if r.get("zone") == zone]
            co2_moy = sum(r.get("co2", 0) for r in zone_releves) / len(zone_releves)
            if co2_moy > 0.06:
                zones_co2_eleve.append({
                    "zone": zone,
                    "co2": round(co2_moy, 3)
                })
        
        # Zones avec particules élevées (PM2.5 > 0.03)
        zones_particules_elevees = []
        for zone in zones_uniques:
            zone_releves = [r for r in releves if r.get("zone") == zone]
            pm25_moy = sum(r.get("pm2_5", 0) for r in zone_releves) / len(zone_releves)
            if pm25_moy > 0.03:
                zones_particules_elevees.append({
                    "zone": zone,
                    "pm2_5": round(pm25_moy, 3)
                })
        
        # Zones avec humidité problématique (<40% ou >60%)
        zones_humidite_probleme = []
        for zone in zones_uniques:
            zone_releves = [r for r in releves if r.get("zone") == zone]
            hum_moy = sum(r.get("humidite", 0) for r in zone_releves) / len(zone_releves)
            if hum_moy < 40 or hum_moy > 60:
                zones_humidite_probleme.append({
                    "zone": zone,
                    "humidite": round(hum_moy, 1),
                    "probleme": "Trop sec" if hum_moy < 40 else "Trop humide"
                })
        
        # ========================================
        # CLASSEMENTS
        # ========================================
        
        # Top 5 zones avec meilleur CO2
        top_co2 = sorted(
            [
                {
                    "zone": zone,
                    "co2": round(co2_par_zone[zone] / co2_count[zone], 3)
                }
                for zone in co2_par_zone.keys()
            ],
            key=lambda x: x["co2"]
        )[:5]
        
        # Top 5 zones avec pire CO2
        pire_co2 = sorted(
            [
                {
                    "zone": zone,
                    "co2": round(co2_par_zone[zone] / co2_count[zone], 3)
                }
                for zone in co2_par_zone.keys()
            ],
            key=lambda x: x["co2"],
            reverse=True
        )[:5]
        
        # Préparer les données pour le template
        overview = {
            # KPIs Principaux
            "total_zones": total_zones,
            "temp_moyenne": round(temp_moyenne, 1),
            "zone_meilleur_co2": zone_meilleur_co2,
            "zone_meilleur_air": zone_meilleur_air,
            "humidite_moyenne": round(humidite_moyenne, 1),
            "zones_optimales": zones_optimales,
            
            # Graphiques
            "graphique_temperature": graphique_temperature,
            "graphique_co2": graphique_co2,
            "graphique_humidite": graphique_humidite,
            "graphique_qualite_air": graphique_qualite_air,
            "graphique_pression": graphique_pression,
            "graphique_comparatif": graphique_comparatif,
            
            # Alertes
            "zones_temp_elevee": zones_temp_elevee,
            "zones_co2_eleve": zones_co2_eleve,
            "zones_particules_elevees": zones_particules_elevees,
            "zones_humidite_probleme": zones_humidite_probleme,
            
            # Classements
            "top_co2": top_co2,
            "pire_co2": pire_co2
        }
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        overview = {}
    
    return render_template("sanitaire.html", overview=overview, user=user)

if __name__ == "__main__":
    CORS(app)
    app.run(host="0.0.0.0", port=5000, debug=True)

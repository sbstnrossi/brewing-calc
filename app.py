import os
from flask import Flask, request, jsonify, render_template_string, render_template, redirect, url_for, Response
from google.cloud import firestore
from recipeman import RecipeManager
from batchman import BatchManager
import sync_utils
import re
from datetime import datetime
import core
import json

app = Flask(__name__)

# Inicializa el cliente de Firestore.
# Al desplegar en Cloud Run, detecta automáticamente la cuenta de servicio y el proyecto GCP.
db = firestore.Client()

# Inicializar gestores (detectan automáticamente si usan Firestore o JSON local)
recipe_mgr = RecipeManager()
batch_mgr = BatchManager()


# --- RUTAS DE SALUD Y DIAGNÓSTICO ---
@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "Brewing Calc API",
        "mode": {
            "recipe_storage": "Firestore" if recipe_mgr.use_firestore else "Local JSON",
            "batch_storage": "Firestore" if batch_mgr.use_firestore else "Local JSON"
        }
    }), 200

# --- RUTAS DE RECETAS Y MALTAS ---
@app.route("/recipes", methods=["GET"])
def list_recipes():
    """Devuelve la lista o catálogo de recetas."""
    try:
        # Si la colección no tiene método list_all, se usa get_recipe o se recorre el almacén
        recipes = recipe_mgr._read_json(recipe_mgr.recipes_file) if not recipe_mgr.use_firestore else [
            doc.to_dict() for doc in recipe_mgr.recipes_ref.stream()
        ]
        return jsonify({"recipes": recipes}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recipes/<recipe_id>", methods=["GET"])
def get_recipe(recipe_id: str):
    """Obtiene el detalle resuelto de una receta (con granos y agua resueltos)."""
    target_vol = request.args.get("volume", type=float)
    try:
        details = recipe_mgr.get_recipe_details(recipe_id, target_volume_l=target_vol)
        return jsonify(details), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Error procesando la receta: {str(e)}"}), 500

@app.route("/recipes", methods=["POST"])
def save_recipe():
    """Guarda o actualiza una receta."""
    data = request.get_json()
    if not data or "id" not in data:
        return jsonify({"error": "Se requiere un objeto JSON con el campo 'id'."}), 400

    recipe_mgr.save_recipe(data["id"], data)
    return jsonify({"message": f"Receta '{data['id']}' guardada con éxito.", "recipe": data}), 201

@app.route("/malts", methods=["GET"])
def list_malts():
    """Obtiene el catálogo de maltas disponibles."""
    malts = recipe_mgr.get_all_malts()
    return jsonify({"malts": malts}), 200

# --- RUTAS DE LOTES (BATCHES) ---
@app.route("/batches", methods=["GET"])
def list_batches():
    """Devuelve el historial de lotes elaborados."""
    batches = batch_mgr.list_batches()
    return jsonify({"batches": batches}), 200

@app.route("/batches", methods=["POST"])
def create_or_update_batch():
    """
    Procesa las mediciones de un lote (calcula % ABV con fórmula de Michael Hall)
    y lo guarda en la base de datos activo.
    """
    data = request.get_json()
    if not data or "id" not in data:
        return jsonify({"error": "El registro debe incluir el campo 'id' del lote."}), 400

    try:
        processed_batch = batch_mgr.process_and_save_batch(data)
        return jsonify({
            "message": f"Lote '{data['id']}' procesado y guardado correctamente.",
            "batch": processed_batch
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/batches", methods=["POST"])
def guardar_lote():
    """Guarda un lote recibido en formato JSON dentro de la colección 'batches'."""
    data = request.get_json()
    
    if not data or "id" not in data:
        return jsonify({"error": "Se requiere un objeto JSON con la clave 'id'"}), 400

    lote_id = data["id"]
    
    # Referencia al documento en la colección 'batches'
    doc_ref = db.collection("batches").document(lote_id)
    doc_ref.set(data, merge=True)

    return jsonify({
        "status": "success", 
        "message": f"Lote '{lote_id}' guardado correctamente en Firestore."
    }), 201


@app.route("/api/batches/<lote_id>", methods=["GET"])
def obtener_lote(lote_id):
    """Recupera un lote específico desde Firestore."""
    doc_ref = db.collection("batches").document(lote_id)
    doc = doc_ref.get()

    if doc.exists:
        return jsonify(doc.to_dict()), 200
    
    return jsonify({"error": f"El lote '{lote_id}' no existe."}), 404

# --- RUTAS DE GESTION DE TABLAS ---
@app.route("/tables/sync", methods=["POST"])
def sync_tables():
    # Sincroniza las recetas desde el archivo local si querés hacer un restore
    # TODO recorrer jsons y comparar
    success, msg = sync_utils.sync_json_to_firestore("recipes", "recipes.json")
    return jsonify({"success": success, "message": msg})


# -------------------------------------------------------------------
# Vistas de Gestión de Tablas
# -------------------------------------------------------------------

@app.route("/tables")
def tables_dashboard():
    """Vista principal de gestión de tablas: muestra resumen de colecciones."""
    recipes_ref = db.collection("recipes").stream()
    recipes = [doc.to_dict() | {"id": doc.id} for doc in recipes_ref]

    water_profiles_ref = db.collection("profiles").stream()
    water_profiles = [doc.to_dict() | {"id": doc.id} for doc in water_profiles_ref]

    return render_template("tables.html", recipes=recipes, water_profiles=water_profiles)

@app.route("/tables/recipe/new", methods=["GET"])
def new_recipe_form():
    # Obtener maltas desde RecipeManager o Firestore
    malts_dict = recipe_mgr.get_all_malts()  # Devuelve dict {malt_id: {name, di_ph, ...}}
    malts_list = [{"id": k} | v for k, v in malts_dict.items()]
    """Carga los perfiles de agua existentes para el selector y muestra el formulario."""
    water_profiles_ref = db.collection("profiles").stream()
    water_profiles = [
        doc.to_dict() | {"id": doc.id, "name": doc.to_dict().get("name", doc.id.replace("_", " ").title())} 
        for doc in water_profiles_ref
    ]
    
    return render_template(
        "recipe_form.html", 
        water_profiles=water_profiles, 
        malts=malts_list,
        recipe=None  # Indicar que es un alta nueva
    )


@app.route("/tables/recipe/edit/<recipe_id>", methods=["GET"])
def edit_recipe_form(recipe_id):
    """Carga una receta existente y renderiza el mismo formulario pre-poblado."""
    recipe_doc = db.collection("recipes").document(recipe_id).get()
    if not recipe_doc.exists:
        return "Receta no encontrada", 404

    recipe = recipe_doc.to_dict() | {"id": recipe_id}
    
    malts_dict = recipe_mgr.get_all_malts()
    malts_list = [{"id": k} | v for k, v in malts_dict.items()]

    water_profiles_ref = db.collection("profiles").stream()
    water_profiles = [
        doc.to_dict() | {"id": doc.id, "name": doc.to_dict().get("name", doc.id.replace("_", " ").title())} 
        for doc in water_profiles_ref
    ]

    return render_template(
        "recipe_form.html",
        water_profiles=water_profiles,
        malts=malts_list,
        recipe=recipe  # Pasamos la receta existente
    )


def slugify(text: str) -> str:
    """Convierte un texto en un ID limpio para Firestore (ej: 'American IPA #1' -> 'american_ipa_1')."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '_', text)


@app.route("/tables/recipe/add", methods=["POST"])
def add_recipe():
    """Recibe la receta completa en formato JSON y la guarda en Firestore."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No se recibieron datos en JSON"}), 400

        # Si viene un ID explícito (al editar) se usa ese; si no, se genera un slug del nombre
        recipe_id = data.get("id") or slugify(data.get("name", "receta_sin_nombre"))

        # Documento estructurado para Firestore
        recipe_doc = {
            "id": recipe_id,
            "name": data.get("name"),
            "style": data.get("style"),
            "batch_size_l": float(data.get("batch_size_l", 20.0)),
            "target_og": float(data.get("target_og", 1.050)),
            "target_fg": float(data.get("target_fg", 1.010)),
            "target_ph": float(data.get("target_ph", 5.3)),
            "target_water_profile_id": data.get("target_water_profile_id", ""),
            "yeast": data.get("yeast", ""),
            "ibu": float(data.get("ibu", 0)),
            "ebc": float(data.get("ebc", 0)),
            "mash_temp": float(data.get("mash_temp", 65.0)),
            "boil_time_min": int(data.get("boil_time_min", 60)),
            "grain_bill": data.get("grain_bill", []),  # Lista de dicts
            "hop_bill": data.get("hop_bill", []),                 # Lista de dicts
            "notes": data.get("notes", "")
        }

        # Guardar en la colección 'recipes' de Firestore
        db.collection("recipes").document(recipe_id).set(recipe_doc, merge=True)

        return jsonify({"status": "ok", "redirect_url": url_for("tables_dashboard")})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    
@app.route("/tables/recipe/export/<recipe_id>", methods=["GET"])
def export_recipe_json(recipe_id):
    """Obtiene el documento de Firestore y lo entrega como un archivo JSON descargable."""
    doc_ref = db.collection("recipes").document(recipe_id).get()
    
    if not doc_ref.exists:
        return "La receta no existe en Firestore", 404

    recipe_data = doc_ref.to_dict()
    recipe_data["id"] = recipe_id

    # Convertimos el diccionario a una cadena JSON formateada con sangría
    json_output = json.dumps(recipe_data, indent=2, ensure_ascii=False)

    return Response(
        json_output,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename={recipe_id}.json"}
    )

    
@app.route("/tables/water/new", methods=["GET"])
def new_water_profile_form():
    """Formulario para crear un nuevo perfil de agua."""
    return render_template("water_profile_form.html", profile=None)


@app.route("/tables/water/edit/<profile_id>", methods=["GET"])
def edit_water_profile_form(profile_id):
    """Formulario pre-poblado para editar un perfil de agua existente."""
    doc_ref = db.collection("profiles").document(profile_id).get()
    if not doc_ref.exists:
        return "Perfil de agua no encontrado", 404

    profile = doc_ref.to_dict() | {"id": profile_id}
    profile["name"] = profile.get("name", profile_id.replace("_", " ").title())
    return render_template("water_profile_form.html", profile=profile)


@app.route("/tables/water/add", methods=["POST"])
def add_water_profile():
    """Guarda o actualiza un perfil de agua en Firestore."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No se recibieron datos JSON"}), 400

        # Si viene ID se mantiene (Edición); si no, se genera desde el nombre (Alta)
        profile_id = data.get("id") or slugify(data.get("name", "perfil_agua"))

        profile_doc = {
            "id": profile_id,
            "name": data.get("name"),
            "ca": float(data.get("ca", 0.0)),      # Calcio
            "mg": float(data.get("mg", 0.0)),      # Magnesio
            "na": float(data.get("na", 0.0)),      # Sodio
            "so4": float(data.get("so4", 0.0)),    # Sulfato
            "cl": float(data.get("cl", 0.0)),      # Cloruro
            "hco3": float(data.get("hco3", 0.0)),  # Bicarbonato
            "ph_base": float(data.get("ph_base", 7.0)),
            "notes": data.get("notes", "")
        }

        db.collection("profiles").document(profile_id).set(profile_doc, merge=True)
        return jsonify({"status": "ok", "redirect_url": url_for("tables_dashboard")})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    
###############################################################################
# SECCION PARA COCCION
###############################################################################

@app.route("/brew", methods=["GET"])
def brew_setup():
    """Pantalla inicial: selección de receta, perfil base (usado) y perfil objetivo."""
    recipes_ref = db.collection("recipes").stream()
    recipes = [doc.to_dict() | {"id": doc.id} for doc in recipes_ref]

    # Colección 'profiles' en Firestore
    profiles_ref = db.collection("profiles").stream()
    profiles = [
        doc.to_dict() | {"id": doc.id, "name": doc.to_dict().get("name", doc.id.replace("_", " ").title())}
        for doc in profiles_ref
    ]

    # Pasamos las sales de core.py para renderizar los checkboxes dinámicamente
    available_salts_db = core.SALTS_DATABASE

    return render_template(
        "brew_setup.html", 
        recipes=recipes, 
        profiles=profiles, 
        salts_db=available_salts_db
    )


@app.route("/brew/start", methods=["POST"])
def start_brew():
    """Crea un nuevo lote (batch) y calcula el perfil de sales."""
    data = request.get_json()
    batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    water_used_id = data.get("water_used_id", "")
    target_water_profile_id = data.get("target_water_profile_id", "")
    mash_water_l = float(data.get("mash_water_l", 15.0))
    selected_salts = data.get("salts_available", [])

    # 1. Obtener perfiles de agua desde Firestore ('profiles')
    source_profile_doc = db.collection("profiles").document(water_used_id).get() if water_used_id else None
    target_profile_doc = db.collection("profiles").document(target_water_profile_id).get() if target_water_profile_id else None

    source_data = source_profile_doc.to_dict() if (source_profile_doc and source_profile_doc.exists) else {}
    target_data = target_profile_doc.to_dict() if (target_profile_doc and target_profile_doc.exists) else {}

    # 2. Formatear perfiles para core.py (solo iones: ca, mg, na, so4, cl, hco3)
    IONS = ["ca", "mg", "na", "so4", "cl", "hco3"]
    source_ions = {ion: float(source_data.get(ion, 0.0)) for ion in IONS}
    target_ions = {ion: float(target_data.get(ion, 0.0)) for ion in IONS}

    # 3. Calcular adición de sales si existen ambos perfiles
    salt_results = {}
    if water_used_id and target_water_profile_id:
        try:
            # Si el usuario seleccionó sales específicas, podemos pasar un diccionario filtrado de pesos/disponibilidad
            salt_results = core.solve_salt_additions(
                source_profile=source_ions,
                target_profile=target_ions,
                volume_liters=mash_water_l
            )
        except Exception as e:
            salt_results = {"error": f"No se pudo calcular la adición: {str(e)}"}

    batch_doc = {
        "id": batch_id,
        "recipe_id": data.get("recipe_id"),
        "recipe_name": data.get("recipe_name", "Lote Sin Nombre"),
        "status": "in_progress",
        "created_at": datetime.now().isoformat(),
        "expected_liters": float(data.get("expected_liters", 20.0)),
        "mash_water_l": mash_water_l,
        "water_used_id": water_used_id,
        "target_water_profile_id": target_water_profile_id,
        "acid_used": data.get("acid_used", ""),
        "salts_available": selected_salts,
        "salt_additions_result": salt_results,  # Guardamos el resultado del cálculo
        "temp_input_mode": data.get("temp_input_mode", "manual"),
        "timestamps": {"additions": []},
        "readings": []
    }

    db.collection("batches").document(batch_doc["id"]).set(batch_doc)
    return jsonify({"status": "ok", "redirect_url": url_for("brew_session", batch_id=batch_doc["id"])})    


@app.route("/brew/session/<batch_id>", methods=["GET"])
def brew_session(batch_id):
    """Panel de control interactivo durante el día de cocción."""
    doc_ref = db.collection("batches").document(batch_id).get()
    if not doc_ref.exists:
        return "Lote no encontrado", 404

    batch = doc_ref.to_dict() | {"id": batch_id}
    return render_template("brew_session.html", batch=batch)


@app.route("/brew/update/<batch_id>", methods=["POST"])
def update_brew_session(batch_id):
    """Actualiza timestamps, registros de temperatura/pH o notas en tiempo real."""
    data = request.get_json()
    db.collection("batches").document(batch_id).set(data, merge=True)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Toma el puerto de Cloud Run ($PORT) o usa 8080 en ejecuciones locales
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

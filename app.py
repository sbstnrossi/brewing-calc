import os
from flask import Flask, request, jsonify, render_template_string, render_template, redirect, url_for
from google.cloud import firestore
from recipeman import RecipeManager
from batchman import BatchManager
import sync_utils

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
    """Carga los perfiles de agua existentes para el selector y muestra el formulario."""
    water_profiles_ref = db.collection("water_profiles").stream()
    water_profiles = [doc.to_dict() | {"id": doc.id} for doc in water_profiles_ref]
    
    return render_template("recipe_form.html", water_profiles=water_profiles)


@app.route("/tables/recipe/add", methods=["POST"])
def add_recipe():
    """Recibe la receta completa en formato JSON y la guarda en Firestore."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No se recibieron datos en JSON"}), 400

        # Documento estructurado para Firestore
        recipe_doc = {
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
            "fermentables": data.get("fermentables", []),  # Lista de dicts
            "hops": data.get("hops", []),                 # Lista de dicts
            "notes": data.get("notes", "")
        }

        # Guardar en la colección 'recipes' de Firestore
        doc_ref = db.collection("recipes").document()
        recipe_doc["id"] = doc_ref.id
        doc_ref.set(recipe_doc)

        return jsonify({"status": "ok", "redirect_url": url_for("tables_dashboard")})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # Toma el puerto de Cloud Run ($PORT) o usa 8080 en ejecuciones locales
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

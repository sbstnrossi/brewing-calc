import os
from flask import Flask, request, jsonify, render_template_string
from google.cloud import firestore

app = Flask(__name__)

# Inicializa el cliente de Firestore.
# Al desplegar en Cloud Run, detecta automáticamente la cuenta de servicio y el proyecto GCP.
db = firestore.Client()


@app.route("/", methods=["GET"])
def home():
    """Página de inicio sencilla para verificar que la app está viva."""
    return render_template_string("""
        <h1>🍺 Brewing Calc API</h1>
        <p>Servidor activo en Google Cloud Run.</p>
        <ul>
            <li><code>POST /api/batches</code> - Guardar un lote en Firestore</li>
            <li><code>GET /api/batches/&lt;lote_id&gt;</code> - Obtener un lote de Firestore</li>
        </ul>
    """)


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


if __name__ == "__main__":
    # Toma el puerto de Cloud Run ($PORT) o usa 8080 en ejecuciones locales
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
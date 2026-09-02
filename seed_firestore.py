import json
import os
from typing import Dict, Any, List, Tuple
from google.cloud import firestore

# Inicializar cliente de Firestore (utiliza la autenticación local de gcloud)
db = firestore.Client()


def extract_items(data: Any) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Extrae elementos en formato (doc_id, dict_contenido) 
    soportando listas o diccionarios anidados.
    """
    items = []

    if isinstance(data, list):
        for idx, item in enumerate(data):
            doc_id = item.get("id") or f"doc_{idx}"
            items.append((str(doc_id), item))

    elif isinstance(data, dict):
        # Si la lista viene envuelta bajo una clave principal (ej: {"recipes": [...]})
        for key in ["recipes", "batches", "lotes", "malts", "items"]:
            if key in data and isinstance(data[key], list):
                return extract_items(data[key])

        # Si viene como objeto clave: valor (ej: {"pale_ale": {...}})
        for doc_id, item_data in data.items():
            if isinstance(item_data, dict):
                if "id" not in item_data:
                    item_data["id"] = doc_id
                items.append((str(doc_id), item_data))

    return items


def upload_json_to_firestore(filename: str, collection_name: str) -> None:
    """Lee un JSON local y carga sus documentos a una colección de Firestore."""
    if not os.path.exists(filename):
        print(f"⚠️ El archivo '{filename}' no existe localmente. Omitiendo...")
        return

    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = extract_items(data)
    if not items:
        print(f"⚠️ No se encontraron elementos procesables en '{filename}'.")
        return

    # Batch write (máximo 500 operaciones por lote en Firestore)
    batch = db.batch()
    count = 0

    for doc_id, doc_data in items:
        doc_ref = db.collection(collection_name).document(doc_id)
        batch.set(doc_ref, doc_data, merge=True)
        count += 1

    batch.commit()
    print(f"✅ Se cargaron {count} documentos a la colección '{collection_name}'.")


if __name__ == "__main__":
    print("🚀 Iniciando migración a Firestore...")

    # Carga de colecciones
    #upload_json_to_firestore("malts.json", "malts")
    #upload_json_to_firestore("recipes.json", "recipes")
    upload_json_to_firestore("batches.json", "batches")

    print("🎉 Proceso finalizado.")
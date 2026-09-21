#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 21 14:13:16 2026

@author: sebastian
"""

import json
import os
from google.cloud import firestore

db = firestore.Client()

def sync_json_to_firestore(collection_name: str, json_filepath: str):
    """
    Lee un archivo JSON local y actualiza/inserta los documentos en Firestore.
    """
    if not os.path.exists(json_filepath):
        return False, "El archivo JSON no existe."

    with open(json_filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Si el JSON contiene una lista de elementos
    if isinstance(data, list):
        for item in data:
            doc_id = item.get("id") or item.get("name").lower().replace(" ", "_")
            db.collection(collection_name).document(doc_id).set(item, merge=True)
    elif isinstance(data, dict):
        for doc_id, item in data.items():
            db.collection(collection_name).document(doc_id).set(item, merge=True)

    return True, f"Colección {collection_name} actualizada correctamente desde JSON."
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 27 12:07:21 2026

@author: sebastian
"""

import json
import os
from typing import Dict, Any, List, Optional
import core

# Intento de importación defensiva por si la librería no está instalada en un entorno local ligero
try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False


class RecipeManager:
    def __init__(self, recipes_file: str = "recipes.json", malts_file: str = "malts.json"):
        self.recipes_file = recipes_file
        self.malts_file = malts_file
        self.use_firestore = False
        self.db = None

        # Forzar modo offline vía variable de entorno si se desea (ej: FORCE_OFFLINE=1)
        force_offline = os.getenv("FORCE_OFFLINE", "false").lower() in ("1", "true")

        if FIRESTORE_AVAILABLE and not force_offline:
            try:
                # Intentar instanciar cliente con timeout corto para no bloquear la ejecución local
                self.db = firestore.Client()
                # Realizar una prueba rápida de lectura para verificar conectividad
                self.recipes_ref = self.db.collection("recipes")
                self.malts_ref = self.db.collection("malts")
                self.use_firestore = True
                print("🌐 [RecipeManager] Conectado exitosamente a Firestore.")
            except Exception as e:
                print(f"💻 [RecipeManager] No se pudo conectar a Firestore ({e}). Usando JSON local.")
                self.use_firestore = False
        else:
            print("💻 [RecipeManager] Modo offline/local activo (Usando archivos JSON).")

    # --- Métodos de apoyo para JSON local ---
    def _read_json(self, filepath: str) -> Dict:
        if not os.path.exists(filepath):
            return {}
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    return {item.get("id", str(i)): item for i, item in enumerate(data)}
                return data
            except json.JSONDecodeError:
                return {}

    def _write_json(self, filepath: str, data: Dict) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(list(data.values()), f, indent=4, ensure_ascii=False)

    # --- Operaciones de Dominio (Híbridas) ---
    def get_recipe(self, recipe_id: str) -> Optional[Dict]:
        """Obtiene una receta por su ID desde Firestore o JSON local."""
        if self.use_firestore:
            try:
                doc = self.recipes_ref.document(recipe_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                print(f"⚠️ Error al consultar Firestore: {e}. Recurriendo a lectura local...")

        # Fallback a JSON local
        recipes = self._read_json(self.recipes_file)
        return recipes.get(recipe_id)

    def save_recipe(self, recipe_id: str, recipe_data: Dict) -> None:
        """Guarda o actualiza una receta en Firestore y/o en el JSON local."""
        recipe_data["id"] = recipe_id

        # 1. Intentar guardar en Firestore si está disponible
        if self.use_firestore:
            try:
                self.recipes_ref.document(recipe_id).set(recipe_data, merge=True)
                print(f"✅ Receta '{recipe_id}' guardada en Firestore.")
            except Exception as e:
                print(f"⚠️ Error guardando en Firestore: {e}. Guardando localmente...")

        # 2. Guardar SIEMPRE en local como copia de respaldo/sincronización
        recipes = self._read_json(self.recipes_file)
        recipes[recipe_id] = recipe_data
        self._write_json(self.recipes_file, recipes)

    def scale_recipe(self, recipe_id: str, target_volume_l: float) -> Dict:
        """Escala los ingredientes de una receta para un nuevo volumen objetivo."""
        recipe = self.get_recipe(recipe_id)
        if not recipe:
            raise ValueError(f"Receta '{recipe_id}' no encontrada.")

        base_volume = float(recipe.get("target_volume_l", 20.0))
        if base_volume <= 0:
            raise ValueError("El volumen base de la receta debe ser mayor a 0.")

        scale_factor = target_volume_l / base_volume
        scaled_recipe = recipe.copy()
        scaled_recipe["target_volume_l"] = target_volume_l

        if "fermentables" in scaled_recipe:
            scaled_recipe["fermentables"] = [
                {**item, "amount_kg": round(item.get("amount_kg", 0) * scale_factor, 3)}
                for item in scaled_recipe["fermentables"]
            ]

        if "hops" in scaled_recipe:
            scaled_recipe["hops"] = [
                {**item, "amount_g": round(item.get("amount_g", 0) * scale_factor, 2)}
                for item in scaled_recipe["hops"]
            ]

        return scaled_recipe




def process_batch_data(batch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aplica corrección por temperatura a OG y FG, y genera el bloque de análisis (ABV y Atenuación).
    """
    # Corrección de la Densidad Inicial (OG)
    raw_og = batch["wort"]["gravity_sg"]
    og_temp = batch["wort"]["gravity_temp_c"]
    og_corr = core.correct_gravity(raw_og, og_temp)
    batch["wort"]["corrected_gravity_sg"] = og_corr

    # Corrección de la Densidad Final (FG)
    raw_fg = batch["final_beer"]["final_gravity_sg"]
    fg_temp = batch["final_beer"]["gravity_temp_c"]
    fg_corr = core.correct_gravity(raw_fg, fg_temp)
    batch["final_beer"]["corrected_gravity_sg"] = fg_corr

    # Cálculo de métricas
    abv = core.calculate_abv(og_corr, fg_corr)
    attenuation = round(((og_corr - fg_corr) / (og_corr - 1.0)) * 100, 1) if og_corr > 1.0 else 0.0

    batch["analytics"] = {
        "og_corrected": og_corr,
        "fg_corrected": fg_corr,
        "abv_pct": abv,
        "apparent_attenuation_pct": attenuation
    }
    return batch


def process_batch_from_table(batch_id: str, 
                             filename: str = "batches.json",
                             data_dir: str = "."
    ) -> Dict[str, Any]:
    """Calcula ABV del lote registrado en batches.json"""
    
    path = data_dir + "/" + filename
    with open(path, "r", encoding="utf-8") as f:
        batches_db = json.load(f)
    batches = batches_db.get("batches", [])
    batch = next((r for r in batches if r["id"] == batch_id), None)
    if not batch:
        raise ValueError(f"El lote '{batch_id}' no se encontró.")
    
    return process_batch_data(batch)


def save_batch(batch_data: Dict[str, Any], filepath: str = "lotes.json") -> None:
    """Guarda o actualiza un lote en el archivo JSON."""
    processed_batch = process_batch_data(batch_data)
    
    batches = []
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                content = json.load(f)
                batches = content.get("batches", [])
            except json.JSONDecodeError:
                batches = []

    # Insertar o actualizar si el ID ya existe
    updated = False
    for i, b in enumerate(batches):
        if b["id"] == processed_batch["id"]:
            batches[i] = processed_batch
            updated = True
            break
            
    if not updated:
        batches.append(processed_batch)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"batches": batches}, f, ensure_ascii=False, indent=2)

    print(f"✅ Lote '{processed_batch['id']}' procesado y guardado en {filepath}")
    print(f"   - OG Medida: {processed_batch['wort']['gravity_sg']} @ {processed_batch['wort']['gravity_temp_c']}°C ➔ Corregida: {processed_batch['analytics']['og_corrected']}")
    print(f"   - FG Medida: {processed_batch['final_beer']['final_gravity_sg']} @ {processed_batch['final_beer']['gravity_temp_c']}°C ➔ Corregida: {processed_batch['analytics']['fg_corrected']}")
    print(f"   - Alcohol (% ABV): {processed_batch['analytics']['abv_pct']}%")
    print(f"   - Atenuación Aparente: {processed_batch['analytics']['apparent_attenuation_pct']}%\n")

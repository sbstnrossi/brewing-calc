#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 16:29:34 2026

@author: sebastian
"""

import copy
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# Intento de importación defensiva por si la librería no está instalada en un entorno local ligero
try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False


class RecipeManager:
    def __init__(
        self,
        recipes_file: str = "recipes.json",
        malts_file: str = "malts.json",
        acids_file: str = "acids.json"
    ):
        self.recipes_file = recipes_file
        self.malts_file = malts_file
        self.acids_file = acids_file
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
                self.acids_ref = self.db.collection("acids")
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
                
                # Caso 1: El JSON es directamente una lista [...]
                if isinstance(data, list):
                    return {item.get("id", str(i)): item for i, item in enumerate(data)}
                
                # Caso 2: El JSON es un diccionario
                if isinstance(data, dict):
                    # Si viene envuelto en una clave como {"recipes": [...]} o {"malts": [...]}
                    for key, val in data.items():
                        if isinstance(val, list):
                            return {item.get("id", str(i)): item for i, item in enumerate(val)}
                    
                    # Si ya es un mapa directo {"id_1": {...}, "id_2": {...}}
                    return data
    
                return {}
            except json.JSONDecodeError:
                return {}

    def _write_json(self, filepath: str, data: Dict) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(list(data.values()), f, indent=4, ensure_ascii=False)

    # --- Operaciones de Maltas (Híbridas) ---
    def get_malt(self, malt_id: str) -> Optional[Dict]:
        """Obtiene una malta por su ID desde Firestore o JSON local."""
        if self.use_firestore:
            try:
                doc = self.malts_ref.document(malt_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                print(f"⚠️ Error al consultar Firestore (malts): {e}. Recurriendo a JSON local...")

        # Fallback a JSON local
        malts = self._read_json(self.malts_file)
        return malts.get(malt_id)

    def get_all_malts(self) -> Dict[str, Dict]:
        """Obtiene el catálogo completo de maltas desde Firestore o JSON local."""
        if self.use_firestore:
            try:
                docs = self.malts_ref.stream()
                malts = {doc.id: doc.to_dict() for doc in docs}
                if malts:
                    return malts
            except Exception as e:
                print(f"⚠️ Error al obtener lista de maltas desde Firestore: {e}. Recurriendo a JSON local...")

        return self._read_json(self.malts_file)

    def save_malt(self, malt_id: str, malt_data: Dict) -> None:
        """Guarda o actualiza una malta en Firestore y/o en el JSON local."""
        malt_data["id"] = malt_id
        if self.use_firestore:
            try:
                self.malts_ref.document(malt_id).set(malt_data, merge=True)
                print(f"✅ Malta '{malt_id}' guardada en Firestore.")
            except Exception as e:
                print(f"⚠️ Error guardando malta en Firestore: {e}. Guardando localmente...")

        malts = self._read_json(self.malts_file)
        malts[malt_id] = malt_data
        self._write_json(self.malts_file, malts)

    # --- Operaciones de Ácidos (Híbridas / Opcional) ---
    def get_acid(self, acid_id: Optional[str]) -> Optional[Dict]:
        """Obtiene datos técnicos de un ácido desde Firestore o JSON local."""
        if not acid_id:
            return None

        if self.use_firestore:
            try:
                doc = self.acids_ref.document(acid_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                print(f"⚠️ Error al consultar Firestore (acids): {e}. Recurriendo a JSON local...")

        acids = self._read_json(self.acids_file)
        return acids.get(acid_id)

    # --- Operaciones de Recetas (Híbridas) ---
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

        if "grain_bill" in scaled_recipe:
            scaled_recipe["grain_bill"] = [
                {**item, "weight_kg": round(item.get("weight_kg", 0) * scale_factor, 3)}
                for item in scaled_recipe["grain_bill"]
            ]

        if "hops" in scaled_recipe:
            scaled_recipe["hops"] = [
                {**item, "amount_g": round(item.get("amount_g", 0) * scale_factor, 2)}
                for item in scaled_recipe["hops"]
            ]

        return scaled_recipe
    
    def get_recipe_grain_bill(self, recipe: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Recibe una receta y resuelve los datos técnicos de cada malta
        (di_ph y buffering) consultando Firestore o malts.json de forma transparente.
        """

        resolved_grain_bill = []
        items = recipe.get("grain_bill") or recipe.get("fermentables", [])

        for item in items:
            malt_id = item.get("malt_id") or item.get("id")
            weight = item.get("weight_kg") or item.get("amount_kg", 0.0)

            if not malt_id:
                continue

            malt_data = self.get_malt(malt_id)
            if not malt_data:
                raise KeyError(f"La malta '{malt_id}' no está registrada en Firestore ni en '{self.malts_file}'")

            resolved_grain_bill.append({
                "name": malt_data.get("name", malt_id),
                "weight_kg": weight,
                "di_ph": malt_data.get("di_ph"),
                "buffering": malt_data.get("buffering")
            })

        return resolved_grain_bill
    
    def get_recipe_details(
        self, 
        recipe_id: str,
        target_volume_l: Optional[float] = None
    ) -> Dict[str, Any]:
        """Obtiene la configuración completa de la receta resolviendo granos y datos de agua."""
        recipe = self.get_recipe(recipe_id)
        if not recipe:
            raise ValueError(f"La receta '{recipe_id}' no fue encontrada.")
        
        if target_volume_l is not None and target_volume_l > 0:
            recipe = self.scale_recipe(recipe_id, target_volume_l)

        water_settings = recipe.get("water_settings", {})
        acid_selected = water_settings.get("acid_selected") if isinstance(water_settings, dict) else None

        return {
            "recipe_raw": recipe,
            "resolved_grains": self.get_recipe_grain_bill(recipe),
            "acid_info": self.get_acid(acid_selected)
        }

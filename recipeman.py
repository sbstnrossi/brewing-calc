#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 16:29:34 2026

@author: sebastian
"""

import copy
import json
from pathlib import Path
from typing import Dict, List, Any

def scale_recipe(recipe: Dict[str, Any], target_volume_l: float) -> Dict[str, Any]:
    """
    Función auxiliar para escalar proporcionalmente una receta al nuevo volumen final.
    """
    scaled_recipe = copy.deepcopy(recipe)
    current_batch_vol = scaled_recipe["volumes"]["batch_volume_liters"]

    if current_batch_vol <= 0:
        return scaled_recipe

    scaling_factor = target_volume_l / current_batch_vol

    # Escalado de volúmenes
    scaled_recipe["volumes"]["mash_liters"] = round(
        scaled_recipe["volumes"]["mash_liters"] * scaling_factor, 2
    )
    scaled_recipe["volumes"]["batch_volume_liters"] = round(target_volume_l, 2)

    # Escalado de granos
    for grain in scaled_recipe.get("grain_bill", []):
        grain["weight_kg"] = round(grain["weight_kg"] * scaling_factor, 3)

    # Escalado de lúpulos
    for hop in scaled_recipe.get("hop_bill", []):
        hop["weight_g"] = round(hop["weight_g"] * scaling_factor, 2)

    return scaled_recipe

class RecipeManager:
    """Carga bases de datos JSON y resuelve recetas para el cálculo de agua."""

    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.malts_db = self._load_json("malts.json")
        self.recipes_db = self._load_json("recipes.json")
        self.acids_db = self._load_json("acidtable.json")

    def _load_json(self, filename: str) -> Dict[str, Any]:
        path = self.data_dir / filename
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_recipe_grain_bill(self, recipe: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Recibe una receta y resuelve los datos técnicos de cada malta
        (di_ph y buffering) desde la base de datos malts.json.
        """

        resolved_grain_bill = []
        for item in recipe["grain_bill"]:
            malt_id = item["malt_id"]
            weight = item["weight_kg"]

            if malt_id not in self.malts_db:
                raise KeyError(f"La malta '{malt_id}' no está registrada en malts.json")

            malt_data = self.malts_db[malt_id]
            resolved_grain_bill.append({
                "name": malt_data["name"],
                "weight_kg": weight,
                "di_ph": malt_data["di_ph"],
                "buffering": malt_data["buffering"]
            })

        return resolved_grain_bill

    def get_recipe_details(
            self, 
            recipe_id: str,
            target_volume_l: [float] = None
        ) -> Dict[str, Any]:
        """Obtiene la configuración completa de la receta."""
        recipes = self.recipes_db.get("recipes", [])
        recipe = next((r for r in recipes if r["id"] == recipe_id), None)
        if not recipe:
            raise ValueError(f"La receta '{recipe_id}' no fue encontrada.")
        
        if target_volume_l is not None and target_volume_l > 0:
            recipe = scale_recipe(recipe, target_volume_l)
        
        return {
            "recipe_raw": recipe,
            "resolved_grains": self.get_recipe_grain_bill(recipe),
            "acid_info": self.acids_db.get(recipe["water_settings"]["acid_selected"])
        }
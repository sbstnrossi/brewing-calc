#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 16:29:34 2026

@author: sebastian
"""

import json
from pathlib import Path
from typing import Dict, List, Any

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

    def get_recipe_grain_bill(self, recipe_id: str) -> List[Dict[str, Any]]:
        """
        Busca una receta por su 'id' y resuelve los datos técnicos de cada malta
        (di_ph y buffering) desde la base de datos malts.json.
        """
        recipes = self.recipes_db.get("recipes", [])
        recipe = next((r for r in recipes if r["id"] == recipe_id), None)
        
        if not recipe:
            raise ValueError(f"La receta '{recipe_id}' no existe en recipes.json")

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

    def get_recipe_details(self, recipe_id: str) -> Dict[str, Any]:
        """Obtiene la configuración completa de la receta."""
        recipes = self.recipes_db.get("recipes", [])
        recipe = next((r for r in recipes if r["id"] == recipe_id), None)
        if not recipe:
            raise ValueError(f"La receta '{recipe_id}' no fue encontrada.")
        
        return {
            "recipe_raw": recipe,
            "resolved_grains": self.get_recipe_grain_bill(recipe_id),
            "acid_info": self.acids_db.get(recipe["water_settings"]["acid_selected"])
        }
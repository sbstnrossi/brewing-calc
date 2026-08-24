#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 15:09:43 2026

@author: sebastian
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

class BruDataManager:
    """Clase encargada de cargar y consultar las tablas de búsqueda (Lookups)."""

    def __init__(self, config_dir: str = "."):
        self.config_path = Path(config_dir)
        self.acidtable: Dict[str, Any] = self._load_json("acidtable.json")
        self.profiles: Dict[str, Any] = self._load_json("profiles.json")
        self.sprgvaritable: Dict[str, Any] = self._load_json("sprgvaritable.json")

    def _load_json(self, filename: str) -> Dict[str, Any]:
        file_path = self.config_path / filename
        if not file_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo de configuración: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # --- Reemplazo de VLOOKUP para acidtable ---
    def get_acid_info(self, acid_name: str) -> Optional[Dict[str, Any]]:
        """Equivalente a =VLOOKUP(acid_name, acidtable, col_idx, FALSE)"""
        acid = self.acidtable.get(acid_name)
        if not acid:
            print(f"Advertencia: El ácido '{acid_name}' no existe en la tabla.")
        return acid

    # --- Reemplazo de VLOOKUP para profiles ---
    def get_target_profile(self, profile_name: str) -> Optional[Dict[str, float]]:
        """Obtiene las concentraciones objetivo de iones para un perfil dado."""
        profile = self.profiles.get(profile_name)
        if not profile:
            print(f"Advertencia: El perfil '{profile_name}' no se encuentra.")
        return profile

    # --- Reemplazo de VLOOKUP para maltas/factores de grano ---
    def get_grain_factor(self, grain_type: str) -> Dict[str, float]:
        """Obtiene el pH en agua destilada y la capacidad de amortiguación según el tipo de malta."""
        types = self.sprgvaritable.get("grain_types", {})
        return types.get(grain_type, types.get("Base"))  # Retorna 'Base' por defecto
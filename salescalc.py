#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 15:25:06 2026

@author: sebastian
"""

from typing import Dict, Any, Optional
import numpy as np
from scipy.optimize import nnls

# Base de datos de sales y sus aportes iónicos (mg de ión por gramo de sal)
SALTS_DATABASE: Dict[str, Dict[str, Any]] = {
    "CaSO4":  {"name": "Sulfato de Calcio (Yeso)",            "ca": 232.8,  "so4":  557.9},
    "CaCl2":  {"name": "Cloruro de Calcio (Dihidratado)",     "ca": 272.6,   "cl":  482.3},
  # "MgSO4":  {"name": "Sulfato de Magnesio (Epsom)",         "mg": 98.6,   "so4":  389.7},
    "MgCl2":  {"name": "Cloruro de Magnesio (Hexahidratado)", "mg": 119.6,   "cl":  348.8},
    "NaCl":   {"name": "Cloruro de Sodio (Sal de mesa)",      "na": 393.4,   "cl":  606.6},
  # "NaHCO3": {"name": "Bicarbonato de Sodio",                "na": 273.7, "hco3":  726.3},
  # "CaCO3":  {"name": "Carbonato de Calcio (Tiza)",          "ca": 400.4, "hco3": 1219.3},
  # "CaOH2":  {"name": "Hidróxido de Calcio (Cal)",           "ca": 540.9, "hco3": 1647.0}
}

IONS = ["ca", "mg", "na", "so4", "cl", "hco3"]


def calculate_resulting_profile(
    source_profile: Dict[str, float], 
    salts_grams: Dict[str, float], 
    volume_liters: float
) -> Dict[str, float]:
    """
    Calcula el perfil iónico resultante (en ppm) tras añadir adiciones de sales en gramos.
    """
    final_profile = {ion: source_profile.get(ion, 0.0) for ion in IONS}

    for salt_key, grams in salts_grams.items():
        if grams <= 0 or salt_key not in SALTS_DATABASE:
            continue
        salt_data = SALTS_DATABASE[salt_key]
        for ion in IONS:
            yield_mg_per_g = salt_data.get(ion, 0.0)
            final_profile[ion] += (grams * yield_mg_per_g) / volume_liters

    return {ion: round(val, 2) for ion, val in final_profile.items()}


def solve_salt_additions(
    source_profile: Dict[str, float],
    target_profile: Dict[str, float],
    volume_liters: float,
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Calcula la cantidad óptima en gramos de cada sal para alcanzar el perfil objetivo 
    minimizando el error mediante mínimos cuadrados no negativos (NNLS).
    """
    if weights is None:
        # Mayor peso en SO4 y Cl para mantener la relación de perfil de sabor (Sulfato/Cloruro)
        weights = {"ca": 1.0, "mg": 0.8, "na": 0.8, "so4": 1.5, "cl": 1.5, "hco3": 0.5}

    salts_list = list(SALTS_DATABASE.keys())
    num_ions = len(IONS)
    num_salts = len(salts_list)

    # Construir matriz A de aportes iónicos (ppm/gramo en el volumen especificado)
    A = np.zeros((num_ions, num_salts))
    for j, salt_key in enumerate(salts_list):
        salt_data = SALTS_DATABASE[salt_key]
        for i, ion in enumerate(IONS):
            A[i, j] = salt_data.get(ion, 0.0) / volume_liters

    # Vector b con el incremento iónico requerido
    b = np.array([
        max(0.0, target_profile.get(ion, 0.0) - source_profile.get(ion, 0.0)) 
        for ion in IONS
    ])

    # Ponderación por importancia relativa de cada ión
    W = np.diag([weights.get(ion, 1.0) for ion in IONS])
    A_weighted = W @ A
    b_weighted = W @ b

    # Resolver A * x = b sujeto a x >= 0
    x_opt, _ = nnls(A_weighted, b_weighted)

    # Formatear la receta de sales resultante
    salts_recommended = {
        salts_list[j]: round(float(x_opt[j]), 3) 
        for j in range(num_salts) 
        if x_opt[j] > 0.001
    }

    resulting_profile = calculate_resulting_profile(source_profile, salts_recommended, volume_liters)

    return {
        "salts_grams": salts_recommended,
        "resulting_profile": resulting_profile,
        "target_profile": target_profile,
        "so4_cl_ratio": round(
            resulting_profile["so4"] / max(resulting_profile["cl"], 0.1), 2
        )
    }
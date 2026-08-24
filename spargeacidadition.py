#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 20:14:22 2026

@author: seba
"""

from typing import Dict, Any

def calculate_sparge_acid_addition(
    sparge_volume_l: float,
    water_profile: Dict[str, float], # {"hco3": ppm, "co3": ppm (opcional)}
    target_sparge_ph: float = 5.50,
    acid_info: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Calcula los mL de ácido necesarios para ajustar el pH del agua de lavado (sparge).
    
    Parameters:
    -----------
    sparge_volume_l : volumen de agua de lavado en litros.
    water_profile   : perfil de agua de lavado (concentración de bicarbonato y carbonato en ppm).
    target_sparge_ph: pH objetivo para el agua de lavado (por defecto 5.50).
    acid_info       : diccionario con datos del ácido desde acidtable.json.
    """
    if acid_info is None:
        raise ValueError("Debe proporcionar la información del ácido (acid_info).")

    # 1. Alcalinidad inicial en mEq/L
    hco3_ppm = water_profile.get("hco3", 0.0)
    co3_ppm = water_profile.get("co3", 0.0)

    hco3_meq_l = hco3_ppm / 61.0
    co3_meq_l = 2.0 * (co3_ppm / 60.0)
    total_alkalinity_meq_l = hco3_meq_l + co3_meq_l

    # 2. Alcalinidad neutralizada al pH objetivo (pKa1 ácido carbónico ≈ 6.35)
    pka1_carbonic = 6.35
    fraction_neutralized = 1.0 / (1.0 + (10 ** (target_sparge_ph - pka1_carbonic)))
    
    net_meq_required = sparge_volume_l * total_alkalinity_meq_l * fraction_neutralized

    # Si el agua casi no tiene alcalinidad (ej. RO water pura), el ácido necesario es 0
    if net_meq_required <= 0.001:
        return {
            "sparge_acid_volume_ml": 0.0,
            "net_meq_required": 0.0,
            "initial_alkalinity_ppm_hco3": hco3_ppm,
            "note": "El agua de lavado tiene una alcalinidad tan baja que no requiere ácido."
        }

    # 3. Conversión de mEq a mL del ácido seleccionado
    molarity = acid_info.get("molarity_mol_l", 11.6)
    pka_acid = acid_info.get("pka", 3.86)
    
    if "Fosfórico" in acid_info.get("name", ""):
        protons_per_molecule = 1.0 + (1.0 / (1.0 + (10 ** (7.20 - target_sparge_ph))))
    else:
        protons_per_molecule = 1.0 / (1.0 + (10 ** (pka_acid - target_sparge_ph)))

    meq_per_ml = molarity * protons_per_molecule
    acid_volume_ml = net_meq_required / meq_per_ml

    return {
        "sparge_acid_volume_ml": round(acid_volume_ml, 3),
        "net_meq_required": round(net_meq_required, 2),
        "initial_alkalinity_ppm_hco3": hco3_ppm,
        "target_sparge_ph": target_sparge_ph,
        "acid_used": acid_info.get("name", "Ácido")
    }
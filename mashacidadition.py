#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 16:01:24 2026

@author: sebastian
"""

from typing import Dict, List, Any

def estimate_unadjusted_mash_ph(
    mash_volume_l: float,
    water_profile: Dict[str, float],
    grain_bill: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Estima el pH natural del macerado (sin agregar ácido ni sales correctoras).
    
    Retorna el pH estimado y el desglose del impacto del agua sobre la malta.
    """
    # -------------------------------------------------------------------------
    # 1. Capacidad amortiguadora total (mEq / pH) y pH ponderado en agua destilada
    # -------------------------------------------------------------------------
    total_buffering = sum(
        g["weight_kg"] * g.get("buffering", 35.0) 
        for g in grain_bill
    )
    
    if total_buffering == 0:
        raise ValueError("La carga de granos no puede estar vacía o tener peso cero.")

    weighted_di_ph = sum(
        g["weight_kg"] * g.get("buffering", 35.0) * g.get("di_ph", 5.70)
        for g in grain_bill
    ) / total_buffering

    # -------------------------------------------------------------------------
    # 2. Reacción ácida de Calcio y Magnesio (Regla de Kolbach)
    # -------------------------------------------------------------------------
    ca_meq_l = water_profile.get("ca", 0.0) / 20.05
    mg_meq_l = water_profile.get("mg", 0.0) / 12.15
    
    meq_h_released_by_minerals = mash_volume_l * ((ca_meq_l / 3.5) + (mg_meq_l / 7.0))

    # -------------------------------------------------------------------------
    # 3. Iteración de equilibrio para la neutralización de Bicarbonatos (HCO3-)
    # -------------------------------------------------------------------------
    hco3_ppm = water_profile.get("hco3", 0.0)
    hco3_meq_l = hco3_ppm / 61.0
    
    pka1_carbonic = 6.35
    ph_est = weighted_di_ph  # Valor inicial de iteración

    # Se itera 5 veces para converger en el valor exacto de disociación a ese pH
    for _ in range(5):
        fraction_neutralized = 1.0 / (1.0 + (10 ** (ph_est - pka1_carbonic)))
        meq_alkalinity = mash_volume_l * hco3_meq_l * fraction_neutralized
        
        # Balance neto de protones afectando a la malta
        net_meq_shift = meq_alkalinity - meq_h_released_by_minerals
        
        # Actualizar pH estimado
        ph_est = weighted_di_ph + (net_meq_shift / total_buffering)

    # Impactos individuales para análisis/diagnóstico
    alkalinity_impact = (mash_volume_l * hco3_meq_l * (1.0 / (1.0 + (10 ** (ph_est - pka1_carbonic))))) / total_buffering
    minerals_impact = -meq_h_released_by_minerals / total_buffering

    return {
        "estimated_unadjusted_ph": round(ph_est, 2),
        "weighted_di_ph": round(weighted_di_ph, 2),
        "total_buffering_capacity": round(total_buffering, 2),
        "alkalinity_ph_shift": round(alkalinity_impact, 2),
        "minerals_ph_shift": round(minerals_impact, 2)
    }

def calculate_mash_acid_addition(
    mash_volume_l: float,
    target_ph: float,
    water_profile: Dict[str, float],  # {"hco3": ppm, "ca": ppm, "mg": ppm}
    grain_bill: List[Dict[str, Any]], # [{"weight_kg": 4.0, "di_ph": 5.70, "buffering": 35.0}, ...]
    acid_info: Dict[str, Any]         # Entrada de acidtable.json (ej. Lactic 88% o Phosphoric 85%)
) -> Dict[str, float]:
    """
    Calcula los mL de ácido necesarios para alcanzar el pH de maceración objetivo.
    
    Retorna un diccionario con el desglose de mEq y el volumen final en mL.
    """
    # -------------------------------------------------------------------------
    # 1. Protones necesarios para neutralizar Bicarbonatos (HCO3-)
    # -------------------------------------------------------------------------
    hco3_ppm = water_profile.get("hco3", 0.0)
    hco3_meq_l = hco3_ppm / 61.0  # mEq/L de HCO3-

    # Fracción de HCO3- que se convierte en H2CO3 al bajar al pH objetivo (pKa1 ≈ 6.35)
    pka1_carbonic = 6.35
    fraction_neutralized = 1.0 / (1.0 + (10 ** (target_ph - pka1_carbonic)))
    
    meq_alkalinity_needed = mash_volume_l * hco3_meq_l * fraction_neutralized

    # -------------------------------------------------------------------------
    # 2. Reacción de Calcio y Magnesio en el macerado (Regla de Kolbach)
    #    3.5 mEq de Ca2+ o 7.0 mEq de Mg2+ liberan 1 mEq de H+
    # -------------------------------------------------------------------------
    ca_meq_l = water_profile.get("ca", 0.0) / 20.05
    mg_meq_l = water_profile.get("mg", 0.0) / 12.15
    
    meq_h_released_by_minerals = mash_volume_l * ((ca_meq_l / 3.5) + (mg_meq_l / 7.0))

    # -------------------------------------------------------------------------
    # 3. Requerimiento/Aporte de protones de la Malta (Buffering)
    #    mEq = Peso (kg) * Capacidad Buffering (mEq/kg*pH) * (pH_di - pH_objetivo)
    # -------------------------------------------------------------------------
    meq_grain_total = 0.0
    for grain in grain_bill:
        weight = grain["weight_kg"]
        di_ph = grain.get("di_ph", 5.70)
        buffering = grain.get("buffering", 35.0)  # mEq/(kg * pH)
        
        # Si di_ph > target_ph, la malta requiere ácido.
        # Si di_ph < target_ph (ej. maltas tostadas), la malta aporta ácido.
        meq_grain_total += weight * buffering * (di_ph - target_ph)

    # -------------------------------------------------------------------------
    # 4. Balance Neto de mEq requeridos
    # -------------------------------------------------------------------------
    net_meq_required = meq_alkalinity_needed + meq_grain_total - meq_h_released_by_minerals

    if net_meq_required <= 0:
        return {
            "acid_volume_ml": 0.0,
            "net_meq_required": 0.0,
            "unadjusted_est_ph": round(target_ph + (abs(net_meq_required) / sum(g["weight_kg"] * g.get("buffering", 35.0) for g in grain_bill)), 2),
            "status": "No se requiere ácido. El pH ya se encuentra en o por debajo del objetivo."
        }

    # -------------------------------------------------------------------------
    # 5. Conversión de mEq a mL de Ácido según su concentración y Molaridad
    # -------------------------------------------------------------------------
    molarity = acid_info.get("molarity_mol_l", 11.6)
    pka_acid = acid_info.get("pka", 3.86)
    
    # Calcular protones activos por molécula a pH objetivo
    if "Fosfórico" in acid_info.get("name", ""):
        # El Ácido Fosfórico entrega ~1.02 protones a pH ~5.4 (pKa1=2.15, pKa2=7.20)
        protons_per_molecule = 1.0 + (1.0 / (1.0 + (10 ** (7.20 - target_ph))))
    elif "Láctico" in acid_info.get("name", ""):
        # Ácido Láctico (monoprático, pKa=3.86): casi 100% disociado a pH > 5.0
        protons_per_molecule = 1.0 / (1.0 + (10 ** (pka_acid - target_ph)))
    else:
        protons_per_molecule = -10.0

    meq_per_ml = molarity * protons_per_molecule  # mEq por mL de ácido líquido
    acid_volume_ml = net_meq_required / meq_per_ml

    return {
        "acid_volume_ml": round(acid_volume_ml, 2),
        "net_meq_required": round(net_meq_required, 2),
        "meq_alkalinity": round(meq_alkalinity_needed, 2),
        "meq_grain_buffering": round(meq_grain_total, 2),
        "meq_mineral_release": round(meq_h_released_by_minerals, 2),
        "acid_used": acid_info.get("name", "Desconocido")
    }
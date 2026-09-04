#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep  4 13:21:01 2026

@author: sebastian
"""

from typing import Dict, List, Any, Optional
import numpy as np
from scipy.optimize import nnls

# ==============================================================================
# PARAMETROS
# ==============================================================================

# parametros que necesitan ajuste con mediciones
RET_IN_GRAINS_PROP = 1.4
LOST_BOILING_PER_H = 3.25
DUST_IN_BOIL_PROP  = 0.5
DUST_IN_FERM_PROP  = 0.75

# ==============================================================================
# VOLUMENES DE AGUA
# ==============================================================================

def calculate_water_volumes(
    final_volume: float,
    mash_volume: float,
    grain_bill: List[Dict[str, Any]],
    sparge_volume_max = 0.0,
    preboil_volume_max = 0.0,
    minutes_boiling = 60.0
) -> Dict[str, Any]:
    """
    Estima agua retenida en los granos y evaporada en el hervor para 
    determinar el volumen de agua de enjuague y de dilución de mosto para
    el volumen final deseado
    """
    # -------------------------------------------------------------------------
    # 1. volumen retenido por los granos
    # -------------------------------------------------------------------------
    total_weight = sum(g["weight_kg"] for g in grain_bill)
    water_to_grist_ratio = mash_volume/total_weight
    
    if water_to_grist_ratio < 2.5 or water_to_grist_ratio > 5.0:
        raise ValueError("Revisar cantidades de maltas y volumen de macerado.")
        
    retained_in_grains = RET_IN_GRAINS_PROP * total_weight
    preboil_volume_from_mash = mash_volume - retained_in_grains
    
    # -------------------------------------------------------------------------
    # 2. volumen perdido en el fondo del fermentador
    # -------------------------------------------------------------------------
    dust_in_fermenter = DUST_IN_FERM_PROP * total_weight
    
    # -------------------------------------------------------------------------
    # 3. Calcula perdida por hervor y fondo de olla
    # -------------------------------------------------------------------------
    lost_in_boiling = LOST_BOILING_PER_H * minutes_boiling/60.0 + DUST_IN_BOIL_PROP * total_weight
    
    # -------------------------------------------------------------------------
    # 4. calcula total de agua necesaria y proporciones
    # -------------------------------------------------------------------------
    extra_needed = retained_in_grains + lost_in_boiling + dust_in_fermenter + final_volume - mash_volume
    preboil_volume = extra_needed + preboil_volume_from_mash
    
    sparge_volume = extra_needed
    dilute_volume = 0.0
    
    if preboil_volume_max > 0.0 and preboil_volume_max < preboil_volume:
        sparge_volume = preboil_volume_max - preboil_volume_from_mash
        dilute_volume = preboil_volume - preboil_volume_max
    
    if sparge_volume_max > 0.0 and sparge_volume_max < sparge_volume:
        dilute_volume += sparge_volume - sparge_volume_max
        sparge_volume = sparge_volume_max
        
    return {
        "sparge_volume": round(sparge_volume, 2),
        "dilute_volume": round(dilute_volume, 2)
    }

# ==============================================================================
# SALES
# ==============================================================================

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

# ==============================================================================
# ACIDOS
# ==============================================================================

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

# ==============================================================================
# 
# ==============================================================================


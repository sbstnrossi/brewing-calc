#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 16:01:24 2026

@author: sebastian
"""
# parametros que necesitan ajuste con mediciones
RET_IN_GRAINS_PROP = 1.4
LOST_BOILING_PER_H = 3.25
DUST_IN_BOIL_PROP  = 0.5
DUST_IN_FERM_PROP  = 0.75

from typing import Dict, List, Any

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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 27 12:07:21 2026

@author: sebastian
"""

import json
import os
from typing import Dict, Any

CALIBRATION_TEMP_C = 20.0  # Temperatura estándar de calibración del densímetro


def water_density(temp_c: float) -> float:
    """Calcula la densidad del agua pura en kg/m³ según la fórmula ASBC/Kell."""
    t = temp_c
    num = (
        999.83952
        + 16.945176 * t
        - 7.9870401e-3 * (t**2)
        - 46.170461e-6 * (t**3)
        + 105.56302e-9 * (t**4)
        - 280.54253e-12 * (t**5)
    )
    den = 1 + 16.897850e-3 * t
    return num / den


def correct_gravity(sg_measured: float, temp_c: float, calib_temp_c: float = CALIBRATION_TEMP_C) -> float:
    """
    Ajusta la densidad específica (SG) según la temperatura de lectura 
    con respecto a la temperatura de calibración del instrumento.
    """
    rho_calib = water_density(calib_temp_c)
    rho_measured = water_density(temp_c)
    sg_corrected = sg_measured * (rho_calib / rho_measured)
    return round(sg_corrected, 4)


def calculate_abv(og: float, fg: float) -> float:
    """Calcula el porcentaje de alcohol por volumen (% ABV)."""
    if og <= fg:
        return 0.0
    
    abw = (76.08 * (og - fg)) / (1.775 - og)
    abv = abw * (fg / 0.794)

    return round(abv, 2)


def process_batch_data(batch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aplica corrección por temperatura a OG y FG, y genera el bloque de análisis (ABV y Atenuación).
    """
    # Corrección de la Densidad Inicial (OG)
    raw_og = batch["wort"]["gravity_sg"]
    og_temp = batch["wort"]["gravity_temp_c"]
    og_corr = correct_gravity(raw_og, og_temp)
    batch["wort"]["corrected_gravity_sg"] = og_corr

    # Corrección de la Densidad Final (FG)
    raw_fg = batch["final_beer"]["final_gravity_sg"]
    fg_temp = batch["final_beer"]["gravity_temp_c"]
    fg_corr = correct_gravity(raw_fg, fg_temp)
    batch["final_beer"]["corrected_gravity_sg"] = fg_corr

    # Cálculo de métricas
    abv = calculate_abv(og_corr, fg_corr)
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


if __name__ == "__main__":
    # Ejemplo de lote tomado a 28°C (OG) y 16°C (FG)
    lote_ejemplo = {
        "id": "lote_2026_001",
        "brew_date": "2026-08-26",
        "recipe_id": "american_ipa_01",
        "target_batch_volume_l": 50.0,
        "mash": {
            "water_l": 55.0,
            "acid_added_ml": 12.5,
            "avg_temp_c": 65.5,
            "ph": 5.38,
            "est_post_mash_vol_l": 46.0
        },
        "sparge": {
            "water_l": 35.0,
            "acid_added_ml": 5.0
        },
        "boil": {
            "est_pre_boil_vol_l": 72.0,
            "est_post_boil_vol_l": 54.0,
            "dilution_water_added_l": 2.0
        },
        "wort": {
            "gravity_sg": 1.052,
            "gravity_temp_c": 28.0,  # Medido a 28°C (corrige a ~1.054)
            "ph": 5.20,
            "fermenter_vol_l": 51.0
        },
        "fermentation": {
            "days_fermenting": 10,
            "days_cold_crash": 3
        },
        "final_beer": {
            "final_gravity_sg": 1.011,
            "gravity_temp_c": 16.0,  # Medido a 16°C (corrige a ~1.010)
            "ph": 4.35,
            "packaged_vol_l": 48.0
        }
    }

    save_batch(lote_ejemplo)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 15:10:45 2026

@author: sebastian
"""

import brudataman as bdm
import recipeman as rm
import salescalc as sales
import mashacidadition as acidm
import spargeacidadition as acids
import watervolume as water
import htmlreport as report

RECIPE_ID = "scottish_export_01"

mash_vol         = 12.5
final_vol        = 13.0
preboil_max      = 19.0
target_mash_ph   = None
target_sparge_ph = 5.5
# Agua inicial (ej. Agua Ósmosis Inversa / Muy Blanda)
ro_water = {"ca": 1.0, "mg": 0.0, "na": 8.0, "so4": 2.0, "cl": 2.0, "hco3": 11.0}

# Instanciar el gestor de datos
db = bdm.BruDataManager()
recipes = rm.RecipeManager()

details = recipes.get_recipe_details(RECIPE_ID, target_volume_l=final_vol)

recipe_data = details["recipe_raw"]
grains = details["resolved_grains"]
acid = details["acid_info"]
target_profile_name = recipe_data["water_settings"]["target_profile_id"]
if target_mash_ph == None:
    target_mash_ph = recipe_data["target_mash_ph"]

# 0. calcula volumenes de agua
extra_water = water.calculate_water_volumes(final_vol, mash_vol, grains, preboil_volume_max=preboil_max)
sparge_vol = extra_water["sparge_volume"]
dilute_vol = extra_water["dilute_volume"]
tot_volume = mash_vol + sparge_vol + dilute_vol

print("--- ESTIMACIÓN DE VOLUMENES DE AGUA ---")
print(f"Volumen para enjuague: {sparge_vol} l")
print(f"Volumen para dilución: {dilute_vol} l\n")

# 1. Consulta de un Ácido para la acidificación del lavado
acid_selected = "Phosphoric 1M"
acid_data = db.get_acid_info(acid_selected)

if acid_data:
    conc = acid_data["concentration_pct"]
    molarity = acid_data["molarity_mol_l"]
    print(f"Ácido seleccionado: {acid_selected} | Conc: {conc}% | Molaridad: {molarity} M")

# 2. Consulta de un Perfil Deseado de Agua
target_water = db.get_target_profile(target_profile_name)

if target_water:
    print(f"Objetivo Ca2+: {target_water['ca']} ppm | SO4--: {target_water['so4']} ppm")

# Calcular la combinación de sales
receta_sales = sales.solve_salt_additions(
    source_profile=ro_water, 
    target_profile=target_water, 
    volume_liters=tot_volume
)

print("--- Sales recomendadas (gramos) ---")
for salt, g in receta_sales["salts_grams"].items():
    print(f"  {sales.SALTS_DATABASE[salt]['name']}: {g} g")

print("\n--- Comparación de Perfil ---")
print(f"Objetivo  : {receta_sales['target_profile']}")
adj_water = receta_sales['resulting_profile']
print(f"Resultante: {receta_sales['resulting_profile']}")
print(f"Relación SO4/Cl: {receta_sales['so4_cl_ratio']}")

estimate_mash_ph = acidm.estimate_unadjusted_mash_ph(
    mash_volume_l=mash_vol,
    water_profile=adj_water,
    grain_bill=grains
)

print("--- ESTIMACIÓN DE pH DE MACERACIÓN (SIN ÁCIDO) ---")
print(f"pH base de los granos (en agua destilada): {estimate_mash_ph['weighted_di_ph']}")
print(f"Aumento por Bicarbonatos: +{estimate_mash_ph['alkalinity_ph_shift']} pH")
print(f"Reducción por Ca/Mg:      {estimate_mash_ph['minerals_ph_shift']} pH")
print(f"-> pH NATURAL ESTIMADO:   {estimate_mash_ph['estimated_unadjusted_ph']}\n")

resultado_fosforico = acidm.calculate_mash_acid_addition(
    mash_volume_l= mash_vol,
    target_ph=target_mash_ph,
    water_profile=adj_water,
    grain_bill=grains,
    acid_info=acid_data
)

print("--- RESULTADO ÁCIDO FOSFÓRICO 1M ---")
print(f"Volumen necesario: {resultado_fosforico['acid_volume_ml']} mL")



res_ro = acids.calculate_sparge_acid_addition(
    sparge_volume_l=sparge_vol,
    water_profile=ro_water,
    target_sparge_ph=target_sparge_ph,
    acid_info=acid_data
)

print("--- AGUA DE LAVADO RO ---")
print(f"HCO3 inicial: {res_ro['initial_alkalinity_ppm_hco3']} ppm")
print(f"{acid_selected} necesario: {res_ro['sparge_acid_volume_ml']} mL\n")

report.generate_html_report(recipe_data, receta_sales, estimate_mash_ph, resultado_fosforico, res_ro, sparge_vol, dilute_vol, sales.SALTS_DATABASE)

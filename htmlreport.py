#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 24 19:56:09 2026

@author: seba
"""

import os
import webbrowser
from typing import Dict, Any

def generate_html_report(
    recipe: Dict[str, Any], 
    receta_calc: Dict[str, Any], 
    estimacion: Dict[str, Any], 
    resultado_fosforico: Dict[str, Any], 
    res_ro: Dict[str, Any], 
    mash_vol: float,
    sparge_vol: float, 
    dilute_vol: float, 
    sales_db: Dict[str, Any],
    output_filename: str = "reporte_receta.html"
) -> None:
    """
    Genera un informe HTML completo con volúmenes de agua, tratamiento de sales y estimación de pH.
    """
    
    # 1. Filas de Maltas
    grains_rows = "".join([
        f"<tr><td><strong>{g.get('malt_id')}</strong></td><td style='text-align: right;'>{g.get('weight_kg'):.3f} kg</td></tr>"
        for g in recipe.get("grain_bill", [])
    ])

    # 2. Filas de Lúpulos
    hops_rows = ""
    for h in recipe.get("hop_bill", []):
        use_type = h.get("use", "boil")
        time_text = f"{h.get('time_days')} días" if use_type == "dry_hop" else f"{h.get('time_min')} min"
        hops_rows += f"""
        <tr>
            <td><strong>{h.get('name')}</strong></td>
            <td>{use_type.upper()} @ {time_text}</td>
            <td style="text-align: right;">{h.get('alpha_acid_pct')}%</td>
            <td style="text-align: right;"><strong>{h.get('weight_g'):.2f} g</strong></td>
        </tr>
        """
        
    yeast_row = f"<tr><td><strong>{recipe.get('yeast')}</strong></td></tr>"

    # 3. Filas de Sales Recomendadas
    salts_rows = ""
    for salt_key, grams in receta_calc.get("salts_grams", {}).items():
        salt_name = sales_db.get(salt_key, {}).get("name", salt_key)
        salts_rows += f"""
        <tr>
            <td><strong>{salt_name}</strong></td>
            <td style="text-align: right;"><strong>{grams:.2f} g</strong></td>
        </tr>
        """
    
    # Extraer perfiles (si vienen como diccionarios o strings cargados)
    target_prof = receta_calc.get('target_profile', {})
    result_prof = receta_calc.get('resulting_profile', {})
    
    # Si vienen en formato dict, aseguramos obtener cada valor numérico:
    target_ca = target_prof.get('ca', 0) if isinstance(target_prof, dict) else 0
    target_mg = target_prof.get('mg', 0) if isinstance(target_prof, dict) else 0
    target_na = target_prof.get('na', 0) if isinstance(target_prof, dict) else 0
    target_so4 = target_prof.get('so4', 0) if isinstance(target_prof, dict) else 0
    target_cl = target_prof.get('cl', 0) if isinstance(target_prof, dict) else 0
    target_hco3 = target_prof.get('hco3', 0) if isinstance(target_prof, dict) else 0
    
    result_ca = result_prof.get('ca', 0) if isinstance(result_prof, dict) else 0
    result_mg = result_prof.get('mg', 0) if isinstance(result_prof, dict) else 0
    result_na = result_prof.get('na', 0) if isinstance(result_prof, dict) else 0
    result_so4 = result_prof.get('so4', 0) if isinstance(result_prof, dict) else 0
    result_cl = result_prof.get('cl', 0) if isinstance(result_prof, dict) else 0
    result_hco3 = result_prof.get('hco3', 0) if isinstance(result_prof, dict) else 0
    
    # Generar la tabla HTML
    water_profile_table = f"""
    <table>
        <thead>
            <tr>
                <th>Perfil (ppm)</th>
                <th style="text-align: right;">Ca⁺²</th>
                <th style="text-align: right;">Mg⁺²</th>
                <th style="text-align: right;">Na⁺</th>
                <th style="text-align: right;">SO₄⁻²</th>
                <th style="text-align: right;">Cl⁻</th>
                <th style="text-align: right;">HCO₃⁻</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Objetivo</strong></td>
                <td style="text-align: right;">{target_ca:.1f}</td>
                <td style="text-align: right;">{target_mg:.1f}</td>
                <td style="text-align: right;">{target_na:.1f}</td>
                <td style="text-align: right;">{target_so4:.1f}</td>
                <td style="text-align: right;">{target_cl:.1f}</td>
                <td style="text-align: right;">{target_hco3:.1f}</td>
            </tr>
            <tr>
                <td><strong>Resultante</strong></td>
                <td style="text-align: right;">{result_ca:.1f}</td>
                <td style="text-align: right;">{result_mg:.1f}</td>
                <td style="text-align: right;">{result_na:.1f}</td>
                <td style="text-align: right;">{result_so4:.1f}</td>
                <td style="text-align: right;">{result_cl:.1f}</td>
                <td style="text-align: right;">{result_hco3:.1f}</td>
            </tr>
        </tbody>
    </table>
    """

    acid_selected = recipe.get("water_settings", {}).get("acid_selected", "Ácido")

    # Documento HTML estructurado
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>{recipe.get('name', 'Receta')} - Hoja de Elaboración</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.5;
            color: #1f2937;
            max-width: 850px;
            margin: 20px auto;
            padding: 20px;
            background-color: #f3f4f6;
        }}
        .card {{
            background: #ffffff;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 20px;
        }}
        h1 {{ color: #d97706; margin-top: 0; border-bottom: 2px solid #fef3c7; padding-bottom: 8px; }}
        h2 {{ color: #374151; margin-top: 0; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; font-size: 1.2em; }}
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
        .grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }}
        .metric-box {{
            background: #f9fafb;
            padding: 12px;
            border-radius: 6px;
            border-left: 4px solid #d97706;
        }}
        .metric-box.highlight {{ border-left-color: #059669; background: #ecfdf5; }}
        .metric-box label {{ font-size: 0.8em; color: #6b7280; display: block; text-transform: uppercase; font-weight: bold; }}
        .metric-box span {{ font-size: 1.25em; font-weight: bold; color: #111827; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
        th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #e5e7eb; font-size: 0.95em; }}
        th {{ background-color: #f9fafb; font-weight: 600; color: #4b5563; }}
    </style>
</head>
<body>

    <!-- Encabezado de Receta -->
    <div class="card">
        <h1>🍺 {recipe.get('name')}</h1>
        <p><strong>Estilo:</strong> {recipe.get('style')} | <strong>pH Objetivo Macerado:</strong> {recipe.get('target_mash_ph')}</p>

        <div class="grid-3">
            <div class="metric-box">
                <label>Volumen Lote Final</label>
                <span>{recipe['volumes']['batch_volume_liters']} L</span>
            </div>
            <div class="metric-box">
                <label>Volumen Macerado</label>
                <span>{mash_vol} L</span>
            </div>
            <div class="metric-box">
                <label>Volumen Enjuague</label>
                <span>{sparge_vol:.2f} L</span>
            </div>
            <div class="metric-box">
                <label>Volumen Dilución</label>
                <span>{dilute_vol:.2f} L</span>
            </div>
        </div>
    </div>

    <!-- Ajuste de Agua y Sales -->
    <div class="card">
        <h2>🧂 Tratamiento de Agua y Sales</h2>
        <div class="grid-2">
            <div>
                <h3>Sales Recomendadas</h3>
                <table>
                    <thead>
                        <tr><th>Sal</th><th style="text-align: right;">Cantidad</th></tr>
                    </thead>
                    <tbody>
                        {salts_rows}
                    </tbody>
                </table>
            </div>
            <div>
                <h3>Perfil de Agua</h3>
                <div class="metric-box" style="margin-bottom: 12px;">
                    <label>Relación SO4 / Cl</label>
                    <span>{receta_calc.get('so4_cl_ratio')}</span>
                </div>
                {water_profile_table}
                <small style="display:block; color:#6b7280; margin-top:8px;">
                    <em>{target_prof.get('description', '') if isinstance(target_prof, dict) else ''}</em>
                </small>
            </div>
        </div>
    </div>

    <!-- Control de pH -->
    <div class="card">
        <h2>🧪 Estimación y Ajuste de pH</h2>
        <div class="grid-2">
            <div>
                <p><strong>pH Base Granos (DI):</strong> {estimacion.get('weighted_di_ph')}</p>
                <p><strong>Aumento por Bicarbonatos:</strong> +{estimacion.get('alkalinity_ph_shift')} pH</p>
                <p><strong>Reducción por Ca/Mg:</strong> {estimacion.get('minerals_ph_shift')} pH</p>
                <div class="metric-box">
                    <label>pH Natural Estimado (Sin Ácido)</label>
                    <span>{estimacion.get('estimated_unadjusted_ph')}</span>
                </div>
            </div>
            <div>
                <div class="metric-box highlight" style="margin-bottom: 12px;">
                    <label>Ácido Macerado (Ácido Fosfórico 1M)</label>
                    <span>{resultado_fosforico.get('acid_volume_ml')} mL</span>
                </div>
                <div class="metric-box highlight">
                    <label>Ácido Lavado RO ({acid_selected})</label>
                    <span>{res_ro.get('sparge_acid_volume_ml')} mL</span>
                    <small style="display:block; color:#6b7280; margin-top:3px;">HCO3 inicial: {res_ro.get('initial_alkalinity_ppm_hco3')} ppm</small>
                </div>
            </div>
        </div>
    </div>

    <!-- Ingredientes -->
    <div class="card">
        <h2>🌾 Granos y 🌿 Lúpulos</h2>
        <div class="grid-2">
            <div>
                <h3>Maltas</h3>
                <table><tbody>{grains_rows}</tbody></table>
            </div>
            <div>
                <h3>Lúpulos</h3>
                <table><tbody>{hops_rows}</tbody></table>
            </div>
            <div>
                <h3>Levadura</h3>
                <table><tbody>{yeast_row}</tbody></table>
            </div>
        </div>
    </div>

</body>
</html>
"""

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    file_path = os.path.abspath(output_filename)
    webbrowser.open(f"file://{file_path}")
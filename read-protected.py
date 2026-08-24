#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 16:13:14 2026

Try read protected xlsx and save unprotected

@author: sebastian
"""
import openpyxl

# 1. Cargar el archivo original manteniendo las fórmulas vivas
archivo_origen = "BrunWater1.25.xlsx"
wb = openpyxl.load_workbook(archivo_origen, data_only=False)

# 2. Iterar por cada una de las hojas del libro
for sheet in wb.worksheets:
    # Opción alternativa compatible con la estructura interna de openpyxl
    if hasattr(sheet, 'protection'):
        sheet.protection.sheet = False
        sheet.protection.enable = False # Dependiendo de la subversión
    else:
        # Forzar la desactivación directa de los componentes de bloqueo
        sheet.sheet_view.showGridLines = True # Asegura refresco visual
        # Si el objeto protection existe bajo el nombre 'protection':
        sheet.protection.disable() 

# 3. Guardar en un nuevo archivo limpio
archivo_destino = "BrunWater1.25_desbloqueado.xlsx"
wb.save(archivo_destino)

print(f"\n¡Proceso completado! Se ha generado '{archivo_destino}' con todas sus hojas editables.")



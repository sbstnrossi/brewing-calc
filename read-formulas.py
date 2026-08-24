#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 14:33:25 2026

@author: sebastian
"""

import openpyxl

# data_only=False mantiene la fórmula en lugar de calcular el valor
wb = openpyxl.load_workbook("BrunWater1.25_desbloqueado.xlsx", data_only=False)

ecuaciones = {}
for sheet in wb.worksheets:
    for row in sheet.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                ecuaciones[sheet.title+": "+cell.coordinate] = cell.value

# 'ecuaciones' ahora contiene {'C1': '=A1+B1', 'D1': '=PROMEDIO(A1:A10)', ...}
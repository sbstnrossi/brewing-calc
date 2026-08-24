#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 14:45:10 2026

@author: sebastian
"""

import math

class WaterReport:
    """Traducción de '1. Water Report Input'"""
    
    @staticmethod
    def cations_meq(ca: float, mg: float, na: float, k: float, fe: float = 0.0) -> float:
        # Celda I14: =(B6/20.05)+(B7/12.15)+(B8/23)+(B11/39.1)+(B12/28)
        return (ca / 20.05) + (mg / 12.15) + (na / 23.0) + (k / 39.1) + (fe / 28.0)

    @staticmethod
    def anions_meq(hco3: float, co3: float, so4: float, cl: float, no3: float = 0.0, no2: float = 0.0, f: float = 0.0) -> float:
        # Celda I15: (C6/61)+(C7/30)+(C8/48)+(C9/35.45)+(C10/62)+(C11/46)+(C12/19)
        return (hco3 / 61.0) + (co3 / 30.0) + (so4 / 48.0) + (cl / 35.45) + (no3 / 62.0) + (no2 / 46.0) + (f / 19.0)

    @staticmethod
    def alkalinity_as_caco3(hco3: float, co3: float) -> float:
        # Celda B15: 50 * ((HCO3/61) + 2*(CO3/60))
        return 50.0 * ((hco3 / 61.0) + (2.0 * (co3 / 60.0)))


class SpargeAcidification:
    """Traducción del equilibrio de carbonatos y pKa de '2. Sparge Acidification'"""
    
    @staticmethod
    def alpha_fractions(ph: float):
        # Celda T22: 10^(pH - 6.38) y T23: 10^(pH - 10.33)
        k1 = 10 ** (ph - 6.38)
        k2 = 10 ** (ph - 10.33)
        denom = 1.0 + k1 + (k1 * k2)  # Celda T24
        
        alpha_0 = 1.0 / denom        # Celda T25 (H2CO3)
        alpha_1 = k1 / denom         # Celda T26 (HCO3-)
        alpha_2 = (k1 * k2) / denom  # Celda T27 (CO3--)
        return alpha_0, alpha_1, alpha_2

    @staticmethod
    def acid_density_polynomial(acid_conc_pct: float) -> float:
        # Celda G41 (Polinomio de densidad según la concentración del ácido F10)
        x = acid_conc_pct
        return 1000.0 * (
            (-7.575e-10 * (x**4)) + 
            (7.01e-8 * (x**3)) + 
            (-9.254e-6 * (x**2)) + 
            (1.575e-3 * x) + 
            0.9979
        )


class GrainBill:
    """Traducción de '3. Grain Bill Input'"""
    
    @staticmethod
    def lovibond_to_srm(color_val: float, unit: str = "Lovibond") -> float:
        # Celda R6: IF(B20="Lovibond", E6, (0.375*E6)+0.561)
        if unit.lower() == "lovibond":
            return color_val
        return (0.375 * color_val) + 0.561

    @staticmethod
    def estimated_distilled_mash_ph(ph_shift_factor: float) -> float:
        # Celda F24: IFERROR(IF(5.76 - 0.17*I26 < 0, 0.1, 5.76 - 0.17*I26), 5)
        ph_est = 5.76 - (0.17 * ph_shift_factor)
        return max(ph_est, 0.1)
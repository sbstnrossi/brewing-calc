#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 27 12:07:21 2026

@author: sebastian
"""

from datetime import datetime, timezone
import json
import os
from typing import Dict, List, Optional, Any
import core

# Intento de importación defensiva por si la librería no está instalada en un entorno local ligero
try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False


class BatchManager:
    def __init__(self, lotes_file: str = "lotes.json"):
        self.lotes_file = lotes_file
        self.use_firestore = False
        self.db = None

        force_offline = os.getenv("FORCE_OFFLINE", "false").lower() in ("1", "true")

        if FIRESTORE_AVAILABLE and not force_offline:
            try:
                self.db = firestore.Client()
                self.lotes_ref = self.db.collection("lotes")
                self.use_firestore = True
                print("🌐 [BatchManager] Conectado a Firestore.")
            except Exception as e:
                print(f"💻 [BatchManager] Sin acceso a Firestore ({e}). Operando en modo local.")
                self.use_firestore = False
        else:
            print("💻 [BatchManager] Modo offline/local activo.")

    @staticmethod
    def calculate_hall_abv(og: float, fg: float) -> float:
        """Fórmula de Michael Hall (Zymurgy 1995) para el cálculo de % ABV."""
        if og <= fg or og <= 1.0:
            return 0.0
        abw = (76.08 * (og - fg)) / (1.775 - og)
        abv = abw * (fg / 0.794)
        return round(abv, 2)

    # --- Auxiliares de lectura/escritura local ---
    def _load_local_batches(self) -> Dict[str, Dict]:
        if not os.path.exists(self.lotes_file):
            return {}
        with open(self.lotes_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    return {item.get("id", f"lote_{i}"): item for i, item in enumerate(data)}
                return data
            except json.JSONDecodeError:
                return {}

    def _save_local_batches(self, batches: Dict[str, Dict]) -> None:
        with open(self.lotes_file, "w", encoding="utf-8") as f:
            json.dump(list(batches.values()), f, indent=4, ensure_ascii=False)

    # --- Operaciones principales ---
    def process_and_save_batch(self, batch_data: Dict) -> Dict:
        """Calcula el ABV y guarda los datos del lote en Firestore y/o localmente."""
        batch_id = batch_data.get("id")
        if not batch_id:
            raise ValueError("El lote debe contener un campo 'id'.")

        og = float(batch_data.get("og", 1.000))
        fg = float(batch_data.get("fg", 1.000))

        # Cálculo de ABV universal con la fórmula de Hall
        batch_data["abv"] = self.calculate_hall_abv(og, fg)
        batch_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # 1. Guardar en Firestore si está conectado
        if self.use_firestore:
            try:
                self.lotes_ref.document(batch_id).set(batch_data, merge=True)
                print(f"✅ Lote '{batch_id}' persistido en Firestore.")
            except Exception as e:
                print(f"⚠️ Fallo al guardar en Firestore ({e}). Guardando localmente...")

        # 2. Guardar localmente siempre
        batches = self._load_local_batches()
        batches[batch_id] = batch_data
        self._save_local_batches(batches)

        return batch_data

    def list_batches(self) -> List[Dict]:
        """Devuelve la lista completa de lotes registrados."""
        if self.use_firestore:
            try:
                docs = self.lotes_ref.stream()
                return [doc.to_dict() for doc in docs]
            except Exception as e:
                print(f"⚠️ Error leyendo Firestore: {e}. Leyendo archivo JSON local...")

        batches = self._load_local_batches()
        return list(batches.values())


def process_batch_data(batch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aplica corrección por temperatura a OG y FG, y genera el bloque de análisis (ABV y Atenuación).
    """
    # Corrección de la Densidad Inicial (OG)
    raw_og = batch["wort"]["gravity_sg"]
    og_temp = batch["wort"]["gravity_temp_c"]
    og_corr = core.correct_gravity(raw_og, og_temp)
    batch["wort"]["corrected_gravity_sg"] = og_corr

    # Corrección de la Densidad Final (FG)
    raw_fg = batch["final_beer"]["final_gravity_sg"]
    fg_temp = batch["final_beer"]["gravity_temp_c"]
    fg_corr = core.correct_gravity(raw_fg, fg_temp)
    batch["final_beer"]["corrected_gravity_sg"] = fg_corr

    # Cálculo de métricas
    abv = core.calculate_abv(og_corr, fg_corr)
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

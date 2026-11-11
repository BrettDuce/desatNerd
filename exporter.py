"""
CSV Export Engine for Oximetry & Hypoxic Burden Results
Handles:
  - Single file summary export
  - Detailed individual event morphology export
  - Batch summary CSV export with thread-safe append support
"""

import csv
import os
import re
from typing import Any, Dict, List
import pandas as pd


SUMMARY_FIELDNAMES = [
    "File_Name",
    "Device_Type",
    "Patient_ID",
    "Annotation_File",
    "Analysis_Window_Type",
    "Total_Duration_Hours",
    "Analysis_Duration_Hours",
    "SPT_Minutes",
    "TST_Minutes",
    "TRT_Minutes",
    "Sleep_Efficiency_pct",
    "First_Sleep_Epoch",
    "Last_Sleep_Epoch",
    "Sampling_Rate_Hz",
    "Baseline_SpO2",
    "Mean_SpO2",
    "Min_SpO2",
    "Desaturation_Threshold",
    "Desaturation_Count",
    "ODI_Selected",
    "ODI_3pct",
    "ODI_4pct",
    "Mean_Desat_Duration_sec",
    "Mean_Desat_Depth_pct",
    "Mean_Fall_Slope_pct_s",
    "Mean_Recovery_Slope_pct_s",
    "Mean_Desat_Area_pct_sec",
    "Mean_Desat_Area_pct_min",
    "T90_Percent",
    "T90_Minutes",
    "T88_Percent",
    "T88_Minutes",
    "T85_Percent",
    "T85_Minutes",
    "T80_Percent",
    "T80_Minutes",
    "Artifact_Percent",
    "Artifact_Minutes",
    "Azarbarzin_HB_pctmin_hr",
    "Azarbarzin_HB_Total_pctmin",
    "Azarbarzin_Method",
    "REDTA_pct_hours",
    "REDTA_Rate_pctmin_hr",
    "REDTA_Method",
    "Kulkas_DesSev_pctmin_hr",
    "Kulkas_RecSev_pctmin_hr",
    "Kulkas_Total_Severity_pctmin_hr",
    "Kulkas_Mean_Fall_Slope",
    "Kulkas_Mean_Recovery_Slope"
]

EVENT_FIELDNAMES = [
    "Event_ID",
    "Start_sec",
    "End_sec",
    "Duration_sec",
    "Fall_Duration_sec",
    "Recovery_Duration_sec",
    "Baseline_SpO2_pct",
    "Nadir_SpO2_pct",
    "Depth_pct",
    "Fall_Slope_pct_s",
    "Recovery_Slope_pct_s",
    "Fall_Area_pct_sec",
    "Fall_Area_pct_min",
    "Recovery_Area_pct_sec",
    "Recovery_Area_pct_min",
    "Total_Area_pct_sec",
    "Total_Area_pct_min",
    "Is_In_SPT",
    "Is_In_TST"
]


def _order_odi_columns(cols: List[str]) -> List[str]:
    """Keep all ODI_<x>pct columns together, sorted by threshold, directly after ODI_Selected."""
    pat = re.compile(r"^ODI_(\d+(?:p\d+)?)pct$")
    odi_cols = [c for c in cols if pat.match(c)]
    if not odi_cols:
        return cols
    odi_cols.sort(key=lambda c: float(pat.match(c).group(1).replace("p", ".")))
    rest = [c for c in cols if c not in odi_cols]
    pos = rest.index("ODI_Selected") + 1 if "ODI_Selected" in rest else len(rest)
    return rest[:pos] + odi_cols + rest[pos:]


def summary_fieldnames(result: Dict[str, Any]) -> List[str]:
    """Static summary columns plus one ODI column per extra threshold (e.g. ODI_2pct, ODI_5pct).
    All ODI columns are ordered by threshold after ODI_Selected."""
    from oximetry_engine import odi_key

    fields = list(SUMMARY_FIELDNAMES)
    fields += [odi_key(t) for t in result.get("ODI_Thresholds", []) if odi_key(t) not in fields]
    return _order_odi_columns(fields)


class OximetryExporter:
    @staticmethod
    def _build_summary_row(result: Dict[str, Any]) -> Dict[str, Any]:
        sleep_sum = result.get("Sleep_Summary", {})
        row = {}
        for k in summary_fieldnames(result):
            if k in result:
                row[k] = result[k]
            elif k in sleep_sum:
                row[k] = sleep_sum[k]
            else:
                row[k] = ""
        return row
    @staticmethod
    def export_single_summary(result: Dict[str, Any], output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        file_stem = os.path.splitext(result["File_Name"])[0]
        csv_path = os.path.join(output_dir, f"{file_stem}_oximetry_summary.csv")

        row = OximetryExporter._build_summary_row(result)
        df = pd.DataFrame([row])
        df.to_csv(csv_path, index=False)
        return csv_path

    @staticmethod
    def export_events_csv(result: Dict[str, Any], output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        file_stem = os.path.splitext(result["File_Name"])[0]
        csv_path = os.path.join(output_dir, f"{file_stem}_desaturation_events.csv")

        events = result.get("desaturation_events", [])
        rows = []
        for ev in events:
            rows.append({
                "Event_ID": ev.get("Event_ID"),
                "Start_sec": round(ev.get("Start", 0.0), 2),
                "End_sec": round(ev.get("End", 0.0), 2),
                "Duration_sec": round(ev.get("Duration", 0.0), 2),
                "Fall_Duration_sec": round(ev.get("Fall_Duration", 0.0), 2),
                "Recovery_Duration_sec": round(ev.get("Recovery_Duration", 0.0), 2),
                "Baseline_SpO2_pct": round(ev.get("Baseline", 0.0), 1),
                "Nadir_SpO2_pct": round(ev.get("Nadir", 0.0), 1),
                "Depth_pct": round(ev.get("Depth", 0.0), 1),
                "Fall_Slope_pct_s": round(ev.get("Fall_Slope", 0.0), 3),
                "Recovery_Slope_pct_s": round(ev.get("Recovery_Slope", 0.0), 3),
                "Fall_Area_pct_sec": round(ev.get("Fall_Area_sec", 0.0), 2),
                "Fall_Area_pct_min": round(ev.get("Fall_Area_min", 0.0), 4),
                "Recovery_Area_pct_sec": round(ev.get("Recovery_Area_sec", 0.0), 2),
                "Recovery_Area_pct_min": round(ev.get("Recovery_Area_min", 0.0), 4),
                "Total_Area_pct_sec": round(ev.get("Total_Area_sec", 0.0), 2),
                "Total_Area_pct_min": round(ev.get("Total_Area_min", 0.0), 4)
            })

        df = pd.DataFrame(rows)
        df.to_csv(csv_path, index=False)
        return csv_path

    @staticmethod
    def append_to_batch_summary(result: Dict[str, Any], output_dir: str, master_filename: str = "batch_oximetry_hypoxic_burden_summary.csv") -> str:
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, master_filename)
        file_exists = os.path.exists(csv_path)

        row = OximetryExporter._build_summary_row(result)
        fields = list(row.keys())

        if file_exists:
            with open(csv_path, newline='', encoding='utf-8') as f:
                existing_header = next(csv.reader(f), [])
            if existing_header and set(fields) - set(existing_header):
                # New ODI threshold columns (or an older file): rebuild with the union of
                # columns so earlier rows keep their values and new columns are blank for them.
                df_old = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
                merged = list(existing_header) + [c for c in fields if c not in existing_header]
                merged = _order_odi_columns(merged)
                df_new = pd.concat([df_old, pd.DataFrame([row])], ignore_index=True)
                df_new.reindex(columns=merged).to_csv(csv_path, index=False)
                return csv_path
            if existing_header:
                fields = existing_header

        with open(csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore', restval='')
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        return csv_path

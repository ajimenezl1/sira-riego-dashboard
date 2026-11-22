"""Series complementarias de la misma emisión que el semáforo."""
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
SEM = RAIZ / "reports/semaforo_c"
GEOS = RAIZ / "data/processed/modelo_a/geos/geos_nrt.csv"


@st.cache_data
def temperaturas(inicio, version):
    g = pd.read_csv(GEOS, usecols=["inicio", "fecha", "variable", "valor"])
    t = g[(g.inicio == int(inicio.replace("-", ""))) & g.variable.isin(["t2mmin", "t2mmax"])]
    return t.pivot_table(index="fecha", columns="variable", values="valor").reindex(columns=["t2mmin","t2mmax"]) - 273.15


@st.cache_data
def ndvi_emision(emision, version):
    import json
    if json.loads((SEM / "resumen.json").read_text(encoding="utf8"))["hoy"] != emision:
        return pd.DataFrame()
    with np.load(SEM / "diario.npz") as diario:
        ids = diario["pixel"][(diario["clase"] >= 0).any(axis=1)]
    p = pd.read_csv(SEM / "pixeles.csv.gz", usecols=lambda c: c == "pixel" or c.startswith("ndvi_h"))
    return p.loc[p.pixel.isin(ids)].reset_index(drop=True)

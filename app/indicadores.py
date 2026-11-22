"""Indicadores derivados del producto diario de Nataima."""
import math

import numpy as np
import pandas as pd


def delimitar_lotes(pixeles, lado):
    """Componentes de cuatro vecinos, de igual edad, con al menos 0,5 ha."""
    lat = np.asarray(pixeles["lat"])
    lon = np.asarray(pixeles["lon"])
    filas = np.rint((lat.max() - lat) * 110574 / lado).astype(int)
    cols = np.rint((lon - lon.min()) * 111320 * math.cos(math.radians(lat.mean())) / lado).astype(int)
    edades = pixeles["das_hoy"]
    pendientes = {(r, c): i for i, (r, c) in enumerate(zip(filas, cols))}
    if len(pendientes) != len(lat):
        raise ValueError("La resolución espacial del archivo no permite distinguir todas las celdas.")
    etiquetas = np.full(len(lat), "Área dispersa", dtype=object)
    numero = 0
    while pendientes:
        punto = next(iter(pendientes))
        inicial = pendientes.pop(punto)
        grupo = [inicial]
        cola = [punto]
        while cola:
            r, c = cola.pop()
            for vecino in ((r-1, c), (r+1, c), (r, c-1), (r, c+1)):
                i = pendientes.get(vecino)
                if i is not None and edades[i] == edades[inicial]:
                    grupo.append(pendientes.pop(vecino))
                    cola.append(vecino)
        if len(grupo) * lado**2 >= 5000:
            numero += 1
            etiquetas[grupo] = f"L-{numero:02d}"
    return etiquetas


def preparar(datos):
    p = datos["pixeles"]
    lado = datos["celda_m"]
    celdas = pd.DataFrame({"Latitud": p["lat"], "Longitud": p["lon"], "Edad inicial": p["das_hoy"],
                           "Lote": delimitar_lotes(p, lado)})
    celdas.index.name = "Celda"
    estados = np.array([list(d["clase"]) for d in datos["dias"]])
    deficit = np.array([d["deficit_mm"] for d in datos["dias"]], dtype=float)
    marcas = np.zeros(estados.shape, dtype=bool)
    for i, d in enumerate(datos["dias"]):
        marcas[i, d["marca"]] = True
    return celdas, estados, deficit, marcas


def resumen(fechas, estados, deficit, marcas, area):
    return pd.DataFrame({
        "Fecha": fechas, "Suficiente": (estados == "0").sum(axis=1) * area,
        "Vigilar": (estados == "1").sum(axis=1) * area, "Crítica": (estados == "2").sum(axis=1) * area,
        "Revisión NDMI": ((estados != "-") & marcas).sum(axis=1) * area,
        "Volumen neto (m³)": np.nansum(np.maximum(deficit, 0), axis=1) * area * 10,
    }).set_index("Fecha")

def ordenar_lotes(base, clases, deficit, fechas, h, area):
    """Orden operativo desde la fecha consultada bajo el escenario sin riego."""
    filas = []
    for nombre, grupo in base.groupby("Lote"):
        if nombre == "Área dispersa":
            continue
        ix = grupo.index.to_numpy()
        serie = clases[h:, ix]
        activos = (serie[0] != "-").sum()
        rojos = (serie[0] == "2").sum()
        dias_rojos = np.flatnonzero((serie == "2").any(axis=1))
        dia = int(dias_rojos[0]) if activos and len(dias_rojos) else None
        if not activos:
            accion = "Sin cultivo activo"
        elif rojos:
            accion = "Regar ahora"
        elif dia is not None:
            accion = "Programar riego"
        elif (serie[0] == "1").any():
            accion = "Vigilar humedad"
        else:
            accion = "Agua suficiente"
        edad = grupo["Edad inicial"].iloc[0] + h
        etapa = "Vegetativa" if edad <= 45 else "Reproductiva" if edad <= 82 else "Maduración" if edad <= 130 else "Fuera de etapa"
        filas.append({"Lote": nombre, "Acción": accion, "Área activa (ha)": activos*area,
                      "Etapa estimada": etapa if activos else "—",
                      "Próxima fecha crítica": fechas[h+dia] if dia is not None else "—",
                      "Crítica (%)": 100*rojos/activos if activos else 0,
                      "Crítica (ha)": rojos*area,
                      "Déficit (m³)": np.nansum(np.maximum(deficit[h, ix], 0))*area*10})
    orden = ["Regar ahora", "Programar riego", "Vigilar humedad", "Agua suficiente", "Sin cultivo activo"]
    tabla = pd.DataFrame(filas)
    if tabla.empty:
        return tabla
    tabla["orden"] = tabla["Acción"].map(orden.index)
    tabla = tabla.sort_values(["orden","Próxima fecha crítica","Crítica (%)","Déficit (m³)","Lote"],
                              ascending=[True,True,False,False,True]).drop(columns="orden").reset_index(drop=True)
    tabla.insert(0, "Prioridad", tabla.index+1)
    return tabla

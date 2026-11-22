"""Mapa Leaflet de la exportación diaria del semáforo C."""
import folium
from streamlit_folium import st_folium

TESSELAS = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
COLORES = {"Suficiente": "#2e9e5b", "Vigilar": "#f2c230", "Crítica": "#e04b4b"}
MORADO = "#8e44ad"


LEYENDAS = {
    "Semáforo": [(COLORES["Suficiente"], "Agua suficiente"), (COLORES["Vigilar"], "Vigilar humedad"),
                 (COLORES["Crítica"], "Regar ahora"), (MORADO, "Inspección por NDMI")],
    "Humedad": [("#146b85", "30 % o más"), ("#58b5b1", "27,1 % a menos de 30 %"), ("#d6eec5", "Menos de 27,1 %")],
    "Déficit": [("#ffedbb", "0 mm o menos"), ("#efa64a", "Más de 0 hasta 4,34 mm"), ("#a92e23", "Más de 4,34 mm")],
    "Alerta NDMI": [("#a9b5a7", "Sin alerta"), (MORADO, "Revisar en campo")],
}


def color_celda(estado, marca, capa, humedad, deficit):
    if capa == "Semáforo":
        return MORADO if marca else COLORES[estado]
    if capa == "Alerta NDMI":
        indice = int(marca)
    elif capa == "Humedad":
        indice = 0 if humedad >= 30 else 1 if humedad >= 27.1 else 2
    else:
        indice = 2 if deficit > 4.34 else 1 if deficit > 0 else 0
    return LEYENDAS[capa][indice][0]


def mapa_satelital(vista, predio, capa, clave, satelite=True):
    mapa = folium.Map(tiles=None, control_scale=True, prefer_canvas=True, max_zoom=20)
    if satelite:
        folium.TileLayer(tiles=TESSELAS, attr="Imágenes © Esri, Maxar, Earthstar Geographics y colaboradores",
                         name="Esri World Imagery", control=False, max_native_zoom=19, max_zoom=20).add_to(mapa)
    else:
        folium.TileLayer("OpenStreetMap", name="Mapa de calles", control=False).add_to(mapa)
    mapa.fit_bounds([[predio.Latitud.min(), predio.Longitud.min()],
                     [predio.Latitud.max(), predio.Longitud.max()]], padding=(18, 18), max_zoom=19)
    puntos = []
    for fila in vista.to_dict("records"):
        color = color_celda(fila["Estado"], fila["Alerta NDMI"], capa, fila["Humedad"], fila["Déficit"])
        puntos.append({"type": "Feature", "geometry": {"type": "Point",
                       "coordinates": [fila["Longitud"], fila["Latitud"]]},
                       "properties": {"Celda": fila["Celda"], "Lote": fila["Lote"], "Estado": fila["Estado"],
                                      "Humedad": f"{fila['Humedad']:.2f} %", "Déficit": f"{fila['Déficit']:.2f} mm",
                                      "NDMI": "Revisar en campo" if fila["Alerta NDMI"] else "Sin alerta",
                                      "color": color}})
    if puntos:
        folium.GeoJson({"type": "FeatureCollection", "features": puntos}, name=capa,
                       marker=folium.CircleMarker(radius=3, stroke=False, fill=True, fill_opacity=0.85),
                       style_function=lambda f: {"fillColor": f["properties"]["color"]},
                       tooltip=folium.GeoJsonTooltip(fields=["Celda", "Lote", "Estado", "Humedad", "Déficit", "NDMI"])
                       ).add_to(mapa)
    if capa == "Semáforo" and puntos:
        nombres = folium.FeatureGroup(name="Nombres de lotes").add_to(mapa)
        for nombre, grupo in vista.groupby("Lote"):
            if nombre == "Área dispersa":
                continue
            centro = grupo[["Latitud","Longitud"]].median()
            distancia = (grupo.Latitud-centro.Latitud)**2 + (grupo.Longitud-centro.Longitud)**2
            punto = grupo.loc[distancia.idxmin()]
            etiqueta = folium.DivIcon(html=f'<b style="color:white;font:700 12px sans-serif;white-space:nowrap;'
                                           f'text-shadow:0 1px 3px black,1px 0 2px black">{nombre}</b>',
                                      icon_size=(30,14),icon_anchor=(15,7))
            folium.Marker([punto.Latitud,punto.Longitud],icon=etiqueta,interactive=False).add_to(nombres)
    folium.LayerControl(collapsed=False).add_to(mapa)
    muestras = "".join(
        f'<div><i aria-hidden="true" style="display:inline-block;background:{color};width:11px;height:11px;'
        f'border:1px solid #555;border-radius:50%;margin-right:6px"></i>{etiqueta}</div>'
        for color, etiqueta in LEYENDAS[capa])
    mapa.get_root().html.add_child(folium.Element(
        '<aside style="position:fixed;left:10px;bottom:52px;z-index:1000;background:white;color:#18251c;'
        'padding:8px 12px;border-radius:6px;font:13px/1.5 sans-serif;box-shadow:0 1px 5px #0006;pointer-events:none">'
        f'<strong>Leyenda · {capa}</strong>{muestras}</aside>'))
    evento = st_folium(mapa, key=clave, height=510, use_container_width=True,
                       returned_objects=["last_object_clicked"])
    punto = (evento or {}).get("last_object_clicked")
    if punto:
        cerca = vista[(vista.Latitud.sub(punto["lat"]).abs() < 0.000045) &
                      (vista.Longitud.sub(punto["lng"]).abs() < 0.000045)]
        if len(cerca) == 1:
            return int(cerca.iloc[0].Celda)
    return None

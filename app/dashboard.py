import json
from datetime import datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from zoneinfo import ZoneInfo

from indicadores import ordenar_lotes, preparar, resumen
from mapa_satelital import mapa_satelital
from series_zona import GEOS, SEM, ndvi_emision, temperaturas

ARCHIVO = Path(__file__).parent / "datos" / "semaforo.json"
NOMBRES = {"0": "Suficiente", "1": "Vigilar", "2": "Crítica"}
ESCALA = alt.Scale(domain=list(NOMBRES.values()), range=["#298465", "#dda832", "#be4c38"])
PAGINAS = ["Panorama", "Mapa de humedad", "Plan de riego", "Clima", "Cultivo", "Datos y modelo"]


@st.cache_resource
def cargar(version):
    datos = json.loads(ARCHIVO.read_text(encoding="utf8"))
    return datos, *preparar(datos)


def numero(valor, decimales=1):
    return f"{valor:,.{decimales}f}".translate(str.maketrans(",.", ".,"))


def descargar(tabla, nombre):
    st.download_button("Descargar CSV", tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"sira_{nombre}.csv", mime="text/csv")


st.set_page_config(page_title="SIRA · Operación de riego", page_icon="🌾", layout="wide")
st.html(Path(__file__).with_suffix(".css"))
datos, base, clases, deficit, marcas = cargar(ARCHIVO.stat().st_mtime_ns)
dias = datos["dias"]
fechas = [d["fecha"] for d in dias]
area = datos["celda_m"]**2 / 10000
u = datos["umbrales"]
MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()


def fecha_corta(valor):
    anio, mes, dia = valor.split("-")
    return f"{int(dia)} {MESES[int(mes)-1]} {anio}"


def abrir(vista, area_elegida=None):
    st.session_state.seccion = vista
    if area_elegida:
        st.session_state.area_elegida = area_elegida


with st.sidebar:
    st.html('<div class="sira-brand"><div class="sira-mark" aria-hidden="true">≋</div><div><strong>SIRA</strong><small>Riego de arroz</small></div></div>')
    pagina = st.radio("Navegación", PAGINAS, key="seccion")
    st.divider()
    st.caption(f"Predio Nataima · El Espinal, Tolima  \nCorrida del {fecha_corta(datos['hoy'])}.")

if pagina == "Panorama":
    area_col = fecha_col = st.sidebar
else:
    area_col, fecha_col = st.columns(2)
lote = area_col.selectbox("Área de consulta", ["Toda la zona", *sorted(base.Lote.unique())], key="area_elegida")
hoy_local = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
fecha_inicial = min(max(hoy_local, fechas[0]), fechas[-1])
fecha = fecha_col.selectbox("Fecha de análisis", fechas, index=fechas.index(fecha_inicial),
                            format_func=fecha_corta, key="fecha_elegida")

h = fechas.index(fecha)
ids = base.index.to_numpy() if lote == "Toda la zona" else base.index[base.Lote == lote].to_numpy()
serie = resumen(fechas, clases[:, ids], deficit[:, ids], marcas[:, ids], area)
actual = serie.loc[fecha]
tabla = base.loc[ids].copy()
tabla["Estado"] = pd.Series(clases[h, ids], index=ids).map(NOMBRES)
tabla["Déficit"] = deficit[h, ids]
tabla["Humedad"] = u["verde_humedad_pct"] - tabla["Déficit"] / u["mm_por_punto"]
tabla["Alerta NDMI"] = marcas[h, ids]
tabla = tabla.dropna(subset=["Estado"]).reset_index()
if pagina != "Panorama":
    st.title(pagina)
    st.caption(f"Nataima · {lote} · {fecha_corta(fecha)}")


def evolucion():
    posiciones = sorted({h, min(h+7,len(fechas)-1), min(h+15,len(fechas)-1), len(fechas)-1})
    muestra = serie.iloc[posiciones][list(NOMBRES.values())]
    porcentajes = muestra.div(muestra.sum(axis=1).replace(0,np.nan),axis=0)*100
    colores = {"Crítica":"#c34940","Vigilar":"#e5a734","Suficiente":"#348562"}
    barras = []
    for f, valores in porcentajes.iterrows():
        segmentos = []
        for estado, color in colores.items():
            pct = valores[estado]
            if pd.notna(pct) and pct > 0:
                segmentos.append(f'<div title="{estado}: {numero(pct)} %" style="height:{pct}%;background:{color}">'
                                 f'{numero(pct,0)+"%" if pct>=18 else ""}</div>')
        barras.append(f'<div class="horizonte"><div class="barra">{"".join(segmentos)}</div>'
                      f'<small>{fecha_corta(f).rsplit(" ",1)[0]}</small></div>')
    leyenda = "".join(f'<span><i style="background:{color}"></i>{estado}</span>' for estado,color in colores.items())
    st.html('<div class="horizontes">'+"".join(barras)+'</div><div class="clave">'+leyenda+'</div>')


def proximos_dias():
    inicio = max(1, h)  # El acumulado de la emisión empieza en cero.
    ventana = dias[inicio:inicio+7]
    temps = temperaturas(datos["geos_inicio"], GEOS.stat().st_mtime_ns)
    filas = []
    for pos, d in enumerate(ventana, inicio):
        f = d["fecha"]
        fila = {"Fecha": fecha_corta(f), "Lluvia (mm)": round(d["lluvia_mm"]-dias[pos-1]["lluvia_mm"], 1),
                "ETo (mm)": round(d["eto_mm"]-dias[pos-1]["eto_mm"], 1)}
        for campo, etiqueta in [("t2mmin","Mín. (°C)"),("t2mmax","Máx. (°C)")]:
            fila[etiqueta] = temps.at[f,campo] if f in temps.index else None
        filas.append(fila)
    semana = pd.DataFrame(filas)
    st.markdown(f"#### Próximos {len(semana)} días" if len(semana)>1 else "#### Último día del pronóstico")
    tarjetas = []
    for d, fila in zip(ventana, filas):
        lluvia = fila["Lluvia (mm)"]
        dia = ["lun","mar","mié","jue","vie","sáb","dom"][pd.Timestamp(d["fecha"]).weekday()]
        fecha_dia = fecha_corta(d["fecha"]).rsplit(" ",1)[0]
        icono = "🌧️" if lluvia >= 1 else "🌦️" if lluvia > 0 else "☀️"
        temp = (f"{numero(fila['Mín. (°C)'],0)}–{numero(fila['Máx. (°C)'],0)} °C"
                if pd.notna(fila["Mín. (°C)"]) and pd.notna(fila["Máx. (°C)"]) else "Sin temperatura")
        tarjetas.append(f'<div class="dia"><small>{dia} {fecha_dia}</small><i aria-hidden="true">{icono}</i>'
                        f'<b>{numero(lluvia)} mm</b><small>ETo {numero(fila["ETo (mm)"])} mm</small><small>{temp}</small></div>')
    st.html('<div class="semana">' + "".join(tarjetas) + '</div>')
    st.caption(f"En el período se esperan {numero(semana['Lluvia (mm)'].sum())} mm de lluvia frente a "
               f"{numero(semana['ETo (mm)'].sum())} mm de demanda atmosférica (ETo).")


def analisis_zona():
    st.subheader(f"Análisis · {lote}")
    st.caption(fecha_corta(fecha))
    a, b = st.columns(2)
    a.metric("Área en arroz", f"{numero(len(tabla)*area, 2)} ha")
    b.metric("Agua que falta", f"{numero(tabla['Déficit'].clip(lower=0).sum()*area*10, 0)} m³")
    a.metric("Humedad media", f"{numero(tabla.Humedad.mean())} %" if len(tabla) else "—")
    ndvi = ndvi_emision(datos["hoy"], (SEM / "pixeles.csv.gz").stat().st_mtime_ns)
    referencia = max(i for i in [0,7,15,30] if i <= h)
    media = ndvi.loc[tabla.Celda, f"ndvi_h{referencia}"].mean() if len(ndvi)==len(base) else np.nan
    b.metric("NDVI medio", numero(media, 2) if pd.notna(media) else "—")
    st.caption(f"NDVI de {fecha_corta(fechas[referencia])} en las celdas activas de la selección.")
    marcas_ha = actual["Revisión NDMI"]
    for estado, ha in [("Regar ahora",actual["Crítica"]), ("Vigilar",actual["Vigilar"]),
                       ("Suficiente",actual["Suficiente"]-marcas_ha), ("Revisar en campo",marcas_ha)]:
        st.progress(min(1.,max(0.,ha/(len(tabla)*area))) if len(tabla) else 0.,
                    text=f"{estado} · {numero(ha,2)} ha")


if pagina == "Panorama":
    fecha_breve = fecha_corta(fecha).rsplit(" ",1)[0]
    st.html(f'<header class="cabecera"><div><h1>Riego en Nataima</h1><p>C. I. Nataima · El Espinal, Tolima</p></div>'
            f'<div class="contexto"><span>{lote}</span><span>{fecha_breve} · {numero(len(tabla)*area)} ha en arroz</span></div></header>')
    fin = min(h+5, len(fechas)-1)
    vigilar = ((clases[h,ids] == "1") & (clases[h:fin+1,ids] == "2").any(axis=0)).sum()*area
    agua = tabla.loc[tabla.Estado=="Crítica", "Déficit"].clip(lower=0).sum()*area*10
    indicadores = [
        ("Regar ahora", actual["Crítica"], "#b53832", f"{numero(agua,0)} m³ para reponer el déficit"),
        ("Programar riego", vigilar, "#976000", f"En vigilancia y pasa a rojo hasta el {fecha_corta(fechas[fin]).rsplit(' ',1)[0]}"),
        ("Agua suficiente", actual["Suficiente"]-actual["Revisión NDMI"], "#247447", "Suelo con humedad suficiente"),
        ("Revisar en campo", actual["Revisión NDMI"], "#7653a9", "Alerta satelital en el cultivo"),
    ]
    tarjetas = [f'<div class="sira-kpi" style="--tono:{color}"><span><i></i>{nombre}</span>'
                f'<strong>{numero(ha)} ha</strong><footer>{detalle}</footer></div>' for nombre,ha,color,detalle in indicadores]
    st.html('<div class="sira-grid">' + "".join(tarjetas) + "</div>")
    with st.container(border=True):
        titulo, control = st.columns([4,1],vertical_alignment="center")
        titulo.markdown("#### Mapa de Nataima")
        fondo = control.toggle("Satélite", value=True, key="satelite_panorama")
        celda = mapa_satelital(tabla, base.loc[ids], "Semáforo", f"panorama_{lote}_{fecha}_{fondo}", fondo)
        if celda is not None:
            punto = tabla.loc[tabla.Celda == celda].iloc[0]
            st.write(f"**{punto.Lote} · Celda {celda}** · {punto.Estado} · Humedad {numero(punto.Humedad)} % · Déficit {numero(punto.Déficit)} mm")
    operaciones, tiempo, escenario = st.tabs(["Turnos de riego", "Clima semanal", "Si no se riega"])
    with operaciones:
        prioridad = ordenar_lotes(base, clases, deficit, fechas, h, area)
        if not prioridad.empty:
            opciones = prioridad.Lote.tolist()
            pagina_lotes = st.select_slider("Recorrer lotes por prioridad", options=list(range(0,len(opciones),3)),
                format_func=lambda n: f"{n+1}–{min(n+3,len(opciones))}")
            columnas = st.columns(3)
            for col, (_, r) in zip(columnas, prioridad.iloc[pagina_lotes:pagina_lotes+3].iterrows()):
                with col, st.container(border=True):
                    st.caption(f"Prioridad {r.Prioridad} · {r['Acción']}")
                    st.subheader(r.Lote)
                    st.write(f"**{numero(r['Déficit (m³)'],0)} m³** · {numero(r['Crítica (%)'],0)} % en rojo")
                    st.caption(f"{numero(r['Área activa (ha)'])} ha · {r['Etapa estimada']}")
                    st.button("Ver en el mapa", key=f"ver_{r.Lote}",on_click=abrir,args=("Mapa de humedad",r.Lote))
                    st.button("Planificar riego",key=f"plan_{r.Lote}",on_click=abrir,args=("Plan de riego",r.Lote))
    with tiempo:
        proximos_dias()
    with escenario:
        evolucion()
    st.caption(f"Corrida del {fecha_corta(datos['hoy'])} · Pronóstico GEOS del {fecha_corta(datos['geos_inicio'])}.")
elif pagina == "Mapa de humedad":
    capa, filtro = st.columns(2)
    variable = capa.selectbox("Capa", ["Semáforo", "Humedad", "Déficit", "Alerta NDMI"])
    estado = filtro.selectbox("Mostrar celdas", ["Todas", *NOMBRES.values(), "Con alerta NDMI"])
    vista = tabla
    if estado == "Con alerta NDMI":
        vista = tabla[tabla["Alerta NDMI"]]
    elif estado != "Todas":
        vista = tabla[tabla.Estado == estado]
    st.caption("Selecciona un punto para consultar la celda de 10 m. Desactiva la capa de puntos para ver el terreno.")
    satelite = st.toggle("Satélite", value=True)
    mapa_col, resumen_col = st.columns([1.8, 1], gap="medium")
    with mapa_col:
        celda_mapa = mapa_satelital(vista, base.loc[ids], variable, f"mapa_{satelite}_{lote}_{h}_{estado}_{variable}", satelite)
    with resumen_col:
        analisis_zona()
    if vista.empty:
        st.info("Ninguna celda cumple el filtro en esta fecha. Selecciona «Todas» o cambia la fecha de análisis.")
    else:
        opciones = vista.Celda.tolist()
        ultimo = (lote, fecha, estado, celda_mapa) if celda_mapa is not None else None
        if ultimo and ultimo != st.session_state.get("ultimo_punto"):
            st.session_state.celda_consulta = celda_mapa
        st.session_state.ultimo_punto = ultimo
        if st.session_state.get("celda_consulta") not in opciones:
            st.session_state.celda_consulta = opciones[0]
        i = st.selectbox("Consultar celda por identificador", opciones, key="celda_consulta")
        st.subheader(f"Celda {i} · {base.at[i, 'Lote']}")
        st.caption(f"{base.at[i,'Latitud']:.6f}°, {base.at[i,'Longitud']:.6f}° · Humedad equivalente durante la corrida")
        st.line_chart(pd.DataFrame({"Fecha": pd.to_datetime(fechas), "Humedad (%)":
            u["verde_humedad_pct"] - deficit[:, i] / u["mm_por_punto"]}), x="Fecha", y="Humedad (%)", color="#187655")
        descargar(vista, f"celdas_{fecha}_{lote}")

elif pagina == "Plan de riego":
    comparacion = st.selectbox("Comparar con", fechas[h:], index=min(7, len(fechas)-h-1))
    futuro = serie.loc[comparacion]
    k, j, m = st.columns(3)
    k.metric(f"Déficit neto · {fecha}", f"{numero(actual['Volumen neto (m³)'])} m³")
    j.metric(f"Déficit neto · {comparacion}", f"{numero(futuro['Volumen neto (m³)'])} m³")
    m.metric("Cambio de superficie crítica", f"{numero(futuro['Crítica']-actual['Crítica'], 2)} ha")
    st.subheader("Riego por lote")
    orden_calendario = ordenar_lotes(base, clases, deficit, fechas, h, area)
    detalle = orden_calendario if lote == "Toda la zona" else orden_calendario[orden_calendario.Lote == lote]
    if not detalle.empty:
        st.expander("Ver detalle técnico por lote").dataframe(detalle, hide_index=True, width="stretch", column_config={
            k: st.column_config.NumberColumn(format="%.2f") for k in ["Área activa (ha)", "Crítica (%)", "Crítica (ha)", "Déficit (m³)"]})
    else:
        st.caption("El área dispersa se incluye en el calendario y en el cálculo de volumen.")
    st.subheader("Calendario por lote")
    piezas = []
    for nombre, grupo in base.loc[ids].groupby("Lote"):
        ix = grupo.index.to_numpy()
        t = resumen(fechas, clases[:, ix], deficit[:, ix], marcas[:, ix], area).loc[fecha:comparacion].reset_index()
        t["Lote"] = nombre
        piezas.append(t)
    plan = pd.concat(piezas, ignore_index=True)
    orden_lotes = orden_calendario.Lote.tolist() if not orden_calendario.empty else []
    graf = alt.Chart(plan).mark_rect().encode(x=alt.X("Fecha:O", axis=alt.Axis(labelExpr="slice(datum.label,5)")),
        y=alt.Y("Lote:N", sort=[*orden_lotes, "Área dispersa"]), color=alt.Color("Crítica:Q", title="En rojo (ha)", scale=alt.Scale(scheme="orangered")),
        tooltip=["Lote", "Fecha", "Crítica", "Vigilar", "Volumen neto (m³)"])
    st.altair_chart(graf, width="stretch")
    descargar(plan, f"plan_{fecha}_{comparacion}_{lote}")
    st.subheader("Capacidad de bombeo")
    st.caption(f"Estimación para reponer el déficit de {lote.lower()} el {comparacion}. Ajusta las condiciones del equipo.")
    c1, c2 = st.columns(2)
    eficiencia = c1.slider("Eficiencia de aplicación (%)", 1, 100, 75)
    caudal = c2.number_input("Caudal (L/s)", min_value=0.1, value=20.0)
    bruto = futuro["Volumen neto (m³)"] * 100 / eficiencia
    v, tiempo = st.columns(2)
    v.metric("Volumen a bombear", f"{numero(bruto)} m³")
    tiempo.metric("Tiempo de bombeo", f"{numero(bruto / (3.6 * caudal))} h")

elif pagina == "Clima":
    st.caption(f"Pronóstico GEOS del {datos['geos_inicio']} · {datos['miembros_geos']} miembros · Común a toda la zona")
    clima = pd.DataFrame({"Fecha": pd.to_datetime(fechas), "Lluvia": [d["lluvia_mm"] for d in dias],
                          "ETo": [d["eto_mm"] for d in dias]}).set_index("Fecha")
    a, b = st.columns(2)
    a.metric("Lluvia acumulada al día seleccionado", f"{numero(clima.iloc[h].Lluvia)} mm")
    b.metric("Evapotranspiración acumulada", f"{numero(clima.iloc[h].ETo)} mm")
    proximos_dias()
    modo = st.radio("Escala temporal", ["Diaria", "Acumulada"], horizontal=True)
    vista = clima.diff().iloc[1:] if modo == "Diaria" else clima
    st.bar_chart(vista, stack=False, y_label="mm", color=["#509379", "#496b9d"])
    descargar(vista.reset_index(), f"clima_{modo}")

elif pagina == "Cultivo":
    a,b,c = st.columns(3)
    a.metric("Superficie activa", f"{numero(len(tabla)*area, 2)} ha")
    b.metric("Edad mediana", f"{numero(tabla['Edad inicial'].median()+h, 0)} días" if len(tabla) else "Sin cultivo")
    c.metric("Alerta del índice de humedad", f"{numero(actual['Revisión NDMI'], 2)} ha")
    st.subheader("Distribución por fecha de siembra")
    siembras = pd.to_datetime(datos["hoy"]) - pd.to_timedelta(tabla["Edad inicial"], unit="D")
    grupos = (siembras.value_counts().sort_index()*area).rename("Superficie (ha)").rename_axis("Siembra estimada")
    st.bar_chart(grupos, color="#37866a")
    st.subheader("Celdas para revisión en campo")
    alertas = tabla[tabla["Alerta NDMI"]]
    st.caption("Una anomalía del índice satelital NDMI orienta la inspección del cultivo. La causa requiere verificación en campo.")
    if len(alertas):
        st.expander("Ver celdas para inspección").dataframe(alertas, hide_index=True)
        descargar(alertas, f"inspeccion_{fecha}_{lote}")
    else:
        st.info("Sin alertas NDMI en esta selección.")

else:
    st.subheader("Cómo se calcula la humedad")
    st.write("El modelo A proyecta los índices satelitales NDVI y NDMI. El modelo B usa el balance hídrico y un ARIMAX para estimar humedad. El producto combina esas salidas en una clasificación diaria por celda.")
    st.write(f"Resolución **{datos['celda_m']} m** · {len(fechas)} fechas · Del {fechas[0]} al {fechas[-1]}.")
    st.write(f"Humedad equivalente (%) = {u['verde_humedad_pct']} − déficit (mm) / {u['mm_por_punto']}. "
             f"El déficit crítico supera {u['rojo_dr_mm']} mm. Un milímetro en una hectárea equivale a 10 m³.")
    st.write(f"Supuesto de la corrida: {datos['modelo_b']['riego_supuesto']}.")
    st.subheader("Lectura de los lotes")
    st.write("Cada lote agrupa celdas contiguas por lado con igual fecha estimada de siembra y al menos 0,5 ha. "
             "Los grupos menores figuran como área dispersa. Los límites son estimados a partir del cultivo.")
    st.caption("Fuente local · app/datos/semaforo.json · Los resultados se actualizan al reemplazar la exportación de la corrida.")



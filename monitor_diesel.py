import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import folium
from streamlit_folium import st_folium

# Configuración técnica de la página
st.set_page_config(page_title="Diésel San Nicolás - CRE RealTime", layout="wide")

@st.cache_data(ttl=3600)  # Actualiza cada hora para eficiencia logística
def fetch_cre_data():
    # URLs de datos abiertos de la CRE
    url_est = "https://publicacionpremiums.cre.gob.mx/Listado/Estaciones.xml"
    url_pre = "https://publicacionpremiums.cre.gob.mx/Listado/Precios.xml"
    
    # 1. Obtener Estaciones
    res_est = requests.get(url_est)
    soup_est = BeautifulSoup(res_est.content, 'xml')
    estaciones = []
    for p in soup_est.find_all('place'):
        # Filtro estricto para San Nicolás de los Garza
        mun = p.find('municipality').text if p.find('municipality') else ""
        if "San Nicolás de los Garza" in mun:
            estaciones.append({
                'place_id': p.get('place_id'),
                'nombre': p.find('name').text,
                'lat': float(p.find('location').get('y')),
                'lng': float(p.find('location').get('x')),
                'cre_id': p.find('cre_id').text if p.find('cre_id') else "N/A"
            })
    
    # 2. Obtener Precios
    res_pre = requests.get(url_pre)
    soup_pre = BeautifulSoup(res_pre.content, 'xml')
    precios = []
    for p in soup_pre.find_all('place'):
        for d in p.find_all('gas_price', {'type': 'diesel'}):
            precios.append({
                'place_id': p.get('place_id'),
                'precio_publico': float(d.text),
                'actualizado': d.get('update_time')
            })
            
    # 3. Cruzar y Calcular
    df = pd.merge(pd.DataFrame(estaciones), pd.DataFrame(precios), on='place_id')
    df['precio_neto_sin_iva'] = (df['precio_publico'] / 1.16).round(2)
    return df

# --- INTERFAZ DE LA APP ---
st.title("⛽ Monitor de Diésel en Tiempo Real")
st.caption("Fuente: Datos Abiertos de la Comisión Reguladora de Energía (CRE)")

try:
    df_final = fetch_cre_data()
    
    # KPIs Rápidos
    c1, c2, c3 = st.columns(3)
    c1.metric("Precio Promedio", f"${df_final['precio_publico'].mean():.2f}")
    c2.metric("Mejor Precio", f"${df_final['precio_publico'].min():.2f}")
    c3.metric("Estaciones", len(df_final))

    # Mapa de Calor de Precios
    st.subheader("Mapa de Ubicación y Costos")
    m = folium.Map(location=[25.75, -100.29], zoom_start=13)
    for _, r in df_final.iterrows():
        folium.Marker(
            [r['lat'], r['lng']],
            popup=f"<b>{r['nombre']}</b><br>Precio: ${r['precio_publico']}",
            tooltip=f"{r['nombre']} - ${r['precio_publico']}",
            icon=folium.Icon(color="green" if r['precio_publico'] == df_final['precio_publico'].min() else "blue")
        ).add_to(m)
    st_folium(m, width=1200, height=400)

    # Tabla Maestra
    st.subheader("Detalle de Establecimientos")
    st.dataframe(df_final[['nombre', 'precio_publico', 'precio_neto_sin_iva', 'actualizado', 'cre_id']].sort_values('precio_publico'), use_container_width=True)

except Exception as e:
    st.error(f"Error de conexión: {e}. Intenta refrescar en unos minutos.")
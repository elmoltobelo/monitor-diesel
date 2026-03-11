import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import folium
from streamlit_folium import st_folium
import time

# Configuración de la página
st.set_page_config(page_title="Diésel RealTime - San Nicolás", layout="wide")

@st.cache_data(ttl=3600)
def fetch_cre_data():
    urls = {
        "estaciones": "https://publicacionpremiums.cre.gob.mx/Listado/Estaciones.xml",
        "precios": "https://publicacionpremiums.cre.gob.mx/Listado/Precios.xml"
    }
    
    # Lógica de reintento para superar el error de conexión de la CRE
    res_est, res_pre = None, None
    for i in range(3):
        try:
            res_est = requests.get(urls["estaciones"], timeout=15)
            res_pre = requests.get(urls["precios"], timeout=15)
            if res_est.status_code == 200 and res_pre.status_code == 200:
                break
        except Exception:
            time.sleep(3)
    
    if not res_est or res_est.status_code != 200:
        st.error("El servidor de la CRE está saturado. Reintenta en 1 minuto.")
        return pd.DataFrame()

    # Procesar Estaciones (Filtrado por San Nicolás)
    soup_est = BeautifulSoup(res_est.content, 'xml')
    est_data = []
    for p in soup_est.find_all('place'):
        mun = p.find('municipality').text if p.find('municipality') else ""
        if "San Nicolás de los Garza" in mun:
            est_data.append({
                'place_id': p.get('place_id'),
                'nombre': p.find('name').text,
                'lat': float(p.find('location').get('y')),
                'lng': float(p.find('location').get('x')),
                'cre_id': p.find('cre_id').text if p.find('cre_id') else "S/N"
            })
    
    # Procesar Precios (Filtrado por Diésel)
    soup_pre = BeautifulSoup(res_pre.content, 'xml')
    pre_data = []
    for p in soup_pre.find_all('place'):
        for d in p.find_all('gas_price', {'type': 'diesel'}):
            pre_data.append({
                'place_id': p.get('place_id'),
                'precio_publico': float(d.text),
                'actualizado': d.get('update_time')
            })
            
    # Unión y Cálculos Fiscales
    if not est_data or not pre_data: return pd.DataFrame()
    
    df = pd.merge(pd.DataFrame(est_data), pd.DataFrame(pre_data), on='place_id')
    # Regla de negocio: Precio Neto = Precio / 1.16 (Desglose de IVA)
    df['precio_neto'] = (df['precio_publico'] / 1.16).round(2)
    return df

# --- INTERFAZ ---
st.title("⛽ Monitor de Diésel en San Nicolás de los Garza")
st.info("Datos oficiales de la CRE (Actualizados según reporte OPE)")

data = fetch_cre_data()

if not data.empty:
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Precio Promedio", f"${data['precio_publico'].mean():.2f}")
    c2.metric("Mejor Precio", f"${data['precio_publico'].min():.2f}")
    c3.metric("Estaciones", len(data))

    # Mapa
    st.subheader("📍 Ubicación de Estaciones")
    m = folium.Map(location=[25.75, -100.29], zoom_start=13)
    for _, r in data.iterrows():
        folium.Marker(
            [r['lat'], r['lng']],
            popup=f"{r['nombre']}: ${r['precio_publico']}",
            icon=folium.Icon(color="green" if r['precio_publico'] == data['precio_publico'].min() else "blue")
        ).add_to(m)
    st_folium(m, width=1200, height=400)

    # Tabla Detallada
    st.subheader("📋 Lista de Precios Vigentes")
    st.dataframe(data[['nombre', 'precio_publico', 'precio_neto', 'actualizado', 'cre_id']].sort_values('precio_publico'))
else:
    st.warning("No se pudieron cargar los datos. Esto suele ser temporal por

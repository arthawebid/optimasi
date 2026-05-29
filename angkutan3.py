import sys
import streamlit as st
import pandas as pd
import requests
import numpy as np
import folium
from streamlit_folium import st_folium

# --- KONFIGURASI PORT DAN SERVER VIA SCRIPT ---
if __name__ == '__main__':
    if f"--server.port" not in "".join(sys.argv):
        sys.argv.extend(["--server.port", "8080", "--server.headless", "true"])

# --- CONFIG HALAMAN STREAMLIT ---
st.set_page_config(page_title="Navigasi Otentik Jimbaran", layout="wide")
st.title("🗺️ Dashboard Rute Akurat - Mode Kepatuhan Jalur & Jalan Tikus")
st.write("Navigasi real-road yang mematuhi aturan satu arah resmi dan menyediakan opsi jalan alternatif/tikus per kendaraan.")

# Koordinat Sekolah
sekolah = {"name": "Sekolah (Kampus Unud)", "lat": -8.784104, "lon": 115.176648}

# --- ENGINE PENGAMBILAN RUTE (UTAMA & ALTERNATIF) ---
@st.cache_data(show_spinner=False)
def dapatkan_rute_komplit(lat1, lon1, lat2, lon2):
    """
    Mengambil 2 alternatif rute dari OSRM:
    Rute 1: Jalur Utama (Tercepat & Resmi)
    Rute 2: Jalur Alternatif (Memanfaatkan jalan alternatif/tikus jika tersedia)
    """
    try:
        # Mengaktifkan parameter alternative=true untuk mencari opsi jalan tikus/alternatif
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson&alternatives=true"
        response = requests.get(url, timeout=5).json()
        
        if response['code'] == 'Ok':
            routes = response['routes']
            
            # Rute Utama
            jarak_utama = routes[0]['distance'] / 1000
            geo_utama = [[coord[1], coord[0]] for coord in routes[0]['geometry']['coordinates']]
            
            # Rute Alternatif (Jalan Tikus jika ditemukan oleh engine)
            if len(routes) > 1:
                jarak_alt = routes[1]['distance'] / 1000
                geo_alt = [[coord[1], coord[0]] for coord in routes[1]['geometry']['coordinates']]
            else:
                # Jika tidak ada jalan alternatif lain, gunakan rute utama sebagai fallback
                jarak_alt, geo_alt = jarak_utama, geo_utama
                
            return jarak_utama, geo_utama, jarak_alt, geo_alt
    except:
        pass
    
    # Fallback matematika lurus jika server OSRM gangguan
    fallback_geo = [[lat1, lon1], [lat2, lon2]]
    return 1.0, fallback_geo, 1.0, fallback_geo

# --- ALGORITMA PENYUSUNAN MANIFEST ---
def proses_rute_armada(titik_awal, jobs):
    rute_teroptimasi = []
    posisi_sekarang = titik_awal
    sisa_jobs = jobs.copy()
    total_jarak = 0
    
    while len(sisa_jobs) > 0:
        indeks_terpilih = 0
        jarak_terkecil = float('inf')
        geo_terpilih, geo_alt_terpilih = [], []
        jarak_alt_terpilih = 0
        
        for idx, titik in enumerate(sisa_jobs):
            j_utama, g_utama, j_alt, g_alt = dapatkan_rute_komplit(posisi_sekarang['lat'], posisi_sekarang['lon'], titik['lat'], titik['lon'])
            if j_utama < jarak_terkecil:
                jarak_terkecil = j_utama
                indeks_terpilih = idx
                geo_terpilih = g_utama
                geo_alt_terpilih = g_alt
                jarak_alt_terpilih = j_alt
        
        node = sisa_jobs.pop(indeks_terpilih)
        node['jarak_utama'] = jarak_terkecil
        node['geo_utama'] = geo_terpilih
        node['jarak_alt'] = jarak_alt_terpilih
        node['geo_alt'] = geo_alt_terpilih
        
        total_jarak += jarak_terkecil
        rute_teroptimasi.append(node)
        posisi_sekarang = node
        
    return rute_teroptimasi, total_jarak

def parse_koordinat_input(text_input, prefix_label):
    daftar_titik = []
    lines = text_input.strip().split('\n')
    idx_counter = 1
    for line in lines:
        if not line.strip():
            continue
        try:
            parts = line.split(',')
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            siswa = int(parts[2].strip()) if len(parts) > 2 else 1
            daftar_titik.append({"id": f"{prefix_label} {idx_counter}", "lat": lat, "lon": lon, "siswa": siswa})
            idx_counter += 1
        except:
            st.error(f"Format penulisan salah: '{line}'")
    return daftar_titik

# --- SIDEBAR INPUT DATA ---
st.sidebar.header("📝 Manifest Koordinat Harian")

default_elf_raw = """-8.790465, 115.190529, 1
-8.793764, 115.184980, 1
-8.798365, 115.185545, 1
-8.805952, 115.186534, 1"""

default_apv_raw = """-8.782020, 115.193469, 2
-8.773100, 115.168400, 1"""

default_xenia_raw = """-8.799637, 115.152115, 1
-8.797903, 115.145172, 1"""

st.sidebar.subheader("🚌 Isuzu Elf")
elf_in = st.sidebar.text_area("Koordinat Sektor Taman Griya:", value=default_elf_raw, height=100)

st.sidebar.subheader("🚐 Suzuki APV")
apv_in = st.sidebar.text_area("Koordinat Sektor Utara:", value=default_apv_raw, height=80)

st.sidebar.subheader("🚗 Daihatsu Xenia")
xenia_in = st.sidebar.text_area("Koordinat Sektor Puri Gading:", value=default_xenia_raw, height=80)

# Pemrosesan Rute
titik_elf = parse_koordinat_input(elf_in, "Elf")
titik_apv = parse_koordinat_input(apv_in, "APV")
titik_xenia = parse_koordinat_input(xenia_in, "Xenia")

with st.spinner("Mengkalkulasi kepatuhan rambu jalan & jalur alternatif..."):
    rute_elf, j_elf = proses_rute_armada(sekolah, titik_elf)
    rute_apv, j_apv = proses_rute_armada(sekolah, titik_apv)
    rute_xenia, j_xenia = proses_rute_armada(sekolah, titik_xenia)

# --- PANEL UTAMA INTERAKTIF ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🎛️ Filter Kendaraan Mandiri")
    # Fokus satu kendaraan membantu driver melihat detail jalan tikus tanpa terganggu rute lain
    pilihan_armada = st.selectbox(
        "Pilih Kendaraan Spesifik untuk Melihat Detail Rute:", 
        ["Isuzu Elf", "Suzuki APV", "Daihatsu Xenia"]
    )
    
    st.write("---")
    st.subheader("📋 Panduan Manifes Perjalanan")
    
    if pilihan_armada == "Isuzu Elf" and rute_elf:
        st.info(f"🚌 **MANIFEST ISUZU ELF (Total Jarak Utama: {j_elf:.2f} km)**")
        for i, stop in enumerate(rute_elf, 1):
            st.write(f"**Stop {i}** ➔ {stop['id']} (Jalur Utama: {stop['jarak_utama']:.2f} km | Tikus: {stop['jarak_alt']:.2f} km)")
            
    elif pilihan_armada == "Suzuki APV" and rute_apv:
        st.warning(f"🚐 **MANIFEST SUZUKI APV (Total Jarak Utama: {j_apv:.2f} km)**")
        for i, stop in enumerate(rute_apv, 1):
            st.write(f"**Stop {i}** ➔ {stop['id']} (Jalur Utama: {stop['jarak_utama']:.2f} km | Tikus: {stop['jarak_alt']:.2f} km)")
            
    elif pilihan_armada == "Daihatsu Xenia" and rute_xenia:
        st.success(f"🚗 **MANIFEST DAIHATSU XENIA (Total Jarak Utama: {j_xenia:.2f} km)**")
        for i, stop in enumerate(rute_xenia, 1):
            st.write(f"**Stop {i}** ➔ {stop['id']} (Jalur Utama: {stop['jarak_utama']:.2f} km | Tikus: {stop['jarak_alt']:.2f} km)")

with col2:
    st.subheader("🗺️ Peta Panduan Mengemudi Berdasarkan Kendaraan")
    st.caption("💡 **Keterangan Warna Jalur:** Garis Tebal = Jalur Utama Resmi | Garis Putus-putus (Dashed) = Jalur Alternatif / Jalan Tikus")
    
    m = folium.Map(location=[sekolah['lat'], sekolah['lon']], zoom_start=14)
    folium.Marker([sekolah['lat'], sekolah['lon']], popup="START: SEKOLAH", icon=folium.Icon(color='red', icon='university', prefix='fa')).add_to(m)
    
    # Render spesifik berdasarkan dropdown pilihan_armada
    if pilihan_armada == "Isuzu Elf":
        warna_utama, warna_alt = "blue", "darkblue"
        rute_aktif = rute_elf
    elif pilihan_armada == "Suzuki APV":
        warna_utama, warna_alt = "orange", "red"
        rute_aktif = rute_apv
    else:
        warna_utama, warna_alt = "green", "darkgreen"
        rute_aktif = rute_xenia

    # Menggambar rute pada peta
    if rute_aktif:
        for pt in rute_aktif:
            # Pin Lokasi Siswa
            folium.Marker([pt['lat'], pt['lon']], popup=f"<b>{pt['id']}</b>", icon=folium.Icon(color=warna_utama)).add_to(m)
            
            # 1. Jalur Utama (Garis Tebal - Mematuhi Aturan Satu Arah OSRM)
            folium.PolyLine(pt['geo_utama'], color=warna_utama, weight=5, opacity=0.85, tooltip="Jalur Utama").add_to(m)
            
            # 2. Jalur Alternatif / Jalan Tikus (Garis Putus-putus)
            if pt['geo_utama'] != pt['geo_alt']:
                folium.PolyLine(pt['geo_alt'], color=warna_alt, weight=3, opacity=0.7, dash_array='7, 7', tooltip="Jalan Tikus / Alternatif").add_to(m)
                
    st_folium(m, width=850, height=600)
  

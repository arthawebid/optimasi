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

st.set_page_config(page_title="Navigasi Linier Searah", layout="wide")
st.title("🗺️ Dashboard Optimasi Jalur Searah - Anti Putar Balik (No Backtracking)")
st.write("Sistem mendeteksi jalan tembus kompleks. Mobil diarahkan keluar lewat gerbang terdekat menuju target berikutnya, bukan putar balik.")

# Koordinat Sekolah
sekolah = {"name": "Sekolah (Kampus Unud)", "lat": -8.784104, "lon": 115.176648}

# --- ENGINE CORE: OSRM NAVIGATION ---
@st.cache_data(show_spinner=False)
def dapatkan_rute_osrm(lat1, lon1, lat2, lon2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        response = requests.get(url, timeout=5).json()
        if response['code'] == 'Ok':
            route = response['routes'][0]
            return route['distance'] / 1000, [[coord[1], coord[0]] for coord in route['geometry']['coordinates']]
    except:
        pass
    p = 0.017453292519943295
    a = 0.5 - np.cos((lat2 - lat1) * p)/2 + np.cos(lat1 * p) * np.cos(lat2 * p) * (1 - np.cos((lon2 - lon1) * p)) / 2
    return 12742 * np.arcsin(np.sqrt(a)), [[lat1, lon1], [lat2, lon2]]

# --- HITUNG SUDUT NAVIGASI (Untuk Deteksi Putar Balik) ---
def hitung_bearing(lat1, lon1, lat2, lon2):
    """Menghitung sudut arah pergerakan dari titik 1 ke titik 2"""
    dLon = np.radians(lon2 - lon1)
    y = np.sin(dLon) * np.cos(np.radians(lat2))
    x = np.cos(np.radians(lat1)) * np.sin(np.radians(lat2)) - np.sin(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.cos(dLon)
    bearing = np.degrees(np.arctan2(y, x))
    return (bearing + 360) % 360

# --- ALGORITMA OPTIMASI DENGAN PENALTI BACKTRACKING ---
def susun_rute_anti_balik(titik_awal, jobs):
    rute_teroptimasi = []
    posisi_sekarang = titik_awal
    sisa_jobs = jobs.copy()
    total_jarak = 0
    bearing_sebelumnya = None
    
    while len(sisa_jobs) > 0:
        indeks_terpilih = 0
        skor_terbaik = float('inf')
        jarak_asli_terpilih = 0
        geo_terpilih = []
        
        for idx, titik in enumerate(sisa_jobs):
            jarak_jalan, jalur_jalan = dapatkan_rute_osrm(posisi_sekarang['lat'], posisi_sekarang['lon'], titik['lat'], titik['lon'])
            
            # Hitung sudut arah menuju titik ini
            bearing_baru = hitung_bearing(posisi_sekarang['lat'], posisi_sekarang['lon'], titik['lat'], titik['lon'])
            
            # Skema Penalti: Jika arahnya berbalik tajam (> 90 derajat dari jalur masuk), beri beban jarak semu
            penalti = 0
            if bearing_sebelumnya is not None:
                selisih_sudut = abs(bearing_baru - bearing_sebelumnya)
                if selisih_sudut > 180:
                    selisih_sudut = 360 - selisih_sudut
                
                # Jika driver dipaksa memutar balik ke belakang, beri penalti bobot jarak 5 KM semu
                if selisih_sudut > 110: 
                    penalti = 5.0 
            
            skor_rute = jarak_jalan + penalti
            
            if skor_rute < skor_terbaik:
                skor_terbaik = skor_rute
                jarak_asli_terpilih = jarak_jalan
                indeks_terpilih = idx
                geo_terpilih = jalur_jalan
                bearing_sebelumnya_temp = bearing_baru
                
        node = sisa_jobs.pop(indeks_terpilih)
        node['jarak_berkendar'] = jarak_asli_terpilih
        node['geometry'] = geo_terpilih
        
        bearing_sebelumnya = bearing_sebelumnya_temp
        total_jarak += jarak_asli_terpilih
        rute_teroptimasi.append(node)
        posisi_sekarang = node
        
    return rute_teroptimasi, total_jarak

# --- PARSER INPUT DATA ---
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
            pass
    return daftar_titik

# --- SIDEBAR MANIFEST ---
st.sidebar.header("📝 Manifest Koordinat")
default_elf_raw = """-8.790465, 115.190529, 1
-8.793764, 115.184980, 1
-8.798365, 115.185545, 1
-8.805952, 115.186534, 1"""

default_apv_raw = """-8.782020, 115.193469, 2
-8.773100, 115.168400, 1"""

default_xenia_raw = """-8.799637, 115.152115, 1
-8.797903, 115.145172, 1"""

st.sidebar.subheader("Isuzu Elf")
elf_in = st.sidebar.text_area("Sektor Taman Griya:", value=default_elf_raw, height=90)
st.sidebar.subheader("Suzuki APV")
apv_in = st.sidebar.text_area("Sektor Utara:", value=default_apv_raw, height=70)
st.sidebar.subheader("Daihatsu Xenia")
xenia_in = st.sidebar.text_area("Sektor Puri Gading:", value=default_xenia_raw, height=70)

titik_elf = parse_koordinat_input(elf_in, "Elf")
titik_apv = parse_koordinat_input(apv_in, "APV")
titik_xenia = parse_koordinat_input(xenia_in, "Xenia")

armada_pilihan = st.selectbox("Pilih Tampilan Rute Kendaraan:", ["Isuzu Elf", "Suzuki APV", "Daihatsu Xenia"])

# Eksekusi Rute Berdasarkan Pilihan
if armada_pilihan == "Isuzu Elf":
    rute_aktif, jarak_total = susun_rute_anti_balik(sekolah, titik_elf)
    warna = "blue"
elif armada_pilihan == "Suzuki APV":
    rute_aktif, jarak_total = susun_rute_anti_balik(sekolah, titik_apv)
    warna = "orange"
else:
    rute_aktif, jarak_total = susun_rute_anti_balik(sekolah, titik_xenia)
    warna = "green"

# --- TAMPILAN DASHBOARD ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader(f"📋 Manifes Perjalanan {armada_pilihan}")
    st.metric(label="Estimasi Total Jarak Efisien", value=f"{jarak_total:.2f} km")
    st.write("---")
    
    if rute_aktif:
        for i, stop in enumerate(rute_aktif, 1):
            st.info(f"**Drop {i}** ➔ **{stop['id']}**\n\nJarak Jalan: {stop['jarak_berkendar']:.2f} km")

with col2:
    st.subheader("🗺️ Peta Gerakan Linier (Maju Searah)")
    m = folium.Map(location=[sekolah['lat'], sekolah['lon']], zoom_start=14)
    folium.Marker([sekolah['lat'], sekolah['lon']], popup="SEKOLAH (START)", icon=folium.Icon(color='red', icon='university', prefix='fa')).add_to(m)
    
    if rute_aktif:
        for pt in rute_aktif:
            folium.Marker([pt['lat'], pt['lon']], popup=pt['id'], icon=folium.Icon(color=warna)).add_to(m)
            folium.PolyLine(pt['geometry'], color=warna, weight=5, opacity=0.85).add_to(m)
            
    st_folium(m, width=850, height=600)

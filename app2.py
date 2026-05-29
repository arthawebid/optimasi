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
st.set_page_config(page_title="Routing 3 Armada Jimbaran", layout="wide")
st.title("🗺️ Dashboard Rute Antaran TK - Sistem 3 Armada (Jalan Riil)")
st.write("Optimasi rute harian menggunakan Isuzu Elf, Suzuki APV, dan Daihatsu Xenia berbasis OSRM API.")

# 1. Koordinat Sekolah (Kampus Unud)
sekolah = {"name": "Sekolah (Kampus Unud)", "lat": -8.784104, "lon": 115.176648}

# 2. Fungsi Mengambil Jarak dan Geometri Jalan Riil dari OSRM API
@st.cache_data(show_spinner=False)
def dapatkan_rute_osrm(lat1, lon1, lat2, lon2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        response = requests.get(url, timeout=5).json()
        if response['code'] == 'Ok':
            route = response['routes'][0]
            jarak_km = route['distance'] / 1000
            koordinat_jalan = [[coord[1], coord[0]] for coord in route['geometry']['coordinates']]
            return jarak_km, koordinat_jalan
    except:
        pass
    # Fallback jika rute API gagal
    p = 0.017453292519943295
    a = 0.5 - np.cos((lat2 - lat1) * p)/2 + np.cos(lat1 * p) * np.cos(lat2 * p) * (1 - np.cos((lon2 - lon1) * p)) / 2
    jarak_fallback = 12742 * np.arcsin(np.sqrt(a))
    return jarak_fallback, [[lat1, lon1], [lat2, lon2]]

# 3. Algoritma Optimasi Rute
def susun_rute_real_road(titik_awal, jobs):
    rute_teroptimasi = []
    posisi_sekarang = titik_awal
    sisa_jobs = jobs.copy()
    total_jarak_armada = 0
    
    while len(sisa_jobs) > 0:
        indeks_terpilih = 0
        jarak_terkecil = float('inf')
        jalur_terpilih = []
        
        for idx, titik in enumerate(sisa_jobs):
            jarak_jalan, jalur_jalan = dapatkan_rute_osrm(posisi_sekarang['lat'], posisi_sekarang['lon'], titik['lat'], titik['lon'])
            if jarak_jalan < jarak_terkecil:
                jarak_terkecil = jarak_jalan
                indeks_terpilih = idx
                jalur_terpilih = jalur_jalan
        
        node = sisa_jobs.pop(indeks_terpilih)
        node['jarak_ke_sini'] = jarak_terkecil
        node['geometri_jalan'] = jalur_terpilih
        total_jarak_armada += jarak_terkecil
        rute_teroptimasi.append(node)
        posisi_sekarang = node
        
    if rute_teroptimasi:
        jarak_pulang, jalur_pulang = dapatkan_rute_osrm(posisi_sekarang['lat'], posisi_sekarang['lon'], titik_awal['lat'], titik_awal['lon'])
        total_jarak_armada += jarak_pulang
        rute_teroptimasi[-1]['jalur_pulang_sekolah'] = jalur_pulang
        
    return rute_teroptimasi, total_jarak_armada

# 4. Fungsi Helper Parser Input
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
            st.error(f"Format salah pada baris: '{line}'")
    return daftar_titik

# --- SIDEBAR INPUT (3 ARMADA) ---
st.sidebar.header("📝 Entri Koordinat Harian")

# Elf memegang penuh Taman Griya
default_elf_raw = """-8.790465, 115.190529, 1
-8.793764, 115.184980, 1
-8.793994, 115.183287, 1
-8.795039, 115.184327, 1
-8.795711, 115.185095, 1
-8.798365, 115.185545, 1
-8.791939, 115.188037, 1
-8.803393, 115.187910, 2
-8.805493, 115.188839, 1
-8.805952, 115.186534, 1"""

# APV memegang Taman Jimbaran + Siswa luar sisi utara/timur
default_apv_raw = """-8.782020, 115.193469, 2
-8.773100, 115.168400, 1
-8.785200, 115.163200, 1"""

# Xenia memegang Puri Gading + Siswa luar sisi barat/kampus
default_xenia_raw = """-8.799637, 115.152115, 1
-8.797903, 115.145172, 1
-8.781100, 115.151200, 1
-8.794500, 115.172100, 1
-8.796100, 115.174300, 1"""

st.sidebar.subheader("🚌 Armada 1: Isuzu Elf")
elf_input_raw = st.sidebar.text_area("Siswa Elf (Taman Griya):", value=default_elf_raw, height=120)

st.sidebar.subheader("🚐 Armada 2: Suzuki APV")
apv_input_raw = st.sidebar.text_area("Siswa APV (Taman Jbr + Utara):", value=default_apv_raw, height=100)

st.sidebar.subheader("🚗 Armada 3: Daihatsu Xenia")
xenia_input_raw = st.sidebar.text_area("Siswa Xenia (Puri Gading + Barat):", value=default_xenia_raw, height=100)

# Parsing & Eksekusi Optimasi Rute
titik_elf = parse_koordinat_input(elf_input_raw, "Elf")
titik_apv = parse_koordinat_input(apv_input_raw, "APV")
titik_xenia = parse_koordinat_input(xenia_input_raw, "Xenia")

with st.spinner("Menghitung rute 3 armada berdasarkan jalan raya riil..."):
    rute_elf, jarak_elf = sys.modules[__name__].susun_rute_real_road(sekolah, titik_elf) if titik_elf else ([], 0)
    rute_apv, jarak_apv = sys.modules[__name__].susun_rute_real_road(sekolah, titik_apv) if titik_apv else ([], 0)
    rute_xenia, jarak_xenia = sys.modules[__name__].susun_rute_real_road(sekolah, titik_xenia) if titik_xenia else ([], 0)

# --- LAYOUT DASHBOARD ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📊 Manifes Navigasi Rute")
    total_aktif = sum([x['siswa'] for x in titik_elf]) + sum([x['siswa'] for x in titik_apv]) + sum([x['siswa'] for x in titik_xenia])
    st.metric(label="Total Siswa Diantar Hari Ini", value=total_aktif)
    
    pilihan = st.selectbox("Pilih Tampilan Jalur Armada:", ["Semua Armada", "Isuzu Elf (Biru)", "Suzuki APV (Oranye)", "Daihatsu Xenia (Hijau)"])
    
    if pilihan in ["Semua Armada", "Isuzu Elf (Biru)"] and rute_elf:
        st.info(f"🚌 **JALUR ELF ({jarak_elf:.2f} km) - Sektor Taman Griya**")
        for i, stop in enumerate(rute_elf, 1):
            st.write(f"**Drop {i}** ➔ {stop['id']} (+{stop['jarak_ke_sini']:.2f} km)")
            
    if pilihan in ["Semua Armada", "Suzuki APV (Oranye)"] and rute_apv:
        st.warning(f"🚐 **JALUR APV ({jarak_apv:.2f} km) - Sektor Utara & Taman Jimbaran**")
        for i, stop in enumerate(rute_apv, 1):
            st.write(f"**Drop {i}** ➔ {stop['id']} (+{stop['jarak_ke_sini']:.2f} km)")
            
    if pilihan in ["Semua Armada", "Daihatsu Xenia (Hijau)"] and rute_xenia:
        st.success(f"🚗 **JALUR XENIA ({jarak_xenia:.2f} km) - Sektor Puri Gading & Barat**")
        for i, stop in enumerate(rute_xenia, 1):
            st.write(f"**Drop {i}** ➔ {stop['id']} (+{stop['jarak_ke_sini']:.2f} km)")

with col2:
    st.subheader("🗺️ Peta Navigasi Multi-Armada (Jimbaran)")
    m = folium.Map(location=[sekolah['lat'], sekolah['lon']], zoom_start=13)
    folium.Marker([sekolah['lat'], sekolah['lon']], popup="SEKOLAH (CAMPUS UNUD)", icon=folium.Icon(color='red', icon='university', prefix='fa')).add_to(m)
    
    # Render Lintasan Isuzu Elf (Biru)
    if pilihan in ["Semua Armada", "Isuzu Elf (Biru)"] and rute_elf:
        for pt in rute_elf:
            folium.Marker([pt['lat'], pt['lon']], popup=pt['id'], icon=folium.Icon(color='blue')).add_to(m)
            folium.PolyLine(pt['geometri_jalan'], color="blue", weight=4, opacity=0.8).add_to(m)
        if 'jalur_pulang_sekolah' in rute_elf[-1]:
            folium.PolyLine(rute_elf[-1]['jalur_pulang_sekolah'], color="darkblue", weight=3, opacity=0.5, dash_array='5, 5').add_to(m)

    # Render Lintasan Suzuki APV (Oranye)
    if pilihan in ["Semua Armada", "Suzuki APV (Oranye)"] and rute_apv:
        for pt in rute_apv:
            folium.Marker([pt['lat'], pt['lon']], popup=pt['id'], icon=folium.Icon(color='orange')).add_to(m)
            folium.PolyLine(pt['geometri_jalan'], color="orange", weight=4, opacity=0.8).add_to(m)
        if 'jalur_pulang_sekolah' in rute_apv[-1]:
            folium.PolyLine(rute_apv[-1]['jalur_pulang_sekolah'], color="darkred", weight=3, opacity=0.5, dash_array='5, 5').add_to(m)

    # Render Lintasan Daihatsu Xenia (Hijau)
    if pilihan in ["Semua Armada", "Daihatsu Xenia (Hijau)"] and rute_xenia:
        for pt in rute_xenia:
            folium.Marker([pt['lat'], pt['lon']], popup=pt['id'], icon=folium.Icon(color='green')).add_to(m)
            folium.PolyLine(pt['geometri_jalan'], color="green", weight=4, opacity=0.8).add_to(m)
        if 'jalur_pulang_sekolah' in rute_xenia[-1]:
            folium.PolyLine(rute_xenia[-1]['jalur_pulang_sekolah'], color="darkgreen", weight=3, opacity=0.5, dash_array='5, 5').add_to(m)
            
    st_folium(m, width=800, height=600)

import sys
import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium

# --- KONFIGURASI PORT DAN SERVER VIA SCRIPT ---
if __name__ == '__main__':
    if f"--server.port" not in "".join(sys.argv):
        sys.argv.extend(["--server.port", "8080", "--server.headless", "true"])

# --- CONFIG HALAMAN STREAMLIT ---
st.set_page_config(page_title="Optimasi Rute Dinamis Jimbaran", layout="wide")
st.title("🚚 Dashboard Rute Antaran TK - Input Dinamis Harian")
st.write("Masukkan koordinat anak yang aktif hari ini saja. Sistem akan langsung memperbarui rute optimal.")

# 1. Definisikan Koordinat Sekolah (Tetap)
sekolah = {"name": "Sekolah (Kampus Unud)", "lat": -8.784104, "lon": 115.176648}

# 2. Jarak Haversine
def hitung_jarak(lat1, lon1, lat2, lon2):
    R = 6371.0
    p = np.pi / 180
    a = 0.5 - np.cos((lat2 - lat1) * p)/2 + np.cos(lat1 * p) * np.cos(lat2 * p) * (1 - np.cos((lon2 - lon1) * p)) / 2
    return 2 * R * np.arcsin(np.sqrt(a))

# 3. Fungsi Optimasi Rute (Nearest Neighbor)
def susun_rute_optimal(titik_awal, jobs):
    rute = []
    posisi_sekarang = titik_awal
    sisa_jobs = jobs.copy()
    
    while len(sisa_jobs) > 0:
        indeks_terpilih = 0
        jarak_terkecil = float('inf')
        for idx, titik in enumerate(sisa_jobs):
            d = hitung_jarak(posisi_sekarang['lat'], posisi_sekarang['lon'], titik['lat'], titik['lon'])
            if d < jarak_terkecil:
                jarak_terkecil = d
                indeks_terpilih = idx
        
        node = sisa_jobs.pop(indeks_terpilih)
        rute.append(node)
        posisi_sekarang = node
    return rute

# 4. Fungsi Helper untuk Parsing Input Teks menjadi List Objek
def parse_koordinat_input(text_input, prefix_label):
    daftar_titik = []
    lines = text_input.strip().split('\n')
    idx_counter = 1
    for line in lines:
        if not line.strip():
            continue
        try:
            # Format pemisahan koma (Lat, Lon, [Opsi Jumlah Siswa])
            parts = line.split(',')
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            siswa = int(parts[2].strip()) if len(parts) > 2 else 1
            
            daftar_titik.append({
                "id": f"{prefix_label} {idx_counter}",
                "lat": lat,
                "lon": lon,
                "siswa": siswa
            })
            idx_counter += 1
        except Exception as e:
            st.error(f"Gagal membaca baris: '{line}'. Pastikan formatnya: lat, lon (Contoh: -8.782020, 115.193469)")
    return daftar_titik

# --- SIDEBAR INPUT UNTUK ENTRI MANUAL ---
st.sidebar.header("📝 Entri Koordinat Harian")

# Contoh template default agar user tidak bingung formatnya
default_elf_raw = """-8.782020, 115.193469, 2
-8.790465, 115.190529, 1
-8.793764, 115.184980, 1
-8.799637, 115.152115, 1"""

default_xenia_raw = """-8.781100, 115.151200, 1
-8.785200, 115.163200, 1"""

st.sidebar.subheader("Armada 1: Isuzu Elf")
elf_input_raw = st.sidebar.text_area("Masukkan Lat, Lon, Jumlah Siswa (1 baris 1 titik):", value=default_elf_raw, height=150)

st.sidebar.subheader("Armada 2: Daihatsu Xenia")
xenia_input_raw = st.sidebar.text_area("Masukkan Lat, Lon, Jumlah Siswa (1 baris 1 titik):", value=default_xenia_raw, height=120)

# Parsing data teks menjadi format objek/dictionary
titik_elf = parse_koordinat_input(elf_input_raw, "Siswa Elf")
titik_xenia = parse_koordinat_input(xenia_input_raw, "Siswa Xenia")

# Hitung Rute Teroptimasi berdasarkan data input terbaru
rute_elf = susun_rute_optimal(sekolah, titik_elf)
rute_xenia = susun_rute_optimal(sekolah, titik_xenia)

# --- TAMPILAN UTAMA DASHBOARD ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📊 Manifest Perjalanan Hari Ini")
    total_siswa = sum([x['siswa'] for x in titik_elf]) + sum([x['siswa'] for x in titik_xenia])
    st.metric(label="Total Siswa Aktif Diantar", value=total_siswa)
    
    pilihan = st.radio("Filter Tampilan Lintasan:", ["Semua", "Isuzu Elf", "Daihatsu Xenia"])
    
    if pilihan in ["Semua", "Isuzu Elf"] and rute_elf:
        st.info(f"🚌 **URUTAN JALUR ELF ({len(rute_elf)} Titik Turun):**")
        for i, stop in enumerate(rute_elf, 1):
            st.write(f"**{i}** ➔ {stop['id']} ({stop['lat']:.5f}, {stop['lon']:.5f}) - [{stop['siswa']} anak]")
            
    if pilihan in ["Semua", "Daihatsu Xenia"] and rute_xenia:
        st.success(f"🚗 **URUTAN JALUR XENIA ({len(rute_xenia)} Titik Turun):**")
        for i, stop in enumerate(rute_xenia, 1):
            st.write(f"**{i}** ➔ {stop['id']} ({stop['lat']:.5f}, {stop['lon']:.5f}) - [{stop['siswa']} anak]")

with col2:
    st.subheader("🗺️ Peta Navigasi Hasil Optimasi")
    
    m = folium.Map(location=[sekolah['lat'], sekolah['lon']], zoom_start=14)
    
    # Menandai Sekolah
    folium.Marker(
        [sekolah['lat'], sekolah['lon']], 
        popup="<b>SEKOLAH (START)</b>", 
        icon=folium.Icon(color='red', icon='university', prefix='fa')
    ).add_to(m)
    
    # Render Jalur Elf jika data ada
    if pilihan in ["Semua", "Isuzu Elf"] and rute_elf:
        path_elf = [[sekolah['lat'], sekolah['lon']]]
        for pt in rute_elf:
            path_elf.append([pt['lat'], pt['lon']])
            folium.Marker([pt['lat'], pt['lon']], popup=f"{pt['id']} ({pt['siswa']} anak)", icon=folium.Icon(color='blue')).add_to(m)
        path_elf.append([sekolah['lat'], sekolah['lon']])
        folium.PolyLine(path_elf, color="blue", weight=4, opacity=0.85).add_to(m)
        
    # Render Jalur Xenia jika data ada
    if pilihan in ["Semua", "Daihatsu Xenia"] and rute_xenia:
        path_xenia = [[sekolah['lat'], sekolah['lon']]]
        for pt in rute_xenia:
            path_xenia.append([pt['lat'], pt['lon']])
            folium.Marker([pt['lat'], pt['lon']], popup=f"{pt['id']} ({pt['siswa']} anak)", icon=folium.Icon(color='green')).add_to(m)
        path_xenia.append([sekolah['lat'], sekolah['lon']])
        folium.PolyLine(path_xenia, color="green", weight=4, opacity=0.85).add_to(m)
        
    st_folium(m, width=800, height=600)

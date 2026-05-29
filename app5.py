import sys
import os
import streamlit as st
import pandas as pd
import requests
import numpy as np
import folium
from streamlit_folium import st_folium
from amplpy import AMPL

# --- KONFIGURASI PORT DAN SERVER VIA SCRIPT ---
if __name__ == '__main__':
    if f"--server.port" not in "".join(sys.argv):
        sys.argv.extend(["--server.port", "8080", "--server.headless", "true"])

# --- CONFIG HALAMAN STREAMLIT ---
st.set_page_config(page_title="AMPL-Streamlit Integrasi", layout="wide")
st.title("🚚 Dashboard Navigasi Eksak TK Jimbaran - Integrasi AMPL & Python")
st.write("Sistem optimasi rute terintegrasi penuh. AMPL bertindak sebagai mesin solver matematis eksak, Python Streamlit sebagai antarmuka visual.")

# Koordinat Sekolah (Kampus Unud) sebagai Titik Depot Utama (Index 0)
sekolah = {"name": "Sekolah (Kampus Unud)", "lat": -8.784104, "lon": 115.176648}

# --- ENGINE CALL NAVIGASI JALAN RIIL (OSRM) ---
@st.cache_data(show_spinner=False)
def dapatkan_rute_komplit(lat1, lon1, lat2, lon2):
    """
    Mengambil data navigasi jalan dari OSRM.
    Mengembalikan: Jarak Utama (km), Geometri Jalur Utama, Jarak Alternatif (km), Geometri Jalur Tikus
    """
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson&alternatives=true"
        response = requests.get(url, timeout=5).json()
        
        if response['code'] == 'Ok':
            routes = response['routes']
            jarak_utama = routes[0]['distance'] / 1000
            geo_utama = [[coord[1], coord[0]] for coord in routes[0]['geometry']['coordinates']]
            
            if len(routes) > 1:
                jarak_alt = routes[1]['distance'] / 1000
                geo_alt = [[coord[1], coord[0]] for coord in routes[1]['geometry']['coordinates']]
            else:
                jarak_alt, geo_alt = jarak_utama, geo_utama
                
            return jarak_utama, geo_utama, jarak_alt, geo_alt
    except:
        pass
    
    fallback_geo = [[lat1, lon1], [lat2, lon2]]
    return 1.0, fallback_geo, 1.0, fallback_geo

# --- INTEGRASI CORE ENGINE: ENGINE OPTIMASI AMPL ---
def jalankan_optimasi_ampl(all_locations, capacities):
    """
    Menyusun Matriks Jarak, mentransfer data ke model matematika AMPL, 
    dan mengambil hasil keputusan penugasan rute variabel binary 'x'.
    """
    num_locations = len(all_locations)
    
    # 1. Bangun Matriks Jarak Jalan Riil & Geometri secara berpasangan
    distance_matrix = np.zeros((num_locations, num_locations))
    geometry_matrix = {}
    alt_geometry_matrix = {}
    alt_distance_matrix = np.zeros((num_locations, num_locations))
    
    for i in range(num_locations):
        for j in range(num_locations):
            if i == j:
                distance_matrix[i][j] = 0
                alt_distance_matrix[i][j] = 0
            else:
                j_ut, g_ut, j_al, g_al = dapatkan_rute_komplit(
                    all_locations[i]['lat'], all_locations[i]['lon'],
                    all_locations[j]['lat'], all_locations[j]['lon']
                )
                # AMPL membaca satuan jarak dalam METER (integer) untuk akurasi MIP Solver
                distance_matrix[i][j] = int(j_ut * 1000)
                alt_distance_matrix[i][j] = int(j_al * 1000)
                geometry_matrix[(i, j)] = g_ut
                alt_geometry_matrix[(i, j)] = g_al

    # 2. Inisialisasi Environment AMPL
    try:
        ampl = AMPL()
        
        # Pastikan file 'vrtp.mod' berada di direktori yang sama dengan script ini
        if os.path.exists("vrtp.mod"):
            ampl.read("vrtp.mod")
        else:
            st.error("File model matematika 'vrtp.mod' tidak ditemukan di direktori lokal!")
            return [], 0, {}, {}
            
        # 3. Injeksikan Set Elemen secara Dinamis dari Data Streamlit
        ampl.set["NODES"] = list(range(num_locations))
        ampl.set["VEHICLES"] = list(capacities.keys())
        
        # 4. Injeksikan Parameter Elemen
        ampl.param["demand"] = {i: all_locations[i]['siswa'] for i in range(num_locations)}
        ampl.param["capacity"] = capacities
        
        # Injeksikan Matriks Jarak 2D Python ke Parameter AMPL 'distance'
        dist_dict = {(i, j): distance_matrix[i][j] for i in range(num_locations) for j in range(num_locations)}
        ampl.param["distance"] = dist_dict
        
        # 5. Eksekusi Pencarian Solusi Eksak via Solver CBC
        ampl.set_option("solver", "cbc")
        ampl.solve()
        
        # 6. Ekstraksi Variabel Keputusan Berbantuan Dictionary Python
        x_values = ampl.get_variable("x").to_dict()
        objective_value = ampl.get_objective("Total_Distance").value()
        
        # Filter jalur berpindah yang aktif (bernilai 1)
        active_arcs = []
        for (i, j, v), val in x_values.items():
            if val > 0.5: # Toleransi floating-point binary variable
                active_arcs.append({
                    "dari": int(i),
                    "ke": int(j),
                    "vehicle": v,
                    "geo_utama": geometry_matrix.get((int(i), int(j)), []),
                    "geo_alt": alt_geometry_matrix.get((int(i), int(j)), []),
                    "jarak_utama": distance_matrix[int(i)][int(j)] / 1000,
                    "jarak_alt": alt_distance_matrix[int(i)][int(j)] / 1000
                })
                
        return active_arcs, objective_value / 1000, geometry_matrix, alt_geometry_matrix
    
    except Exception as e:
        st.error(f"Terjadi kesalahan pada inisialisasi API AMPL: {str(e)}")
        st.warning("Pastikan AMPL dan Solver CBC telah terinstall dengan benar di sistem host.")
        return [], 0, {}, {}

# --- HELPER PARSER DATA INPUT TEXT ---
def parse_koordinat_input(text_input):
    daftar_titik = []
    lines = text_input.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue
        try:
            parts = line.split(',')
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            siswa = int(parts[2].strip()) if len(parts) > 2 else 1
            daftar_titik.append({"lat": lat, "lon": lon, "siswa": siswa})
        except:
            pass
    return daftar_titik

# --- SIDEBAR MANIFEST HARIAN ---
st.sidebar.header("📝 Manifest Koordinat Harian")

default_input_raw = """-8.790465, 115.190529, 1
-8.793764, 115.184980, 1
-8.798365, 115.185545, 1
-8.805952, 115.186534, 1
-8.782020, 115.193469, 2
-8.773100, 115.168400, 1
-8.799637, 115.152115, 1
-8.797903, 115.145172, 1"""

siswa_in = st.sidebar.text_area("Masukkan Lat, Lon, Jumlah Siswa Aktif Hari Ini:", value=default_input_raw, height=250)
titik_siswa = parse_koordinat_input(siswa_in)

# Definisi Kapasitas Tipe Kendaraan Sesuai Parameter AMPL mod
capacities = {
    "Elf": 15,
    "APV": 8,
    "Xenia": 5
}

# Gabungkan Sekolah di Index 0 + Daftar Siswa Diterima
all_locations = [{"lat": sekolah['lat'], "lon": sekolah['lon'], "siswa": 0, "label": "SEKOLAH"}]
for idx, pt in enumerate(titik_siswa, 1):
    all_locations.append({
        "lat": pt['lat'],
        "lon": pt['lon'],
        "siswa": pt['siswa'],
        "label": f"Siswa Titik {idx}"
    })

# Sinkronisasi Tombol Kalkulasi Kerja AMPL
if st.sidebar.button("🚀 Hitung Optimasi Rute AMPL"):
    with st.spinner("Mengirim data jaringan jalan ke Solver AMPL..."):
        active_arcs, total_jarak_solusi, geo_mat, alt_geo_mat = jalankan_optimasi_ampl(all_locations, capacities)
        st.session_state['active_arcs'] = active_arcs
        st.session_state['total_jarak_solusi'] = total_jarak_solusi
        st.session_state['solved'] = True

# Inisialisasi session state jika belum menekan tombol kalkulasi
if 'solved' not in st.session_state:
    st.session_state['solved'] = False
    st.session_state['active_arcs'] = []
    st.session_state['total_jarak_solusi'] = 0

# --- TAMPILAN DASHBOARD UTAMA ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📊 Manifes Penugasan Armada Eksak")
    if st.session_state['solved'] and st.session_state['active_arcs']:
        st.metric(label="Total Jarak Tempuh Gabungan Global", value=f"{st.session_state['total_jarak_solusi']:.2f} km")
        st.write("---")
        
        # Tampilkan Dropdown untuk memfilter visualisasi manifes per kendaraan
        armada_view = st.selectbox("Pilih Kendaraan Pengemudi:", ["Elf", "APV", "Xenia"])
        
        # Bangun Urutan Perjalanan Linier dari Arcs AMPL yang aktif
        filtered_arcs = [arc for arc in st.session_state['active_arcs'] if arc['vehicle'] == armada_view]
        
        if filtered_arcs:
            st.success(f"📋 **Urutan Jalur Resmi Armada {armada_view}:**")
            # Urutkan urutan perjalanan linier dimulai dari Depot 0
            current_node = 0
            step = 1
            visited_count = 0
            
            while visited_count < len(filtered_arcs):
                for arc in filtered_arcs:
                    if arc['dari'] == current_node:
                        ke_label = all_locations[arc['ke']]['label']
                        ke_siswa = all_locations[arc['ke']]['siswa']
                        
                        if arc['ke'] == 0:
                            st.write(f"**Langkah {step}** ➔ Kembali ke **SEKOLAH** (+{arc['jarak_utama']:.2f} km)")
                        else:
                            st.write(f"**Langkah {step}** ➔ **{ke_label}** [{ke_siswa} Anak] (+{arc['jarak_utama']:.2f} km)")
                            st.caption(f" Opsi Tikus Tembus: {arc['jarak_alt']:.2f} km")
                        
                        current_node = arc['ke']
                        step += 1
                        visited_count += 1
                        break
        else:
            st.warning(f"Sektor sebaran koordinat hari ini dinilai solver AMPL tidak memerlukan mobil {armada_view} (0 Siswa Alokasi).")
    else:
        st.info("Silakan klik tombol di panel samping kiri untuk memicu proses optimasi engine AMPL.")

with col2:
    st.subheader("🗺️ Peta Navigasi Jalur Eksak Hasil Solusi AMPL")
    st.caption("💡 Jalur Solid = Hasil Rumusan Optimal Utama AMPL | Jalur Dashed = Alternatif Gang Tikus Tembus")
    
    m = folium.Map(location=[sekolah['lat'], sekolah['lon']], zoom_start=13)
    folium.Marker([sekolah['lat'], sekolah['lon']], popup="<b>START/END: SEKOLAH</b>", icon=folium.Icon(color='red', icon='university', prefix='fa')).add_to(m)
    
    # Skema Warna per jenis armada yang terdaftar di model data
    v_colors = {"Elf": "blue", "APV": "orange", "Xenia": "green"}
    v_alt_colors = {"Elf": "darkblue", "APV": "red", "Xenia": "darkgreen"}
    
    if st.session_state['solved'] and st.session_state['active_arcs']:
        # Ambil nama kendaraan aktif dari dropdown filter di panel kiri
        selected_v = st.session_state.get('armada_view', "Elf") if 'armada_view' in locals() else "Elf"
        
        for arc in st.session_state['active_arcs']:
            # Tampilkan rute di peta hanya untuk kendaraan yang dipilih (agar peta bersih)
            if arc['vehicle'] == selected_v:
                idx_ke = arc['ke']
                lat_ke = all_locations[idx_ke]['lat']
                lon_ke = all_locations[idx_ke]['lon']
                lbl_ke = all_locations[idx_ke]['label']
                anak_ke = all_locations[idx_ke]['siswa']
                
                # Plot pin tujuan jika bukan kembali ke sekolah
                if idx_ke != 0:
                    folium.Marker(
                        [lat_ke, lon_ke], 
                        popup=f"<b>{lbl_ke}</b><br>Turun: {anak_ke} anak", 
                        icon=folium.Icon(color=v_colors[selected_v])
                    ).add_to(m)
                
                # 1. Gambar Jalur Utama Hasil Keputusan AMPL (Garis Tegas)
                folium.PolyLine(
                    arc['geo_utama'], 
                    color=v_colors[selected_v], 
                    weight=5, 
                    opacity=0.85, 
                    tooltip=f"Jalur Utama {selected_v}"
                ).add_to(m)
                
                # 2. Gambar Jalur Alternatif Tikus jika rutenya memotong berbeda (Garis Putus-putus)
                if arc['geo_utama'] != arc['geo_alt']:
                    folium.PolyLine(
                        arc['geo_alt'], 
                        color=v_alt_colors[selected_v], 
                        weight=3, 
                        opacity=0.7, 
                        dash_array='7, 7', 
                        tooltip=f"Jalan Tikus Cadangan"
                    ).add_to(m)
                    
    st_folium(m, width=850, height=600)
              

import sys
import os
import sqlite3
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

st.set_page_config(page_title="AMPL-Database Integrasi", layout="wide")
st.title("🚚 Sistem Antaran TK Jimbaran - Berbasis Database & AMPL")

# Koordinat Sekolah (Kampus Unud)
sekolah = {"name": "Sekolah (Kampus Unud)", "lat": -8.784104, "lon": 115.176648}

# ==============================================================================
# 🗄️ BAGIAN FUNGSI DATABASE (SQLite)
# ==============================================================================
DB_NAME = "antar_jemput.db"

def inisialisasi_database():
    """Membuat database dan mengisi data master contoh jika database masih kosong"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS siswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            jumlah_anak INTEGER DEFAULT 1,
            armada_default TEXT
        )
    ''')
    
    # Cek apakah data kosong, jika ya isi dengan koordinat master Jimbaran Anda
    cursor.execute("SELECT COUNT(*) FROM siswa")
    if cursor.fetchone()[0] == 0:
        data_master = [
            ('Anak Taman Griya 1', -8.790465, 115.190529, 1, 'Elf'),
            ('Anak Taman Griya 2', -8.793764, 115.184980, 1, 'Elf'),
            ('Anak Taman Griya 3', -8.798365, 115.185545, 1, 'Elf'),
            ('Anak Taman Griya 4', -8.805952, 115.186534, 1, 'Elf'),
            ('Anak Taman Jimbaran', -8.782020, 115.193469, 2, 'APV'),
            ('Anak Sektor Utara', -8.773100, 115.168400, 1, 'APV'),
            ('Anak Puri Gading 1', -8.799637, 115.152115, 1, 'Xenia'),
            ('Anak Puri Gading 2', -8.797903, 115.145172, 1, 'Xenia')
        ]
        cursor.executemany("INSERT INTO siswa (nama, latitude, longitude, jumlah_anak, armada_default) VALUES (?, ?, ?, ?, ?)", data_master)
        conn.commit()
    conn.close()

def ambil_semua_siswa():
    conn = sqlite3.connect(DB_NAME)
    df_siswa = pd.read_sql_query("SELECT * FROM siswa", conn)
    conn.close()
    return df_siswa

# Jalankan inisialisasi database di awal aplikasi berjalan
inisialisasi_database()

# ==============================================================================
# 🌐 JALUR JALAN RIIL & OPTIMASI AMPL
# ==============================================================================
@st.cache_data(show_spinner=False)
def dapatkan_rute_komplit(lat1, lon1, lat2, lon2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson&alternatives=true"
        response = requests.get(url, timeout=5).json()
        if response['code'] == 'Ok':
            routes = response['routes']
            j_ut = routes[0]['distance'] / 1000
            g_ut = [[coord[1], coord[0]] for coord in routes[0]['geometry']['coordinates']]
            j_al = routes[1]['distance'] / 1000 if len(routes) > 1 else j_ut
            g_al = [[coord[1], coord[0]] for coord in routes[1]['geometry']['coordinates']] if len(routes) > 1 else g_ut
            return j_ut, g_ut, j_al, g_al
    except:
        pass
    fallback = [[lat1, lon1], [lat2, lon2]]
    return 1.0, fallback, 1.0, fallback

def jalankan_optimasi_ampl(all_locations, capacities):
    num_locations = len(all_locations)
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
                j_ut, g_ut, j_al, g_al = dapatkan_rute_komplit(all_locations[i]['lat'], all_locations[i]['lon'], all_locations[j]['lat'], all_locations[j]['lon'])
                distance_matrix[i][j] = int(j_ut * 1000)
                alt_distance_matrix[i][j] = int(j_al * 1000)
                geometry_matrix[(i, j)] = g_ut
                alt_geometry_matrix[(i, j)] = g_al

    try:
        ampl = AMPL()
        ampl.read("vrtp.mod")
        ampl.set["NODES"] = list(range(num_locations))
        ampl.set["VEHICLES"] = list(capacities.keys())
        ampl.param["demand"] = {i: all_locations[i]['siswa'] for i in range(num_locations)}
        ampl.param["capacity"] = capacities
        dist_dict = {(i, j): distance_matrix[i][j] for i in range(num_locations) for j in range(num_locations)}
        ampl.param["distance"] = dist_dict
        
        ampl.set_option("solver", "cbc")
        ampl.solve()
        
        x_values = ampl.get_variable("x").to_dict()
        objective_value = ampl.get_objective("Total_Distance").value()
        
        active_arcs = []
        for (i, j, v), val in x_values.items():
            if val > 0.5:
                active_arcs.append({
                    "dari": int(i), "ke": int(j), "vehicle": v,
                    "geo_utama": geometry_matrix.get((int(i), int(j)), []),
                    "geo_alt": alt_geometry_matrix.get((int(i), int(j)), []),
                    "jarak_utama": distance_matrix[int(i)][int(j)] / 1000,
                    "jarak_alt": alt_distance_matrix[int(i)][int(j)] / 1000
                })
        return active_arcs, objective_value / 1000
    except Exception as e:
        st.error(f"Error AMPL: {str(e)}")
        return [], 0

# ==============================================================================
# 💻 TAMPILAN DASHBOARD STREAMLIT
# ==============================================================================
# Tarik Data dari Database lokal
df_master_siswa = ambil_semua_siswa()

st.sidebar.header("📋 Presensi Absensi Harian")
st.sidebar.write("Centang siswa yang **IKUT** antaran hari ini:")

# Membuat daftar checkbox absensi dinamis berbasis database
siswa_aktif_list = []
for index, row in df_master_siswa.iterrows():
    ikut_antar = st.sidebar.checkbox(f"{row['nama']} ({row['armada_default']})", value=True)
    if ikut_antar:
        siswa_aktif_list.append({
            "lat": row['latitude'],
            "lon": row['longitude'],
            "siswa": row['jumlah_anak'],
            "label": row['nama']
        })

capacities = {"Elf": 15, "APV": 8, "Xenia": 5}

# Susun struktur lokasi: Depot 0 (Sekolah) + Hasil Filter Checkbox Absensi
all_locations = [{"lat": sekolah['lat'], "lon": sekolah['lon'], "siswa": 0, "label": "SEKOLAH"}]
for idx, s in enumerate(siswa_aktif_list, 1):
    all_locations.append({
        "lat": s['lat'], "lon": s['lon'], "siswa": s['siswa'], "label": s['label']
    })

# Tombol Eksekusi
if st.sidebar.button("🚀 Hitung Optimasi Menggunakan Database & AMPL"):
    with st.spinner("Database memproses manifes presensi harian menuju AMPL..."):
        active_arcs, total_jarak = jalankan_optimasi_ampl(all_locations, capacities)
        st.session_state['active_arcs'] = active_arcs
        st.session_state['total_jarak'] = total_jarak
        st.session_state['calculated'] = True

if 'calculated' not in st.session_state:
    st.session_state['calculated'] = False

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📋 Manifes Penugasan Harian")
    if st.session_state['calculated'] and st.session_state['active_arcs']:
        st.metric(label="Total Jarak Tempuh Global", value=f"{st.session_state['total_jarak']:.2f} km")
        armada_view = st.selectbox("Pilih Kendaraan Pengemudi:", ["Elf", "APV", "Xenia"])
        
        filtered_arcs = [arc for arc in st.session_state['active_arcs'] if arc['vehicle'] == armada_view]
        if filtered_arcs:
            current_node = 0
            step = 1
            visited = 0
            while visited < len(filtered_arcs):
                for arc in filtered_arcs:
                    if arc['dari'] == current_node:
                        ke_label = all_locations[arc['ke']]['label']
                        if arc['ke'] == 0:
                            st.write(f"**Langkah {step}** ➔ Kembali ke **SEKOLAH** (+{arc['jarak_utama']:.2f} km)")
                        else:
                            st.write(f"**Langkah {step}** ➔ **{ke_label}** (+{arc['jarak_utama']:.2f} km)")
                        current_node = arc['ke']
                        step += 1
                        visited += 1
                        break
        else:
            st.warning(f"Siswa aktif sektor ini tidak memerlukan kendaraan {armada_view}.")
    else:
        st.info("Pilih presensi anak di sidebar kiri lalu klik tombol Hitung.")

with col2:
    st.subheader("🗺️ Peta Navigasi Otomatis Database")
    m = folium.Map(location=[sekolah['lat'], sekolah['lon']], zoom_start=13)
    folium.Marker([sekolah['lat'], sekolah['lon']], popup="SEKOLAH", icon=folium.Icon(color='red', icon='university', prefix='fa')).add_to(m)
    
    v_colors = {"Elf": "blue", "APV": "orange", "Xenia": "green"}
    v_alt_colors = {"Elf": "darkblue", "APV": "red", "Xenia": "darkgreen"}
    
    if st.session_state['calculated'] and st.session_state['active_arcs']:
        sel_v = armada_view if 'armada_view' in locals() else "Elf"
        for arc in st.session_state['active_arcs']:
            if arc['vehicle'] == sel_v:
                idx_ke = arc['ke']
                if idx_ke != 0:
                    folium.Marker([all_locations[idx_ke]['lat'], all_locations[idx_ke]['lon']], popup=all_locations[idx_ke]['label'], icon=folium.Icon(color=v_colors[sel_v])).add_to(m)
                folium.PolyLine(arc['geo_utama'], color=v_colors[sel_v], weight=5, opacity=0.85).add_to(m)
                if arc['geo_utama'] != arc['geo_alt']:
                    folium.PolyLine(arc['geo_alt'], color=v_alt_colors[sel_v], weight=3, opacity=0.7, dash_array='7, 7').add_to(m)
                    
    st_folium(m, width=850, height=600)
          

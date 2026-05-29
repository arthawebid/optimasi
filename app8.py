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

st.set_page_config(page_title="AMPL-Database Fleet Management", layout="wide")
st.title("🚚 Sistem Navigasi TK Jimbaran - Manajemen Risiko Operasional Armada")

# Koordinat Sekolah (Kampus Unud)
sekolah = {"name": "Sekolah (Kampus Unud)", "lat": -8.784104, "lon": 115.176648}
DB_NAME = "antar_jemput.db"

# ==============================================================================
# 🗄️ MANAJEMEN DATABASE
# ==============================================================================
def inisialisasi_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS siswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            jumlah_anak INTEGER DEFAULT 1,
            armada_default TEXT,
            tipe_siswa TEXT DEFAULT 'Reguler'
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM siswa")
    if cursor.fetchone()[0] == 0:
        data_master = [
            ('Anak Taman Griya 1', -8.790465, 115.190529, 1, 'Elf', 'Reguler'),
            ('Anak Taman Griya 2', -8.793764, 115.184980, 1, 'Elf', 'Reguler'),
            ('Anak Taman Griya 3', -8.798365, 115.185545, 1, 'Elf', 'Reguler'),
            ('Anak Taman Jimbaran', -8.782020, 115.193469, 2, 'APV', 'Reguler'),
            ('Anak Sektor Utara', -8.773100, 115.168400, 1, 'APV', 'Reguler'),
            ('Anak Puri Gading 1', -8.799637, 115.152115, 1, 'Xenia', 'Reguler'),
            ('Siswa Temp - Kebalikan', -8.785200, 115.163200, 1, 'Xenia', 'Temporary'),
            ('Siswa Temp - Kedonganan', -8.773100, 115.168400, 1, 'APV', 'Temporary')
        ]
        cursor.executemany("INSERT INTO siswa (nama, latitude, longitude, jumlah_anak, armada_default, tipe_siswa) VALUES (?, ?, ?, ?, ?, ?)", data_master)
        conn.commit()
    conn.close()

def tambah_siswa_db(nama, lat, lon, jml, armada, tipe):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO siswa (nama, latitude, longitude, jumlah_anak, armada_default, tipe_siswa) VALUES (?, ?, ?, ?, ?, ?)", (nama, lat, lon, jml, armada, tipe))
    conn.commit()
    conn.close()

def ubah_siswa_db(id_siswa, nama, lat, lon, jml, armada, tipe):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE siswa SET nama=?, latitude=?, longitude=?, jumlah_anak=?, armada_default=?, tipe_siswa=? WHERE id=?", (nama, lat, lon, jml, armada, tipe, id_siswa))
    conn.commit()
    conn.close()

def hapus_siswa_db(id_siswa):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM siswa WHERE id=?", (id_siswa,))
    conn.commit()
    conn.close()

def ubah_tipe_siswa_db(id_siswa, tipe_baru):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE siswa SET tipe_siswa=? WHERE id=?", (tipe_baru, id_siswa))
    conn.commit()
    conn.close()

def ambil_semua_siswa():
    conn = sqlite3.connect(DB_NAME)
    df_siswa = pd.read_sql_query("SELECT * FROM siswa", conn)
    conn.close()
    return df_siswa

inisialisasi_database()

# ==============================================================================
# 🌐 JALUR JALAN RAYA & KONTROL SOLVER AMPL
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
    return 1.0, [[lat1, lon1], [lat2, lon2]], 1.0, [[lat1, lon1], [lat2, lon2]]

def jalankan_optimasi_ampl(all_locations, capacities):
    num_locations = len(all_locations)
    distance_matrix = np.zeros((num_locations, num_locations))
    geometry_matrix, alt_geometry_matrix = {}, {}
    alt_distance_matrix = np.zeros((num_locations, num_locations))
    
    for i in range(num_locations):
        for j in range(num_locations):
            if i == j:
                distance_matrix[i][j] = 0
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
        
        # Mengirim daftar armada yang AKTIF saja ke dalam model AMPL
        ampl.set["VEHICLES"] = list(capacities.keys())
        
        ampl.param["demand"] = {i: all_locations[i]['siswa'] for i in range(num_locations)}
        ampl.param["capacity"] = capacities
        dist_dict = {(i, j): distance_matrix[i][j] for i in range(num_locations) for j in range(num_locations)}
        ampl.param["distance"] = dist_dict
        
        ampl.set_option("solver", "cbc")
        ampl.solve()
        
        # Mengecek status penyelesaian solver
        solve_result = ampl.get_value("solve_result")
        if solve_result == "infeasible":
            return None, "INFEASIBLE"
            
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

# --- ANTARMUKA INTERACTIVE ---
df_master_siswa = ambil_semua_siswa()
tab_navigasi, tab_manajemen = st.tabs(["🗺️ Optimasi & Navigasi", "⚙️ Master Data Siswa"])

# ==============================================================================
# TAB 1: OPTIMASI & NAVIGASI (DENGAN MANAJEMEN ARMADA DARURAT)
# ==============================================================================
with tab_navigasi:
    # PANEL KIRI: SIDEBAR KONTROL ABSENSI & OPERASIONAL MOBIL
    st.sidebar.header("📋 Presensi Antaran Hari Ini")
    siswa_aktif_list = []

    st.sidebar.subheader("🔹 Siswa Reguler")
    df_reguler = df_master_siswa[df_master_siswa['tipe_siswa'] == 'Reguler']
    for index, row in df_reguler.iterrows():
        ikut = st.sidebar.checkbox(f"{row['nama']} ({row['armada_default']})", value=True, key=f"nav_reg_{row['id']}")
        if ikut:
            siswa_aktif_list.append({"lat": row['latitude'], "lon": row['longitude'], "siswa": row['jumlah_anak'], "label": row['nama']})

    st.sidebar.subheader("🔸 Siswa Temporary")
    df_temp = df_master_siswa[df_master_siswa['tipe_siswa'] == 'Temporary']
    for index, row in df_temp.iterrows():
        ikut = st.sidebar.checkbox(f"⚠️ {row['nama']}", value=False, key=f"nav_temp_{row['id']}")
        if ikut:
            siswa_aktif_list.append({"lat": row['latitude'], "lon": row['longitude'], "siswa": row['jumlah_anak'], "label": f"⭐ {row['nama']} (TEMP)"})

    # 🚨 FITUR BARU: PANEL STATUS KESIAPAN ARMADA (FLEET AVAILABILITY CONTROL)
    st.sidebar.write("---")
    st.sidebar.subheader("🚨 Status Kesiapan Armada")
    st.sidebar.caption("Hilangkan centang jika mobil mogok/tidak beroperasi harian:")
    
    status_elf = st.sidebar.checkbox("Isuzu Elf (Kapasitas: 15)", value=True)
    status_apv = st.sidebar.checkbox("Suzuki APV (Kapasitas: 8)", value=True)
    status_xenia = st.sidebar.checkbox("Daihatsu Xenia (Kapasitas: 5)", value=True)

    # Membangun dictionary kapasitas dinamis (hanya memasukkan armada yang dicentang aktif)
    capacities = {}
    if status_elf: capacities["Elf"] = 15
    if status_apv: capacities["APV"] = 8
    if status_xenia: capacities["Xenia"] = 5

    all_locations = [{"lat": sekolah['lat'], "lon": sekolah['lon'], "siswa": 0, "label": "SEKOLAH"}]
    for s in siswa_aktif_list:
        all_locations.append({"lat": s['lat'], "lon": s['lon'], "siswa": s['siswa'], "label": s['label']})

    # Validasi Tombol Hitung
    if st.sidebar.button("🚀 Hitung Lintasan Gabungan AMPL"):
        if not capacities:
            st.sidebar.error("❌ Kesalahan: Minimal harus ada 1 armada yang siap beroperasi!")
        else:
            with st.spinner("AMPL mendistribusikan ulang rute darurat harian..."):
                active_arcs, total_jarak = jalankan_optimasi_ampl(all_locations, capacities)
                
                if active_arcs == None and total_jarak == "INFEASIBLE":
                    st.session_state['status_error_cvrp'] = "Siswa aktif terlalu banyak, sisa kapasitas armada tidak muat! Aktifkan kembali mobil yang mogok."
                    st.session_state['calculated'] = False
                else:
                    st.session_state['status_error_cvrp'] = None
                    st.session_state['active_arcs'] = active_arcs
                    st.session_state['total_jarak'] = total_jarak
                    st.session_state['calculated'] = True

    if 'calculated' not in st.session_state:
        st.session_state['calculated'] = False

    # MAIN LAYOUT TAB 1
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📋 Manifes Operasional Sopir")
        
        # Tampilkan Pesan Error Jika Terjadi Kelebihan Beban Kapasitas (Infeasible)
        if 'status_error_cvrp' in st.session_state and st.session_state['status_error_cvrp'] is not None:
            st.error(st.session_state['status_error_cvrp'])
            
        elif st.session_state['calculated'] and st.session_state['active_arcs']:
            st.metric(label="Total Jarak Tempuh Gabungan Global", value=f"{st.session_state['total_jarak']:.2f} km")
            
            # Dropdown hanya menampilkan opsi armada yang saat ini berstatus AKTIF
            armada_view = st.selectbox("Pilih Kendaraan Pengemudi:", list(capacities.keys()))
            
            filtered_arcs = [arc for arc in st.session_state['active_arcs'] if arc['vehicle'] == armada_view]
            if filtered_arcs:
                current_node, step, visited = 0, 1, 0
                while visited < len(filtered_arcs):
                    for arc in filtered_arcs:
                        if arc['dari'] == current_node:
                            ke_label = all_locations[arc['ke']]['label']
                            st.write(f"**Drop {step}** ➔ {ke_label} (+{arc['jarak_utama']:.2f} km)")
                            current_node = arc['ke']
                            step += 1
                            visited += 1
                            break
            else:
                st.warning(f"Siswa aktif hari ini telah dipindah ke mobil lain oleh solver. Mobil {armada_view} istirahat di depot.")
        else:
            st.info("Centang manifes kehadiran & armada aktif di panel kiri, lalu klik tombol Hitung.")

    with col2:
        st.subheader("🗺️ Peta Navigasi Otomatis Jalur Dialihkan")
        m = folium.Map(location=[sekolah['lat'], sekolah['lon']], zoom_start=13)
        folium.Marker([sekolah['lat'], sekolah['lon']], popup="SEKOLAH", icon=folium.Icon(color='red', icon='university', prefix='fa')).add_to(m)
        v_colors = {"Elf": "blue", "APV": "orange", "Xenia": "green"}
        v_alt_colors = {"Elf": "darkblue", "APV": "red", "Xenia": "darkgreen"}
        
        if st.session_state['calculated'] and st.session_state['active_arcs'] and ('armada_view' in locals()):
            for arc in st.session_state['active_arcs']:
                if arc['vehicle'] == armada_view:
                    idx_ke = arc['ke']
                    if idx_ke != 0:
                        lbl = all_locations[idx_ke]['label']
                        p_color = "cadetblue" if "TEMP" in lbl else v_colors[armada_view]
                        folium.Marker([all_locations[idx_ke]['lat'], all_locations[idx_ke]['lon']], popup=lbl, icon=folium.Icon(color=p_color)).add_to(m)
                    folium.PolyLine(arc['geo_utama'], color=v_colors[armada_view], weight=5, opacity=0.85).add_to(m)
                    if arc['geo_utama'] != arc['geo_alt']:
                        folium.PolyLine(arc['geo_alt'], color=v_alt_colors[armada_view], weight=3, opacity=0.7, dash_array='7, 7').add_to(m)
        st_folium(m, width=850, height=550)

# ==============================================================================
# TAB 2: MANAJEMEN DATA SISWA (CRUD PANEL MASTER)
# ==============================================================================
with tab_manajemen:
    st.subheader("⚙️ Panel Kontrol Administrasi Data Siswa (SQLite Master)")
    col_form, col_table = st.columns([1, 2])
    
    with col_form:
        st.write("### 📝 Formulir Input Siswa")
        mode_operasi = st.radio("Pilih Operasi Data:", ["Tambah Siswa Baru", "Ubah/Edit Data Siswa Existing"])
        id_siswa_edit = None
        default_nama, default_lat, default_lon, default_jml, default_armada, default_tipe = "", -8.780000, 115.170000, 1, "Elf", "Reguler"
        
        if mode_operasi == "Ubah/Edit Data Siswa Existing":
            if not df_master_siswa.empty:
                pilihan_edit = st.selectbox("Pilih Siswa yang Ingin Diubah:", df_master_siswa['nama'].tolist())
                siswa_row = df_master_siswa[df_master_siswa['nama'] == pilihan_edit].iloc[0]
                id_siswa_edit = int(siswa_row['id'])
                default_nama = siswa_row['nama']
                default_lat = float(siswa_row['latitude'])
                default_lon = float(siswa_row['longitude'])
                default_jml = int(siswa_row['jumlah_anak'])
                default_armada = siswa_row['armada_default']
                default_tipe = siswa_row['tipe_siswa']
            else:
                st.warning("Database kosong.")
        
        input_nama = st.text_input("Nama Lengkap Siswa:", value=default_nama)
        input_lat = st.number_input("Latitude Koordinat Rumah:", format="%.6f", value=default_lat)
        input_lon = st.number_input("Longitude Koordinat Rumah:", format="%.6f", value=default_lon)
        input_jml = st.number_input("Jumlah Anak:", min_value=1, max_value=5, value=default_jml)
        input_armada = st.selectbox("Rekomendasi Utama Kendaraan:", ["Elf", "APV", "Xenia"], index=["Elf", "APV", "Xenia"].index(default_armada))
        input_tipe = st.selectbox("Status Berlangganan (Tipe):", ["Reguler", "Temporary"], index=["Reguler", "Temporary"].index(default_tipe))
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("💾 Simpan Perubahan"):
                if input_nama:
                    if mode_operasi == "Tambah Siswa Baru":
                        tambah_siswa_db(input_nama, input_lat, input_lon, input_input_jml, input_armada, input_tipe)
                    else:
                        ubah_siswa_db(id_siswa_edit, input_nama, input_lat, input_lon, input_jml, input_armada, input_tipe)
                    st.rerun()
        with col_btn2:
            if mode_operasi == "Ubah/Edit Data Siswa Existing" and id_siswa_edit is not None:
                if st.button("🗑️ Hapus Siswa từ DB", type="primary"):
                    hapus_siswa_db(id_siswa_edit)
                    st.rerun()

    with col_table:
        st.write("### ⚡ Akselerasi Konversi Status Siswa")
        df_only_temp = df_master_siswa[df_master_siswa['tipe_siswa'] == 'Temporary']
        if not df_only_temp.empty:
            for idx, r in df_only_temp.iterrows():
                col_name, col_act = st.columns([3, 2])
                with col_name:
                    st.markdown(f"⚠️ **{r['nama']}** | Alamat: `{r['latitude']:.5f}, {r['longitude']:.5f}`")
                with col_act:
                    if st.button(f"🔄 Jadikan Permanen/Reguler", key=f"conv_{r['id']}"):
                        ubah_tipe_siswa_db(int(r['id']), "Reguler")
                        st.rerun()
        else:
            st.success("🎉 Semua siswa berstatus Reguler.")
            
        st.write("---")
        st.dataframe(df_master_siswa[['id', 'nama', 'latitude', 'longitude', 'jumlah_anak', 'armada_default', 'tipe_siswa']], use_container_width=True)

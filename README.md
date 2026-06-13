# 📘 SISTEM OPTIMASI RUTE ARMADA ANTAR-JEMPUT SISWA BERBASIS AMPL, STREAMLIT, DAN OSRM

## 📌 Ringkasan Sistem

Sistem ini merupakan implementasi **Vehicle Routing Problem (VRP)** berbasis optimasi eksak menggunakan **AMPL (A Mathematical Programming Language)** yang diintegrasikan dengan:

* **Streamlit** → antarmuka pengguna (UI dashboard)
* **OSRM API** → perhitungan rute jalan nyata (real-road routing)
* **SQLite** → manajemen data siswa (CRUD)
* **Folium** → visualisasi peta interaktif

Evolusi sistem dikembangkan secara bertahap dalam file:

```
app.py  → app2.py → app3.py → app4.py → app5.py → app6.py → app7.py → app8.py
```

Setiap versi menambahkan fitur baru dari sistem statis → dinamis → database → manajemen risiko armada.

---

# 🏗️ ARSITEKTUR SISTEM

## 🔷 Arsitektur Umum

```
                ┌──────────────────────┐
                │   STREAMLIT UI       │
                │ (app1 - app8 layer)  │
                └─────────┬────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   OSRM API   │  │   SQLITE DB  │  │   FOLIUM MAP │
│ Routing Jalan│  │ Data Siswa   │  │ Visualisasi  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └────────┬────────┴────────┬────────┘
                ▼                 ▼
          ┌──────────────────────────┐
          │       AMPL MODEL         │
          │  (VRP Optimization)      │
          └──────────┬───────────────┘
                     ▼
            ┌──────────────────┐
            │ CBC / MILP SOLVER│
            └──────────────────┘
```

---

# 📊 MODEL MATEMATIKA (VRP FORMULATION)

Model inti yang digunakan adalah **Capacitated Vehicle Routing Problem (CVRP)** dengan formulasi Mixed Integer Linear Programming (MILP).

---

## 📌 Himpunan (Sets)

$N = {0,1,2,...,n}$

* Node 0 = depot (sekolah)
* Node lainnya = titik siswa

$V = \text{set kendaraan}$

---

## 📌 Parameter

| Parameter | Deskripsi                      |
| --------- | ------------------------------ |
| ($d_{ij}$)  | jarak dari node i ke j (meter) |
| ($q_i$)     | demand (jumlah siswa)          |
| ($C_v$)     | kapasitas kendaraan v          |

---

## 📌 Variabel Keputusan

$$
x_{ijv} =
\begin{cases}
1, & \text{jika kendaraan } v \text{ melewati rute } i \rightarrow j \\
0, & \text{lainnya}
\end{cases}
$$

$$
u_{iv} = \text{variabel urutan kunjungan untuk kendaraan } v
$$

---

## 🎯 Fungsi Objektif

Minimisasi total jarak:

$$
\min \sum_{i \in N} \sum_{j \in N} \sum_{v \in V} d_{ij} \cdot x_{ijv}
$$

---

## 📌 Kendala (Constraints)

### 1. Setiap pelanggan dikunjungi tepat 1 kali

$$
\sum_{j \in N} \sum_{v \in V, j \neq i} x_{ijv} = 1, \quad \forall i \in N \setminus \{0\}
$$

---

### 2. Keseimbangan flow (in = out)

$$
\sum_{j \in N, j \neq i} x_{ijv}=
\sum_{j \in N, j \neq i} x_{jiv},\quad \forall i \in N, \forall v \in V
$$

---

### 3. Depot constraint (start dari sekolah)

$$
\sum_{j \in N \setminus \{0\}} x_{0jv} \le 1,
\quad \forall v \in V
$$

---

### 4. Kapasitas kendaraan

$$
\sum_{i \in N \setminus \{0\}} \sum_{j \in N} q_i \cdot x_{ijv}
\le C_v,
\quad \forall v \in V
$$

---

### 5. Subtour Elimination (MTZ)

$$
u_{iv} - u_{jv} + |N| \cdot x_{ijv} \le |N| - 1,
\quad \forall i \neq j,\ i,j \in N \setminus \{0\},\ v \in V
$$

👉 memastikan tidak ada rute kecil yang tidak kembali ke depot

---

# 🧠 PENJELASAN ALGORITMA

## 🔹 1. OSRM Routing Layer

* Mengambil jarak **real-road**
* Output:

  * shortest route
  * alternative route (“jalan tikus”)

---

## 🔹 2. Distance Matrix Builder

Mengubah koordinat menjadi:

$D = [d_{ij}]$

berbasis API OSRM (bukan Euclidean)

---

## 🔹 3. AMPL Solver Layer

* Model `.mod` → VRP formulation
* Solver → CBC (Mixed Integer Programming)

Output:

* variabel binary ($x_{ijv}$)
* total jarak optimal

---

## 🔹 4. Streamlit Visualization

* Menampilkan hasil solver
* Filter kendaraan
* Animasi rute di Folium

---

## 🔹 5. SQLite Layer (app6–app8)

Menambahkan:

* CRUD siswa
* status siswa (reguler/temporary)
* assignment dinamis

---

# 🧪 EVOLUSI SISTEM (APP 1 → APP 8)

## 🟢 app.py (Baseline System)

* Input manual koordinat
* Optimasi VRP sederhana
* Tanpa database

---

## 🟡 app2.py (Routing Enhancement)

* Integrasi OSRM routing
* Alternatif route (jalan tikus)

---

## 🟠 app3.py (Multi Vehicle)

* Multi kendaraan (Elf, APV, Xenia)
* Distribusi beban awal

---

## 🔵 app4.py (Improved Visualization)

* Folium enhancement
* Polyline per kendaraan
* UI lebih interaktif

---

## 🟣 app5.py (AMPL Engine Integration Full)

* Full AMPL solver integration
* Geometry dual-route (utama vs alternatif)
* Advanced dashboard

---

## 🟤 app6.py (Database Integration)

* SQLite database siswa
* Absensi harian (checkbox)
* Dynamic demand input

---

## 🔴 app7.py (CRUD + Data Management System)

* Create / Read / Update / Delete siswa
* Status siswa: Reguler vs Temporary
* Konversi otomatis status siswa

---

## ⚫ app8.py (Fleet Risk Management System)

* Simulasi armada rusak (disable vehicle)
* Dynamic capacity constraint
* Infeasibility detection:
  solve_result = infeasible
* Re-optimization otomatis

---

# ⚙️ FITUR UTAMA SISTEM

* ✔ VRP Optimization (AMPL + CBC)
* ✔ Real-road routing (OSRM)
* ✔ Multi-vehicle scheduling
* ✔ Dynamic student database
* ✔ Fleet failure simulation
* ✔ Interactive GIS visualization
* ✔ Subtour elimination (MTZ model)

---

# 📈 OUTPUT SISTEM

Sistem menghasilkan:

* Rute optimal tiap kendaraan
* Total jarak minimum
* Urutan kunjungan siswa
* Visualisasi peta GIS
* Alternatif rute jalan kecil

---

# 🧾 KESIMPULAN AKADEMIK

Sistem ini merupakan implementasi **Capacitated Vehicle Routing Problem (CVRP)** berbasis MILP yang diperluas dengan:

* data real-world GIS routing (OSRM)
* database dinamis (SQLite)
* user-driven scheduling (Streamlit)
* solver eksak (AMPL + CBC)

Pendekatan ini menghasilkan solusi optimal secara matematis sekaligus realistis secara geografis.


 ---
 Buat Enviroment VENV
 ```bash
 phyton3 -m venv optimasi
```
 Aktifkan Enviroment
 ```bash
 source optimasi/bin/activate
 ```
 install modul
 ```bash
 pip install streamlit amplpy pandas numpy folium streamlit-folium
```
```bash
 python -m amplpy.modules install highs cbc gurobi
```
```bash
 pip install -r requirements.txt
```
 buat daftar modul
 ```bash
 pip freeze > requirements.txt  
```
Run Optimasi
```bash
streamlit run app.py --server.port 8899
```
---


# Sets
set NODES;                       # Semua titik (0 = Sekolah, 1..N = Titik Antar)
set CLIENTS = NODES diff {0};    # Hanya titik pengantaran siswa
set VEHICLES;                    # Kumpulan armada (Elf, Xenia)

# Parameters
param distance{NODES, NODES};    # Matriks jarak antar titik (meter)
param demand{NODES};             # Jumlah siswa di tiap titik
param capacity{VEHICLES};        # Kapasitas maksimal tiap armada

# Variables
var x{NODES, NODES, VEHICLES} binary; # 1 jika armada v melewati jalur (i,j)
var u{CLIENTS, VEHICLES} >= 1;        # Variabel bantu untuk eliminasi sub-tour (MTZ)

# Objective: Meminimalkan total jarak tempuh seluruh armada
minimize Total_Distance:
    sum{i in NODES, j in NODES, v in VEHICLES} distance[i,j] * x[i,j,v];

# Constraints
subject to Visit_Once{i in CLIENTS}:
    sum{j in NODES, v in VEHICLES: i != j} x[i,j,v] = 1;

subject to Leave_Node{i in NODES, v in VEHICLES}:
    sum{j in NODES: i != j} x[i,j,v] = sum{j in NODES: i != j} x[j,i,v];

subject to Start_At_Depot{v in VEHICLES}:
    sum{j in CLIENTS} x[0,j,v] <= 1;

subject to Capacity_Limit{v in VEHICLES}:
    sum{i in CLIENTS, j in NODES: i != j} demand[i] * x[i,j,v] <= capacity[v];

subject to Subtour_Elimination{i in CLIENTS, j in CLIENTS, v in VEHICLES: i != j}:
    u[i,v] - u[j,v] + card(CLIENTS) * x[i,j,v] <= card(CLIENTS) - 1;
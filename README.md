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

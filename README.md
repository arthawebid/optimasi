 Buat Enviroment VENV
 phyton3 -m venv optimasi

 Aktifkan Enviroment
 source optimasi/bin/activate
 
 install modul
 pip install streamlit amplpy pandas numpy folium streamlit-folium 
 python -m amplpy.modules install highs cbc gurobi  
 pip install -r requirements.txt

 buat daftar modul
 pip freeze > requirements.txt  

streamlit run angkutan2.py --server.port 8899

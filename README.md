# SIRA · Riego en Nataima

Dashboard de Streamlit para consultar la humedad del arroz y las prioridades de riego de Nataima, Tolima. Incluye la corrida del 19 de noviembre de 2026 del proyecto [SIRA](https://github.com/GomSal/SIRA), rama modelo-humedad. Los fondos cartográficos se cargan por internet.

## Ejecutar en Windows

Desde la raíz del repositorio, con Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app/dashboard.py
```

## Publicar

Crea un repositorio vacío en tu cuenta de GitHub. Desde esta carpeta, vincula el repositorio y sube la rama principal sustituyendo TU_USUARIO y TU_REPOSITORIO:

```powershell
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
git push -u origin main
```

En [Streamlit Community Cloud](https://share.streamlit.io/) selecciona **Create app**, el repositorio de tu cuenta, la rama **main** y el archivo **app/dashboard.py**. Elige Python 3.12 y pulsa **Deploy**. Cuando cargue el mapa, usa **Share → Copy link** para obtener el enlace. El acceso de los clientes depende de la visibilidad de la aplicación.

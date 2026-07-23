import sys
from pathlib import Path
sys.path.insert(0, str(Path("/home/acer/projetos_antgravity/dissertacao-soja-ia/06_app")))
import model as M

df = M.carregar("/home/acer/projetos_antgravity/dissertacao-soja-ia/dados/soja_para_mascarado_2001_2024.csv")
print(df["municipio"].unique()[:5])

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "software" / "dashboard_web"))
import model as M

df = M.carregar(str(RAIZ / "pesquisa" / "dados" / "soja_para_mascarado_2001_2024.csv"))
print(df["municipio"].unique()[:5])

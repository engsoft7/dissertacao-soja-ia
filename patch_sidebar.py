import re

with open("software/dashboard_web/app.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Insert the global sidebar selectors just before "# ====================== ABA 1: MAPA"
sidebar_globals = """
st.sidebar.markdown("### Parâmetros Globais")
municipio = st.sidebar.selectbox(
    "Polo Científico / Município",
    municipios,
    key="mun_sel",
    format_func=disp,
    on_change=on_dropdown_change)

comparar = st.sidebar.toggle("Comparar com vizinho", value=False)
mun_comp = None
if comparar:
    opcoes_comp = [m for m in municipios if m != municipio]
    mun_comp = st.sidebar.selectbox(
        "Município Paralelo",
        opcoes_comp,
        format_func=disp)

ano_alvo = st.sidebar.number_input(
    "Safra Alvo (Projeção IA)",
    min_value=int(df.ano.max()) + 1,
    max_value=int(df.ano.max()) + 3,
    value=int(df.ano.max()) + 1)

unidade = st.sidebar.radio(
    "Unidade",
    options=["Sacadas (60kg)", "Quilos (kg)"],
    index=0
)
fator = SACA_KG if "Sacadas" in unidade else 1.0
preco_base = PRECO_SACA_ONLINE
st.sidebar.divider()

# ==============================================================================
# ABA 1: MAPA E PREVISÃO
"""
text = text.replace("# ==============================================================================\n# ABA 1: MAPA E PREVISÃO", sidebar_globals)


import sys
with open("software/dashboard_web/app.py", "w", encoding="utf-8") as f:
    f.write(text)

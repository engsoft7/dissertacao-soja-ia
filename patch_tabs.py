with open("software/dashboard_web/app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace the tabs creation
tabs_decl = '''    aba_mapa, aba_graficos, aba_eco = st.tabs([
        "Inteligência Territorial",
        "Análise Histórica",
        "Viabilidade Financeira"
    ])'''

sidebar_decl = '''    st.sidebar.markdown("### Navegação Principal")
    tela_atual = st.sidebar.radio(
        "",
        ["📍 Inteligência Territorial", "📈 Análise Histórica", "💰 Viabilidade Financeira"],
        label_visibility="collapsed"
    )
    st.sidebar.divider()'''

text = text.replace(tabs_decl, sidebar_decl)

# Replace with blocks
text = text.replace('    with aba_mapa:', '    if tela_atual == "📍 Inteligência Territorial":')
text = text.replace('    with aba_graficos:', '    if tela_atual == "📈 Análise Histórica":')
text = text.replace('    with aba_eco:', '    if tela_atual == "💰 Viabilidade Financeira":')

with open("software/dashboard_web/app.py", "w", encoding="utf-8") as f:
    f.write(text)

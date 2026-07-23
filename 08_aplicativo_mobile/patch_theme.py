import re

with open("app/src/main/java/com/agrointeligencia/app/MainActivity.kt", "r") as f:
    content = f.read()

# Add import
if "import androidx.compose.foundation.isSystemInDarkTheme" not in content:
    content = content.replace("import androidx.compose.foundation.background",
                              "import androidx.compose.foundation.background\nimport androidx.compose.foundation.isSystemInDarkTheme")

# Replace setContent block
setContent_orig = """        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    background = Color(0xFF0F172A),
                    surface = Color(0xFF1E293B),
                    primary = Color(0xFF10B981),
                    onBackground = Color(0xFFE2E8F0),
                    onSurface = Color(0xFFE2E8F0)
                )
            ) {"""

setContent_new = """        setContent {
            val isDark = isSystemInDarkTheme()
            val colors = if (isDark) {
                darkColorScheme(
                    background = Color(0xFF0F172A),
                    surface = Color(0xFF1E293B),
                    primary = Color(0xFF10B981),
                    onBackground = Color(0xFFE2E8F0),
                    onSurface = Color(0xFFE2E8F0)
                )
            } else {
                lightColorScheme(
                    background = Color(0xFFF8FAFC),
                    surface = Color(0xFFFFFFFF),
                    primary = Color(0xFF059669),
                    onBackground = Color(0xFF1E293B),
                    onSurface = Color(0xFF1E293B)
                )
            }
            MaterialTheme(
                colorScheme = colors
            ) {"""
content = content.replace(setContent_orig, setContent_new)

# Add isDark into ResumoFinanceiroCard
content = content.replace("fun ResumoFinanceiroCard(projecao: PrevisaoHistorico, kpis: KpiEconomiaResponse) {",
                          "fun ResumoFinanceiroCard(projecao: PrevisaoHistorico, kpis: KpiEconomiaResponse) {\n    val isDark = isSystemInDarkTheme()")
content = content.replace("val profitColor = if (lucro >= 0) Color(0xFF3fb950) else Color(0xFFf85149)",
                          "val profitColor = if (lucro >= 0) (if (isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if (isDark) Color(0xFFf85149) else Color(0xFFdc2626))")

# Add isDark into CenarioClimaticoCard
content = content.replace("fun CenarioClimaticoCard(municipio: String, baselineRendimento: Double) {",
                          "fun CenarioClimaticoCard(municipio: String, baselineRendimento: Double) {\n    val isDark = isSystemInDarkTheme()")
content = content.replace("color = if (delta < 0) Color(0xFFf85149) else if (delta > 0) Color(0xFF3fb950) else MaterialTheme.colorScheme.primary",
                          "color = if (delta < 0) (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626)) else if (delta > 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else MaterialTheme.colorScheme.primary")
content = content.replace("val c = if (delta >= 0) Color(0xFF3fb950) else Color(0xFFf85149)",
                          "val c = if (delta >= 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626))")


# Fix OutlinedTextField colors in ResumoFinanceiroCard
content = content.replace("Color(0xFF161b22)", "if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9)")

# Add isDark into ResumoAgronomicoCard
content = content.replace("fun ResumoAgronomicoCard(projecao: PrevisaoHistorico, ultimoReal: PrevisaoHistorico?) {",
                          "fun ResumoAgronomicoCard(projecao: PrevisaoHistorico, ultimoReal: PrevisaoHistorico?) {\n    val isDark = isSystemInDarkTheme()")
content = content.replace("val color = if (diff >= 0) Color(0xFF3fb950) else Color(0xFFf85149)",
                          "val color = if (diff >= 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626))")

# Add isDark into PrevisaoCard
content = content.replace("fun PrevisaoCard(historico: PrevisaoHistorico, kpis: KpiEconomiaResponse?) {",
                          "fun PrevisaoCard(historico: PrevisaoHistorico, kpis: KpiEconomiaResponse?) {\n    val isDark = isSystemInDarkTheme()")
content = content.replace("val color = if (lucro > 0) Color(0xFF3fb950) else Color(0xFFf85149)",
                          "val color = if (lucro > 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626))")

# Fix Color(0xFF58a6ff) and Color(0xFFbc8cff) which are light blue and light purple - maybe make them darker in light mode
# 0xFF58a6ff -> 0xFF2563eb
# 0xFFbc8cff -> 0xFF7c3aed
content = content.replace("Color(0xFF58a6ff)", "(if(isDark) Color(0xFF58a6ff) else Color(0xFF2563eb))")
content = content.replace("Color(0xFFbc8cff)", "(if(isDark) Color(0xFFbc8cff) else Color(0xFF7c3aed))")

# MetodologiaCard needs isDark? 58a6ff and bc8cff are used there.
content = content.replace("fun MetodologiaCard() {",
                          "fun MetodologiaCard() {\n    val isDark = isSystemInDarkTheme()")

with open("app/src/main/java/com/agrointeligencia/app/MainActivity.kt", "w") as f:
    f.write(content)


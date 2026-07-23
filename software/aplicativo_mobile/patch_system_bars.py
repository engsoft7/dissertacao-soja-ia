import re

with open("app/src/main/java/com/agrointeligencia/app/MainActivity.kt", "r") as f:
    content = f.read()

# Add imports if missing
imports = [
    "import androidx.compose.ui.platform.LocalView",
    "import androidx.compose.ui.graphics.toArgb",
    "import android.app.Activity",
    "import androidx.core.view.WindowCompat"
]

for imp in imports:
    if imp not in content:
        content = content.replace("import androidx.compose.ui.platform.LocalContext",
                                  f"import androidx.compose.ui.platform.LocalContext\n{imp}")

# Inject SideEffect for system bars
target = "MaterialTheme(\n                colorScheme = colors\n            ) {\n                Surface("
replacement = """MaterialTheme(
                colorScheme = colors
            ) {
                val view = LocalView.current
                if (!view.isInEditMode) {
                    SideEffect {
                        val window = (view.context as Activity).window
                        window.statusBarColor = colors.background.toArgb()
                        window.navigationBarColor = colors.surface.toArgb()
                        WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !isDark
                        WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = !isDark
                    }
                }
                Surface("""

if "SideEffect {" not in content:
    content = content.replace(target, replacement)

with open("app/src/main/java/com/agrointeligencia/app/MainActivity.kt", "w") as f:
    f.write(content)

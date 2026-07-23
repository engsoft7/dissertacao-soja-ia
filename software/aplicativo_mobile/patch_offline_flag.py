import re

with open("app/src/main/java/com/agrointeligencia/app/MainActivity.kt", "r") as f:
    content = f.read()

# Fix loadData
content = content.replace("isOfflineMode = true // Assumes offline until network update succeeds",
                          "// Do not assume offline yet to avoid flickering")

target_loadData_catch = """                }
            } catch (e: Exception) {
                e.printStackTrace()
                if (cachedMunStr == null) {"""
replacement_loadData_catch = """                }
            } catch (e: Exception) {
                isOfflineMode = true
                e.printStackTrace()
                if (cachedMunStr == null) {"""
content = content.replace(target_loadData_catch, replacement_loadData_catch)

# Fix LaunchedEffect
target_le_sync = """                    val prevResponse = RetrofitClient.getInstance().getPrevisao(mun)
                    previsao = prevResponse // Atualiza estado silenciosamente
                    sharedPrefs.edit().putString("previsao_$mun", gson.toJson(prevResponse)).apply()
                } catch (e: Exception) {"""
replacement_le_sync = """                    val prevResponse = RetrofitClient.getInstance().getPrevisao(mun)
                    previsao = prevResponse // Atualiza estado silenciosamente
                    sharedPrefs.edit().putString("previsao_$mun", gson.toJson(prevResponse)).apply()
                    isOfflineMode = false
                } catch (e: Exception) {
                    isOfflineMode = true"""
content = content.replace(target_le_sync, replacement_le_sync)

with open("app/src/main/java/com/agrointeligencia/app/MainActivity.kt", "w") as f:
    f.write(content)

# Regras do R8 para o build de release.
#
# As classes do próprio app são poucas, e o Gson lê as respostas da API por
# reflexão nos campos das data classes (ApiService.kt e o que fica guardado no
# celular): ficam inteiras. O R8 enxuga as bibliotecas, que são o grosso do APK.
-keep class com.agrointeligencia.app.** { *; }
-keepattributes Signature, *Annotation*, InnerClasses, EnclosingMethod

# O LiteRT (contador de vagens) liga as classes Java à biblioteca nativa pela JNI.
-keep class org.tensorflow.lite.** { *; }
-keep class com.google.ai.edge.litert.** { *; }
-dontwarn org.tensorflow.lite.**
-dontwarn com.google.ai.edge.litert.**

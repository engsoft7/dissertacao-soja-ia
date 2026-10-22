#!/bin/bash
awk 'NR==232 {
    print "                                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp, bottom = 8.dp)) {"
    print "                                    Icon(Icons.Filled.DateRange, contentDescription = null, tint = MaterialTheme.colorScheme.onBackground)"
    print "                                    Spacer(Modifier.width(8.dp))"
    print "                                    Text("
    print "                                        text = \"Histórico Completo\","
    print "                                        fontSize = 18.sp,"
    print "                                        fontWeight = FontWeight.SemiBold,"
    print "                                        color = MaterialTheme.colorScheme.onBackground"
    print "                                    )"
    print "                                }"
    next
}
NR>=233 && NR<=238 { next }
{ print }
' app/src/main/java/com/agrointeligencia/app/MainActivity.kt > temp.kt
mv temp.kt app/src/main/java/com/agrointeligencia/app/MainActivity.kt

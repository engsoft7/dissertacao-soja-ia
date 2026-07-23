#!/bin/bash
awk 'NR==212 {
    print "                                }"
    print "                            }"
    next
}
{ print }
' app/src/main/java/com/agrointeligencia/app/MainActivity.kt > temp.kt
mv temp.kt app/src/main/java/com/agrointeligencia/app/MainActivity.kt

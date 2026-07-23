# Fix missing launcher icon resources

The project is currently failing to build because the `AndroidManifest.xml` references `@mipmap/ic_launcher` and `@mipmap/ic_launcher_round`, but these resources are missing from the `res` directory.

## Proposed Changes

I will create a set of default adaptive icon resources to resolve the build error.

### app

#### [NEW] [colors.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/values/colors.xml)
Define primary colors for the launcher icon.

#### [NEW] [ic_launcher_background.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/drawable/ic_launcher_background.xml)
A simple vector background for the adaptive icon.

#### [NEW] [ic_launcher_foreground.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/drawable/ic_launcher_foreground.xml)
A placeholder vector foreground for the adaptive icon.

#### [NEW] [ic_launcher.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml)
Adaptive icon definition referencing background and foreground.

#### [NEW] [ic_launcher_round.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml)
Adaptive icon definition for round icons.

## Verification Plan

### Automated Tests
- Run `./gradlew :app:processDebugResources` to verify that resource linking now succeeds.

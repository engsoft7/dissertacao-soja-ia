# Implementation Plan - Fix Missing Launcher Icons

The build is failing because the `AndroidManifest.xml` references `@mipmap/ic_launcher` and `@mipmap/ic_launcher_round`, but these resource files do not exist in the project.

## Proposed Changes

### [Component Name] - Resources

I will create the missing launcher icon resources using adaptive icons (supported since API 26, which is the project's `minSdk`).

#### [NEW] [colors.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/values/colors.xml)
Create a basic colors file to define colors for the icons.

#### [NEW] [ic_launcher_background.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/drawable/ic_launcher_background.xml)
A simple vector drawable for the adaptive icon background.

#### [NEW] [ic_launcher_foreground.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/drawable/ic_launcher_foreground.xml)
A simple vector drawable for the adaptive icon foreground.

#### [NEW] [ic_launcher.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml)
The adaptive icon definition.

#### [NEW] [ic_launcher_round.xml](file:///home/acer/projetos_antgravity/AgroAppAndroid/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml)
The round adaptive icon definition (aliased to the adaptive icon).

## Verification Plan

### Automated Tests
- Run `./gradlew :app:processDebugResources` to verify that AAPT no longer fails with "resource not found".
- Run a full build: `./gradlew assembleDebug`.

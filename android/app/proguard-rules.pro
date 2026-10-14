# The app is a thin shell around android-browser-helper: the activities subclass its
# classes and Android instantiates them by name from AndroidManifest.xml, so keep
# every android-browser-helper entry point reachable by reflection.
-keep class com.google.androidbrowserhelper.** { *; }
-keep class com.meetbeatz.app.** { *; }

# AndroidX Browser / Trusted Web Activity plumbing is reached through the framework.
-keep class androidx.browser.** { *; }

# Kotlin metadata and coroutines are not used directly, but the stdlib is kept so
# reflection-based callers (Chrome's delegation binder) behave in release builds too.
-keep class kotlin.Metadata { *; }

# Annotations are read at runtime by Google's libraries.
-keepattributes *Annotation*, InnerClasses, Signature, EnclosingMethod

# Optional dependencies of Guava (shipped by android-browser-helper) that are not on
# the classpath in this app. R8 only needs telling that their absence is expected.
-dontwarn org.jetbrains.annotations.**
-dontwarn javax.annotation.**
-dontwarn javax.lang.model.**
-dontwarn com.google.errorprone.annotations.**
-dontwarn com.google.j2objc.annotations.**
-dontwarn java.lang.management.**
-dontwarn sun.misc.**
-dontwarn org.checkerframework.**
-dontwarn com.google.common.util.concurrent.**
-dontwarn org.codehaus.mojo.**
-dontwarn org.jspecify.annotations.**

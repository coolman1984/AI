# MM Core - Android app (Google Play)

A small native Android app (Java, no third-party libraries except the Google Play services
code scanner) that shows the live dashboard of **MM Core Mobile** (`mobile/` in this repository).

- First start: "Scan QR code" (no camera permission needed) or type the address of the PC.
- Then the dashboard of the PC is shown full screen; it updates live (Server-Sent Events).
- Only the paired PC is opened inside the app; other links go to the browser.
- No connection: "Try again" / "Scan a new QR code". Inside the dashboard the footer link
  "Connect to another PC" scans again.

## Build

Needs JDK 17+ and the Android SDK (platform 36, build tools 36).

```
cd android
echo "sdk.dir=/path/to/android-sdk" > local.properties
./gradlew assembleRelease bundleRelease
```

- `app/build/outputs/apk/release/app-release.apk` - install directly on a phone
- `app/build/outputs/bundle/release/app-release.aab` - upload to Google Play

Release signing: create `android/keystore.properties` (never commit it) with

```
storeFile=keystore.jks
storePassword=...
keyAlias=mmcore
keyPassword=...
```

and put the upload key `keystore.jks` next to it. Keep a safe copy of both: every update of
the app on Google Play must be signed with the same upload key (Play App Signing can reset a
lost upload key through Google support).

Before each new release raise `versionCode` (and `versionName`) in `app/build.gradle`.

## Google Play

See `play/STORE_LISTING.md` (texts, data safety, content rating) and `play/PRIVACY_POLICY.md`.

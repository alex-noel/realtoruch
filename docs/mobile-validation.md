# Mobile links and validation

Realtoruch uses the same link parser for the web app and the native app. The native app reads its initial URL through React Native Linking and listens for URL events until the root screen unmounts. A notification click goes through the same listing action. The web app reads incoming URLs on page load and receives warm notification clicks through the service worker.

## Link formats

Use the public HTTPS app origin for web links. The matching native custom scheme uses the same query or fragment after `realtoruch:///`.

| Root query or fragment | Destination |
| --- | --- |
| `?listing=<id>` | Public rental detail. Existing listing email and web push format. |
| `?advert=<id>` | Public owner advert, resolved to its canonical rental detail. |
| `?saved_listing=<id>` | Saved rental detail after sign-in and a check that the canonical home is saved by that account. Delisted favorites remain available here. |
| `?notifications=1` | Notifications after sign-in. |
| `#verify_account=<token>` | Verify the account email. |
| `#reset_password=<token>` | Open the new-password form. |
| `#confirm_email=<token>` | Confirm email alerts and show Notifications. |
| `#unsubscribe_email=<token>` | Turn off email alerts and show Notifications. |

Listing IDs may contain up to 36 ASCII letters, digits, underscores or hyphens. Account tokens use 20–128 URL-safe characters, and alert tokens use 32–128. Each link accepts one action. Token fragments are removed from the web URL during handling, including rejected fragments. The app holds a protected destination as a typed route and optional ID while signing in. In-flight and completed token actions are tracked in memory during the current app lifecycle. Transient errors allow explicit retry or reopening after leaving the action.

The API resolves listing aliases. An authenticated detail opening uses the same seen action as an ordinary listing card. Discovery continues to exclude delisted homes.

## Build configuration

| Setting | Use |
| --- | --- |
| `EXPO_PUBLIC_API_URL` | Public rental API. The local example points to localhost port 8000. |
| `EXPO_PUBLIC_AUTH_URL` | Auth service. The local example points to localhost port 8001. |
| `EXPO_PUBLIC_WEB_URL` | HTTPS app origin accepted by the native parser. Match backend `PUBLIC_WEB_URL`. Leave empty for local custom-scheme testing. The browser also accepts its own HTTPS origin or a loopback HTTP origin. |
| `EXPO_PUBLIC_LINK_SCHEME` | Registered custom scheme. Defaults to `realtoruch`. Use the same setting for app config and bundling. |
| `EXPO_PUBLIC_MAP_TILE_URL` | Raster tile URL for web maps. Isolated browser runs use a local tile. |
| `GOOGLE_MAPS_ANDROID_API_KEY` | Android Maps client key restricted to the app's Android package and signing certificate. Leave empty for JS export validation. |

Treat Expo public variables and the Android Maps client key as visible to users of the build. Use HTTPS for deployed API and auth origins. When testing an installed app against a local service, set reachable development addresses for API and auth.

## Local JS checks

Use the locked dependencies and supported Node version. From the repository root, `python3 scripts/mobile_check.py --help` lists the prerequisite report options. Run the Expo commands from `apps/mobile` with the placeholder values in `.env.example` and a private output directory. The [native bundle commands in the local verification guide](testing.md#ci) also work here.

```sh
set -a
. ./.env.example
set +a
export CI=1 EXPO_OFFLINE=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DOTENV=1
npm run typecheck
npm run test:unit -- linking session
npm exec --offline -- expo config --type public --json
npm exec --offline -- expo export --platform ios --platform android --output-dir /path/to/private-output
```

Expect a bundle for each platform and export metadata. These checks compile JavaScript and inspect resolved app config. The browser suite exercises the responsive web app with isolated auth, synthetic API fixtures and local file mail.

## Installed build checks for T22

A new custom scheme requires a new development build. With that build installed, use the configured scheme on both iOS and Android. Test a public listing from a closed app, repeat it in a running app, open Notifications while signed out and verify that sign-in resumes the destination. Open a saved delisted home through an alias and confirm the canonical detail and seen action. Use local synthetic account and alert links to verify fragment handling and retry. Keep test tokens in the run's private artifacts.

For example, substitute a fixture listing ID before running these on the installed development builds.

```sh
npx uri-scheme open 'realtoruch:///?listing=<id>' --ios
npx uri-scheme open 'realtoruch:///?listing=<id>' --android
```

Universal Links and Android App Links require a user-supplied domain and the corresponding iOS and Android association files. No domain has been supplied. Association and installed-device validation are deferred to T22. [Expo incoming-link documentation](https://docs.expo.dev/linking/into-your-app/).

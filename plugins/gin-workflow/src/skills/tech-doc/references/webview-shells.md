# WebView shell scouting

Use this reference when the code area is an Android or iOS app that loads server pages in a WebView. The app is a shell: its screens are server routes. Tag notes `features` (for `02-FEATURES.md`) and `routes` (for `05-API.md`). Every note carries `file:line`.

## Android

- Search `WebView.loadUrl`, `loadData`, and `loadDataWithBaseURL`. Record the URL or the base URL each screen loads.
- Resolve base URLs from `BuildConfig` fields, `build.gradle` build types, and resource strings; record each variant value.
- Search `addJavascriptInterface` and the `@JavascriptInterface` methods on the bound object. Each method is a bridge method.
- Search `shouldOverrideUrlLoading` and record the URL schemes it intercepts and what it does with them.

## iOS

- Search `WKWebView` and `load(URLRequest)` or `loadHTMLString`. Record the URL or the base URL each screen loads.
- Resolve base URLs from `Info.plist`, `.xcconfig` files, or a configuration type; record each variant value.
- Search `WKScriptMessageHandler`, `add(_:name:)` on the user content controller, and `window.webkit.messageHandlers.<name>.postMessage` in the web code. Each handler name is a bridge method.
- Search `decidePolicyFor` in `WKNavigationDelegate` and record the URL schemes it intercepts.

## Records

- `02-FEATURES.md` row: the app screen (activity, fragment, or view controller), the server URL it loads, and a link to the matching `05-API.md` route, with `file:line`.
- `05-API.md` row for each bridge method, listed as an app-side API: method name, direction (web to app, or app to web), payload fields, `file:line`.
- A loaded URL with no route declaration in the scouted server code goes to the coverage gaps of `02-FEATURES.md`.
- A URL built at runtime from user data is recorded with its pattern and marked as inference.

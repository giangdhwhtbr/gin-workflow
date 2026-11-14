---
id: jvm-templates
tier: framework
applies_to: ["**/*.jsp", "**/*.jspf", "**/*.tag", "**/*.vm"]
detect: {files_exist: [src/main/webapp/WEB-INF/web.xml, WebContent/WEB-INF/web.xml, WEB-INF/web.xml], build_file_mentions: [velocity, jstl]}
---
- [critical] `escape-output`: Escape every dynamic value for its context: HTML with <c:out> or fn:escapeXml in JSP and $esc.html in Velocity; JavaScript with $esc.javascript in Velocity and a JS encoder in JSP (e.g. OWASP Encoder Encode.forJavaScript); URLs with <c:url>/<c:param> in JSP and $esc.url in Velocity. ${...} in JSP template text and $var in Velocity are not escaped; $esc exists only when EscapeTool is configured in the Velocity tools.
- [high] `no-logic-in-views`: Keep views free of business logic, database queries, and scriptlets; compute and format all view models in the controller or action before rendering.
- [high] `csrf-token`: Include a valid CSRF token hidden input or header in every state-changing HTML form and asynchronous request.
- `no-internal-data`: Never render credentials, internal system identifiers, or raw exception stack traces in templates accessible to browsers or WebView shells.

## Why
- `escape-output`: Unescaped dynamic expressions in JSP EL and Velocity templates lead directly to cross-site scripting vulnerabilities.

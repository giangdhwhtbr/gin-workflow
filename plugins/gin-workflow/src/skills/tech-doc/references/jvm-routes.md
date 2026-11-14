# JVM route scouting

Use this reference when the code area is Java, Kotlin, or Groovy on the JVM. Find each route declaration by stack, then tag notes `routes` (for `05-API.md`) and `features` (for `02-FEATURES.md`). Every note carries `file:line`. A repository can mix stacks; scout each one present.

## Spring

Routes are declared by annotations and by `RouterFunction` beans.

- Search `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, and `@PatchMapping`. Join a class-level prefix to each method path.
- `@RestController` methods return a body. `@Controller` methods return a view name; resolve it through the view resolver to the template.
- Search `RouterFunction` and `RouterFunctions.route` for functional routes.
- `05-API.md` row: HTTP method, full path, controller class and method, request and response type, auth if declared, `file:line`.
- `02-FEATURES.md` row: the feature the route serves, the template or screen that renders or calls it, and the `05-API.md` row it matches.

## JAX-RS

- Search `@Path` on classes and methods; join class path and method path.
- Methods carry `@GET`, `@POST`, `@PUT`, `@DELETE`, or `@PATCH`. Record `@Produces` and `@Consumes` as media types.
- Find the `Application` subclass and its `@ApplicationPath` for the base path. Without a subclass, check `web.xml` for the JAX-RS servlet mapping.
- `05-API.md` row: method, base path plus class path plus method path, resource class and method, media types, `file:line`.
- `02-FEATURES.md` row: the feature, and the caller if one exists in the repository.

## Struts 1

- Read `struts-config.xml`. Each `<action path>` is a route; record its `type` (Action class), `name` (form bean), and `input`.
- Each `<forward>` (local or global) names the page or action rendered next. Record the forward name and target.
- Check `web.xml` for the `ActionServlet` `<servlet-mapping>` (`*.do` or a prefix) to build the full URL.
- `05-API.md` row: URL, Action class, form bean, forwards with their templates, `file:line`.
- `02-FEATURES.md` row: the screen reached through the forwards and the form that posts to the action.

## Struts 2

- Read `struts.xml`. Each `<action name>` is a route; record its `class`, `method`, and package namespace.
- Each `<result>` names the view. Record the result `type`; `type="velocity"` points to a `.vm` template.
- Search `@Action` and `@Result` annotations for convention-based routes.
- Check `web.xml` for the Struts filter and its URL pattern (`/*` or `*.action`).
- `05-API.md` row: namespace plus action name, action class and method, results with their templates, `file:line`.
- `02-FEATURES.md` row: the screen the result renders and the form or link that calls the action.

## Servlet and JSP

- Read `web.xml`. Each `<servlet-mapping>` joins a `<url-pattern>` to a `<servlet-name>`; resolve it to its `<servlet-class>`.
- Search `@WebServlet` and `@WebFilter` for annotation-declared routes.
- JSP pages under the web root are reachable by URL unless under `WEB-INF`. List each reachable page.
- Follow form `action` targets, `jsp:include`, `jsp:forward`, `RequestDispatcher.forward`, and `sendRedirect` to find the next route.
- `05-API.md` row: URL pattern, servlet class or JSP path, HTTP methods handled (`doGet`, `doPost`), `file:line`.
- `02-FEATURES.md` row: the JSP that renders the screen, the forms that post to the route, and the redirects that follow.

## Velocity

Velocity is the only template engine in scope. Other engines are noted as uncertain, not scouted.

- Find `VelocityViewServlet` in `web.xml` and its mapping, such as `*.vm`. A mapped template is reachable by URL.
- For Spring, read the `VelocityViewResolver` bean and record its `prefix` and `suffix`; join them to each returned view name.
- For Struts 2, collect `type="velocity"` results from `struts.xml`.
- Follow `#parse` and `#include` to record which templates compose a screen.
- In each `.vm` file, collect form `action` values and `href` values; each one is a route to match against the declarations above.
- `05-API.md` row: the route and its controller or servlet, with the `.vm` template that renders it, `file:line`.
- `02-FEATURES.md` row: the screen composed from the template and its parsed parts, and the routes its forms and links call.

## Matching

Each route row names the controller, action, or servlet and the template that renders it, with `file:line`. A form action or link with no matching declaration goes to the coverage gaps of `02-FEATURES.md`. A declaration with no caller stays in `05-API.md`.

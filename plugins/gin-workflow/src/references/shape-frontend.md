# Shape: Frontend

Apply on top of the `execute` or `quick` rules when the change touches UI code.

- **Components:** one responsibility per component; keep data fetching, state, and presentation separable; follow the existing folder and naming pattern.
- **State ownership:** keep state local first and lift it only when it is shared; server state goes through the project's existing data layer (query client, store, loader), not ad hoc fetches.
- **Accessibility:** semantic elements, labelled form controls, visible keyboard focus and a reachable tab order, alt text for meaningful images.
- **Strings:** no hardcoded user-facing strings when the project has i18n.
- **Security:** no secrets, tokens, or private endpoints in client code or bundles.
- **Tests:** test behavior through the rendered UI (what the user sees and does), not implementation details.
- **Strict rigor:** run a visual check (for example a Playwright screenshot) when the project configures one.

<!-- leaf 266, 9 members -->

This group documents a Flask-Admin configuration layer (Apache 2.0, Province of British Columbia) for a payment/fee system. It has a secured base view, one admin view per model, a hidden index view, a barrel file that re-exports the views, and a parametrized test.

## Base and infrastructure
- **SecuredView** wraps Flask-Admin's `ModelView` with Keycloak auth.
  - The constructor takes `view_role='admin_view'` and `edit_role='admin_edit'`.
  - `is_accessible()` calls `_has_role()`. `can_create` and `can_edit` are gated by the edit role.
  - `inaccessible_callback()` redirects to the Keycloak login if the user isn't connected. Otherwise it returns the plain string 'not authorized'.
  - Fixed settings: `can_export=False`, `can_delete=False`, `can_set_page_size=True`.
- **IndexView** overrides `is_visible()` to return False, which hides the admin index from the menu.
- **Barrel file** re-exports `CodeConfig`, `CorpTypeView`, `DistributionCodeView`, `FeeCodeView`, `FeeScheduleView` and `IndexView`.

## Model views
Each view extends `SecuredView` and is instantiated as `XView = XConfig(Model, db.session)`.

**Simple code-table pattern** (`CodeConfig`, `CorpTypeConfig`, `FeeCodeConfig`):
- Columns are `code` plus `description` (or `amount` for `FeeCode`). They are sorted by `code`, and `CodeConfig` and `CorpTypeConfig` are searchable.
- `on_form_prefill()` makes `code` readonly.
- Variations:
  - `CorpTypeConfig`'s form also includes BCOL fee codes (full, no and partial service, staff), an online banking flag and product mapping.
  - `CodeConfig` is generic and is used for `FilingType`.

**DistributionCodeConfig:**
- List columns: name, client, responsibility_centre, service_line, stob, project_code, start_date, end_date. Search also covers `stop_ejv`. Sorting is by name only.
- The form adds service fee and disbursement distribution codes and an account. The account query is filtered to `PaymentAccount.payment_method == 'EJV'`.
- The edit form disables the account field.
- `on_model_change` sets `created_by='SYSTEM'` if it is null. On create, it also sets `updated_by='SYSTEM'`.

**FeeScheduleConfig:**
- List columns: corp_type_code, filing_type_code, fee, future_effective_fee, priority_fee, service_fee, variable. It is searchable by corp type and filing type, and sorted by corp_type_code.
- The create form adds fee_start_date, fee_end_date and distribution_codes. The edit form is restricted to corp/filing, fee dates, fees and distribution.
- `_change_labels()` injects prefix hints into form labels: EN (filing), FUT (future effective), PRI (priority), TRF (service).

## Tests
`test_view_configs(db, model, config)` runs over five pairs: (FeeCode, FeeCodeConfig), (CorpType, CorpTypeConfig), (FilingType, CodeConfig), (DistributionCode, DistributionCodeConfig) and (FeeSchedule, FeeScheduleConfig). For each pair it instantiates the config and asserts that every column from `list_columns()` is in `config.column_list`.

Caution:
- **`DistributionCodeConfig`:** `stop_ejv` is listed twice in `form_columns`. This is likely a copy-paste error that could break form rendering.
- **Readonly `code`:** `code` is readonly in the `CodeConfig`, `CorpTypeConfig` and `FeeCodeConfig` forms, so existing codes can't be edited. It is enforced client-side via `render_kw`, not by server-side validation. The `id` parameter in `on_form_prefill` shadows the Python builtin (pylint disabled), which is a Flask-Admin convention but error-prone.
- **`FeeScheduleConfig`:** the EN/FUT/PRI/TRF prefixes are UI-only labels, with no validation behind them.
- **`SecuredView`:** the `connected` flag assumes one redirect triggers login. Later denials return a plain 'not authorized' string, not a proper error response.

## Members

- sbc-pay: pay-admin/admin/views/__init__.py
- sbc-pay: pay-admin/admin/views/code.py
- sbc-pay: pay-admin/admin/views/corp_type.py
- sbc-pay: pay-admin/admin/views/distribution_code.py
- sbc-pay: pay-admin/admin/views/fee_code.py
- sbc-pay: pay-admin/admin/views/fee_schedule.py
- sbc-pay: pay-admin/admin/views/index.py
- sbc-pay: pay-admin/admin/views/secured_view.py
- sbc-pay: pay-admin/tests/unit/test_views.py

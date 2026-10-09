<!-- leaf 47, 8 members -->

This set is a family of small Jinja2 email templates for BC Business Registry restoration filings. Most are thin child templates that extend a shared parent and override one or two blocks. The inheritance chain is `common/base_template.jinja2` → `RES-common.jinja2` → `RES-PAID` / `RES-COMPLETED` → per-filing-type templates.

## Groupings

**1. Base and common layers (structure only)**
- `common/base_template.jinja2` sets the title block "You have successfully filed your restoration with the BC Business Registry." It includes `business-information-block.jinja2` and the static text "The following documents are attached to this email:" and "These documents are also available through your BC Business Registry account." It leaves the `attachments` and `after_processing` blocks empty for child templates to fill.
- One template extending `RES-common.jinja2` sets the same "successfully filed your restoration" page title. It lists Notice of Articles and Certificate of Restoration as outputs after processing, and its attachments block is empty.

**2. Completion templates (extend `RES-COMPLETED` or `RES-common`)**
- Restoration completed: page title and title message are both "You have successfully restored your business with the BC Business Registry." Attachments are Notice of Articles and Certificate of Restoration.
- Extension completed (extends `RES-COMPLETED.jinja2`): page title and title message are both "You have successfully extended the period of restoration with the BC Business Registry."

**3. Payment-received (PAID) templates**
Each extends `RES-PAID.jinja2` and overrides only the `attachments` block with a two-item list. The second item is always "Receipt". The first item varies by filing type:
- Full Restoration Application
- Limited Restoration Application
- Limited Restoration Extension Application
- Conversion to Full Restoration Application

## Caution:
- The `page_title` and `title_message` blocks are identical in the completed templates. This is boilerplate duplication, and it's worth checking whether they were meant to differ.
- The `RES-common` filing template has an explicitly empty attachments block that likely needs content.
- The base template's `attachments` and `after_processing` blocks are intentionally empty placeholders for child templates.
- The PAID overrides contain no conditionals or dynamic data. Verify that `RES-PAID.jinja2` defines an `attachments` block and renders it as a list. If it doesn't, the override will silently replace it or have no effect.
- The Limited Restoration PAID template has no content beyond the block override, so its output depends entirely on the parent.

## Members

- lear: queue_services/entity-emailer/src/entity_emailer/email_templates/RES-COMPLETED.jinja2
- lear: queue_services/entity-emailer/src/entity_emailer/email_templates/RES-PAID.jinja2
- lear: queue_services/entity-emailer/src/entity_emailer/email_templates/RES-common.jinja2
- lear: queue_services/entity-emailer/src/entity_emailer/email_templates/RES-fullRestoration-PAID.jinja2
- lear: queue_services/entity-emailer/src/entity_emailer/email_templates/RES-limitedRestoration-PAID.jinja2
- lear: queue_services/entity-emailer/src/entity_emailer/email_templates/RES-limitedRestorationExtension-COMPLETED.jinja2
- lear: queue_services/entity-emailer/src/entity_emailer/email_templates/RES-limitedRestorationExtension-PAID.jinja2
- lear: queue_services/entity-emailer/src/entity_emailer/email_templates/RES-limitedRestorationToFull-PAID.jinja2

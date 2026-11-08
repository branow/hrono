# Task: credit control

You are the developer who owns this feature in webERP, from request to a
change you would ship. The business wrote what it wants in `task/brd.md`,
in its own words; it does not know how webERP works inside.

Work out what this feature really needs in webERP to make sense and to
work: what it depends on, what else in the system has to change with it,
what the business did not think to ask for. Decide the open questions the
way a good engineer on this project would. Then build the whole feature,
following how this project does things.

When done, write `NOTES.md` at the repository root: what you built and
where, what else you changed and why, and the decisions you made.


The webERP repository is in the current directory; the task is task/task.md. There is nothing to run against: deliver the change as files. The repository's GitHub issues, pull requests and discussions up to the base date are in github/, one markdown file per thread.

## How you must work: the map first

This project has a map in /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads-fixed: briefs that describe the whole codebase, what each part does, its rules and its flows, in far less text than the code. These are requirements, not suggestions:

1. You MUST read the map before any code. Read root.md, then the brief.md of every area your work touches, then the leaf brief of every part your work touches and of every existing flow your new code works like (how the system already stores, posts, sends, secures or shows the same kind of thing). The listing below names every brief. When a part is not clear from the listing, Grep the map folder, then read the briefs you find in full.
2. You MUST NOT stop after a few briefs. Keep reading until you know, for every part you will change or add, which brief describes it and the rules it states.
3. You MUST take how the system works from the briefs. Do not open source code to learn how something works when a brief describes it. Open source files only to change them, or to confirm one specific claim from a brief.
4. Do not read briefs unrelated to the work.

The map in /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads-fixed, by area. A leaf's brief is <area>/<leaf>/brief.md.
weberp-database-installation-and-upgrade-149: webERP database installation and upgrade
  database-layer-history-in-weberp-pr-issue-threads-on-connect-185
  database-platform-strategy-for-weberp-mysql-vs-mariadb-calcu-164
  weberp-2-9-2-9a-upgrade-script-help-table-text-new-columns-a-14
  weberp-admin-utilities-database-backup-upgrade-scripts-gl-bu-198
  weberp-database-layer-issue-threads-connector-files-installe-179
  weberp-database-migration-scripts-sql-updates-numbered-steps-25
  weberp-database-schema-upgrades-and-installation-issue-threa-175
  weberp-database-update-scripts-sql-updates-numbers-1-7-10-11-26
  weberp-discussion-threads-database-installer-and-upgrade-scr-199
  weberp-foreign-key-constraint-issue-threads-and-the-schema-m-177
  weberp-includes-user-defined-sales-report-sql-builder-form-f-19
  weberp-installer-issues-threads-on-the-install-wizard-and-it-169
  weberp-installer-problems-discussion-threads-174-203-208-310-160
  weberp-mysql-schema-upgrade-scripts-version-2-7-to-3-11-1-38
  weberp-mysql-upgrade-scripts-3-03-4-15-2-source-weberp-sql-m-147
  weberp-pull-request-records-database-upgrade-system-login-re-200
  weberp-release-merge-pull-requests-4-15-to-4-15-2-thread-rec-181
  weberp-sql-upgrade-scripts-3-00-4-03-8-schema-and-data-migra-148
  weberp-threads-discussions-schema-sync-and-column-size-discu-159
  weberp-threads-issues-issue-tracker-records-on-installer-sch-197
  weberp-threads-pull-request-history-documentation-of-merged--196
weberp-finance-and-ledger-area-152: webERP finance and ledger area
  currency-maintenance-and-exchange-rate-auto-update-issue-and-173
  maintenance-pages-for-weberp-gl-account-sections-dashboard-s-70
  suppliercredit-php-supplier-credit-note-entry-validation-and-34
  weberp-api-debtor-transactions-gl-accounts-groups-sections-s-62
  weberp-bank-matching-bank-reconciliation-daily-bank-transact-123
  weberp-commission-calculation-date-period-utilities-gl-accou-57
  weberp-currency-list-page-and-bank-statement-import-mt940-gi-23
  weberp-customer-and-supplier-account-inquiries-plus-po-back--107
  weberp-customer-and-supplier-allocations-special-orders-and-214
  weberp-customerreceipt-php-customer-and-gl-receipt-batch-ent-49
  weberp-fixed-assets-depreciation-item-maintenance-register-a-110
  weberp-general-ledger-master-data-account-groups-gl-accounts-119
  weberp-install-schema-bank-currency-location-payment-method--77
  weberp-manual-gl-payment-and-bank-posting-pages-gl-journal-s-124
  weberp-schema-debtor-gl-payment-term-table-definitions-and-t-146
  weberp-threads-closed-issues-and-merged-pull-requests-on-gl--215
weberp-installer-seed-data-schema-build-ci-and-project-histo-150: webERP installer, seed data, schema, build/CI and project-history area
  company-logo-stock-image-and-logo-display-issue-threads-for--168
  dependency-management-build-ci-and-test-infrastructure-pull--191
  fixed-asset-label-shipping-and-edi-tables-schema-definitions-80
  fixes-to-weberp-s-manual-pages-and-api-include-structure-iss-167
  issue-thread-topic-print-pdf-and-display-bug-reports-in-webe-239
  issue-tracker-threads-of-weberp-weberp-threads-issues-discus-230
  pdf-generation-tcpdf-dompdf-migration-and-related-issue-thre-231
  pull-requests-on-gettext-translation-support-in-weberp-polyf-195
  repository-housekeeping-pull-requests-weberp-threads-pulls-m-233
  topic-weberp-discussion-issue-and-pull-request-threads-gl-224
  weberp-build-scripts-release-database-dump-translations-chec-29
  weberp-ci-workflow-github-workflows-ci-yaml-test-matrix-envi-18
  weberp-code-maintenance-pull-requests-2025-cleanup-and-refac-192
  weberp-community-discussions-weberp-threads-discussions-anno-155
  weberp-configuration-and-session-change-threads-pull-request-206
  weberp-developer-policy-threads-coding-style-includes-and-pa-178
  weberp-discussion-threads-design-questions-rules-and-open-is-225
  weberp-discussion-threads-ui-themes-logo-print-css-and-respo-158
  weberp-discussions-architecture-coding-standards-tooling-and-161
  weberp-discussions-database-updates-maintenance-mode-and-ses-166
  weberp-email-delivery-smtp-phpmailer-migration-discussions-a-157
  weberp-encoding-and-charset-hygiene-prs-bom-removal-charset--190
  weberp-gitignore-change-history-pull-requests-264-265-299-36-189
  weberp-include-path-refactoring-pull-request-discussions-520-193
  weberp-includes-database-connection-session-login-bootstrap--50
  weberp-includes-image-tags-installer-functions-and-pos-data--43
  weberp-install-schema-base-tables-source-weberp-install-sql--78
  weberp-install-schema-geocode-mrp-and-fiscal-period-tables-31
  weberp-install-seed-data-config-currencies-product-spec-grou-9
  weberp-install-seed-data-menu-items-module-list-and-transact-10
  weberp-install-sql-table-definitions-audit-dashboard-securit-76
  weberp-installer-chart-of-accounts-seed-files-install-sql-co-5
  weberp-installer-sql-files-database-dump-tooling-and-related-183
  weberp-installer-wizard-install-index-php-install-pages-page-4
  weberp-issue-threads-login-session-install-defaults-menu-and-170
  weberp-issue-threads-manufacturing-work-orders-boms-menus-sa-228
  weberp-issue-threads-security-tokens-token-role-script-termi-174
  weberp-issue-tracker-threads-version-numbering-smtp-schema-c-208
  weberp-localisation-and-manual-tools-google-item-description-213
  weberp-login-session-and-security-discussion-issue-and-pull--220
  weberp-project-history-pull-request-threads-code-cleanup-doc-203
  weberp-prs-156-158-181-182-183-184-and-199-one-feature-bundl-188
  weberp-pull-request-records-redirects-rootpath-reportrunner--234
  weberp-pull-request-threads-code-architecture-cli-access-and-210
  weberp-pull-requests-page-start-cleanup-header-markup-fixes--194
  weberp-repository-root-project-configuration-packaging-metad-211
  weberp-seed-data-system-settings-config-menu-items-menuitems-8
  weberp-shared-includes-formatting-locale-pdf-commission-emai-58
  weberp-sql-demo-sql-demo-database-data-fixture-insert-only-s-7
  weberp-test-harness-installer-anonymous-logged-in-page-acces-15
  weberp-tests-setup-test-environment-provisioning-scripts-and-16
  weberp-threads-discussions-266-367-498-583-and-668-company-t-165
  weberp-threads-discussions-bug-reports-and-design-threads-19-162
  weberp-threads-discussions-development-process-branching-lab-163
  weberp-threads-discussions-installer-php-config-manual-api-e-204
  weberp-threads-discussions-issues-and-pull-requests-z-utilit-222
  weberp-threads-discussions-project-governance-tooling-docume-207
  weberp-threads-discussions-user-reported-problems-and-featur-226
  weberp-threads-documentation-translation-and-code-style-disc-212
  weberp-threads-issue-tracker-entries-purchase-orders-goods-r-240
  weberp-threads-issues-bug-reports-feature-requests-and-schem-238
  weberp-threads-issues-date-format-and-schema-bug-reports-and-171
  weberp-threads-issues-installer-config-documentation-menu-an-229
  weberp-threads-issues-php-8-1-baseline-gettext-polyfill-gett-176
  weberp-threads-pull-requests-for-php-7-4-8-x-8-3-8-5-compati-186
  weberp-threads-pull-requests-merge-records-26-31-36-38-54-59-184
  weberp-threads-pull-requests-merge-records-and-the-ci-automa-180
  weberp-threads-pull-requests-merge-records-no-code-diffs-232
  weberp-threads-pull-requests-merged-feature-bundles-installe-205
  weberp-threads-pull-requests-pr-notes-on-getprice-login-inst-209
  weberp-threads-pull-requests-release-notes-for-the-pdf-login-187
  weberp-threads-pulls-pr-issue-records-for-miscellaneous-webe-182
  weberp-xml-rpc-api-entrypoint-session-bootstrap-login-and-11
  weberpdemo-company-directory-template-files-companies-php-ed-13
weberp-report-writer-printable-reports-and-report-admin-page-153: webERP report writer, printable reports and report/admin pages: area overview
  dashboard-applets-source-weberp-dashboard-per-user-widgets-t-6
  inventory-and-stock-reports-in-weberp-planning-valuation-qua-235
  petty-cash-claiming-expenses-on-a-tab-pcclaimexpensesfromtab-71
  printable-reports-and-documents-pdf-html-ods-output-pages-we-236
  quality-assurance-maintenance-qa-reporting-audit-trail-viewe-96
  report-creator-admin-wizard-reportwriter-step-controller-and-21
  reportwriter-forms-html-form-templates-for-the-report-runner-3
  sales-and-security-reports-scheduled-report-mailers-and-data-217
  weberp-admin-utilities-form-designer-label-templates-new-com-32
  weberp-aged-debtors-aged-suppliers-and-mrp-report-pages-98
  weberp-bom-and-stock-document-reports-bom-listings-indented--237
  weberp-customer-statements-and-related-reports-printcuststat-66
  weberp-difot-and-delivery-differences-reports-weberp-pdfdifo-113
  weberp-financial-and-sales-reports-balance-sheet-profit-and--127
  weberp-financial-statement-report-pages-horizontal-analysis--126
  weberp-general-ledger-reports-inquiries-journal-entry-and-gl-223
  weberp-glcashflowsindirect-php-indirect-method-statement-of--112
  weberp-mrp-calculation-demands-calendar-and-mrp-reports-plus-108
  weberp-petty-cash-reports-tab-report-expense-report-tab-expe-69
  weberp-pickinglist-form-design-companies-weberpdemo-formdesi-12
  weberp-purchasing-and-data-reports-mrp-part-info-price-list--27
  weberp-report-writer-admin-report-builder-steps-5-6-reportcr-22
  weberp-report-writer-report-and-form-runner-index-report-lin-2
  weberp-report-writer-shared-includes-rcfunctions-writeform-w-1
  weberp-reports-and-inquiries-customer-supplier-sales-tax-sto-141
  weberp-reports-inquiries-and-a-gl-cash-flow-setup-footer-122
  weberp-sales-analysis-report-maintenance-report-definitions-89
  weberp-sales-order-and-transaction-print-report-pages-packin-117
  weberp-script-audit-report-bank-account-authority-copy-and-q-97
  weberp-user-role-and-access-maintenance-pages-gl-bank-accoun-219
  work-order-shipping-label-and-purchase-order-pdf-printing-we-116
weberp-sales-purchasing-stock-manufacturing-master-data-repo-151: webERP: sales, purchasing, stock, manufacturing, master data, reporting, API and install
  contracts-weberp-contract-set-up-bom-costing-close-out-quota-63
  currency-smtp-shop-and-system-parameter-maintenance-pages-we-41
  fixed-asset-locations-inventory-locations-and-location-user--114
  install-schema-weberp-table-definitions-assets-bom-contracts-145
  inventory-fixed-asset-and-gl-posting-setup-pages-categories--109
  pricing-discount-and-gl-posting-maintenance-pages-weberp-dis-74
  purchase-order-header-authorisation-and-supplier-ordering-pa-95
  selectcustomer-php-customer-search-selection-and-customer-me-87
  supplier-master-factor-companies-and-geocoding-weberp-factor-86
  supplier-side-database-tables-in-weberp-schema-only-144
  tax-authorities-tax-authority-rates-and-tax-groups-maintenan-121
  timesheets-and-fixed-asset-maintenance-scheduling-weberp-30
  utilities-csv-import-of-customers-debtors-and-branches-and-s-55
  weberp-admin-csv-importers-chart-of-accounts-fixed-assets-gl-56
  weberp-admin-utilities-stock-quantity-csv-export-company-tem-33
  weberp-api-include-library-master-data-sales-order-and-stock-61
  weberp-bill-of-materials-inquiry-maintenance-and-bottom-up-c-103
  weberp-bill-of-materials-single-level-bom-maintenance-page-p-104
  weberp-bom-copy-internal-stock-request-item-search-purchase--64
  weberp-browser-side-scripts-counter-sales-quick-entry-login--46
  weberp-confirmdispatchinvoice-php-confirm-dispatch-and-creat-20
  weberp-controlled-item-serial-batch-entry-pages-picking-list-82
  weberp-counter-returns-the-counterreturns-php-page-and-the-s-42
  weberp-counter-sales-countersales-php-and-company-bootstrap-44
  weberp-credit-note-from-invoice-creditinvoice-php-cart-setup-35
  weberp-credit-notes-entry-screen-posting-and-delete-utility-17
  weberp-customer-transaction-print-and-email-emailcusttrans-p-60
  weberp-customerbranches-php-customer-branch-maintenance-page-91
  weberp-edi-invoice-sending-edi-customer-and-message-format-s-65
  weberp-edi-order-intake-order-confirmation-email-and-csv-exp-24
  weberp-goods-receipt-goodsreceived-php-and-its-linked-pages--51
  weberp-includes-in-memory-transaction-container-classes-cart-67
  weberp-includes-serial-batch-item-entry-and-stock-price-and--68
  weberp-install-schema-accounting-stock-sales-category-tax-an-143
  weberp-install-sql-tables-schema-definitions-for-sales-purch-81
  weberp-maintenance-pages-reference-data-forms-and-z-utility--221
  weberp-master-data-maintenance-pages-customer-contacts-and-n-105
  weberp-order-delivery-details-freight-costs-payment-terms-an-48
  weberp-order-selection-and-search-pages-purchase-orders-comp-88
  weberp-purchasing-grn-reversal-and-supplier-invoice-entry-an-54
  weberp-recurring-sales-orders-template-maintenance-due-order-45
  weberp-sales-category-maintenance-item-selection-search-and--102
  weberp-sales-order-entry-and-item-selection-pages-selectorde-37
  weberp-salesinquiry-php-sales-order-and-invoiced-stock-inqui-79
  weberp-shipments-costing-closing-charges-and-item-cost-updat-59
  weberp-stock-and-sales-internal-request-fulfilment-form-sale-83
  weberp-stock-check-count-sheets-stockcheck-php-and-count-vs--218
  weberp-stock-inquiry-count-reorder-and-maintenance-pages-sou-93
  weberp-stock-item-pages-image-serving-getstockimage-php-manu-73
  weberp-stock-transfers-and-stock-counts-entry-pages-for-loca-85
  weberp-stockloctransferreceive-php-receiving-stock-location--84
  weberp-stocks-php-stock-item-create-update-delete-and-form-d-72
  weberp-supplier-purchasing-data-supplier-price-lists-sell-th-94
  weberp-supplier-side-flows-supplier-selection-offers-receive-92
  weberp-supplier-transaction-grn-pages-grn-selection-for-supp-47
  weberp-supplierinvoice-php-automatic-purchase-order-receivin-53
  weberp-utility-pages-customer-branch-csv-import-zimportcustb-52
  weberp-workorderreceive-php-receiving-finished-output-agains-90
  work-order-pages-in-weberp-entry-serial-batch-numbers-issue--100
  work-order-shipment-purchase-order-picking-list-and-internal-99
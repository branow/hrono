## how is a filing payment processed after the user pays

```
[source] git:///Users/orest/hrono-eval/mirror/sbc-auth/queue_services/account-mailer/src/account_mailer/email_templates/online_banking_over_payment.html@e76103cf7604938dc6074f35a3024af42774f9e1 sp:/.text/.raw[1/1]
We have received payment in the amount of ${{ paid_amount }}. Payment received over the outstanding balance has been applied as a credit to your account and will be applied to future purchases.

[source] git:///Users/orest/hrono-eval/mirror/business-filings-ui/src/views/ConsentAmalgamationOut.vue@6af0a43ed247024f9cfc2cc46092f698e428d9f3 sp:/.~blank-line[64]
    // if this is a staff user clicking File and Pay (not Submit)
    // then detour via Staff Payment dialog
    if (this.isRoleStaff && !fromStaffPayment) {
      this.staffPaymentDialog = true
      return
    }

    this.filingPaying = true



[source] git:///Users/orest/hrono-eval/mirror/business-filings-ui/src/views/ConsentContinuationOut.vue@6af0a43ed247024f9cfc2cc46092f698e428d9f3 sp:/.~blank-line[64]
    // if this is a staff user clicking File and Pay (not Submit)
    // then detour via Staff Payment dialog
    if (this.isRoleStaff && !fromStaffPayment) {
      this.staffPaymentDialog = true
      return
    }

    this.filingPaying = true



[source] git:///Users/orest/hrono-eval/mirror/business-filings-ui/src/views/StandaloneDirectorsFiling.vue@6af0a43ed247024f9cfc2cc46092f698e428d9f3 sp:/.~blank-line[69]
    // if this is a staff user clicking File and Pay (not Submit)
    // then detour via Staff Payment dialog
    if (this.isRoleStaff && !fromStaffPayment) {
      this.staffPaymentDialog = true
      return
    }

    this.filingPaying = true



[source] git:///Users/orest/hrono-eval/mirror/business-filings-ui/src/views/StandaloneOfficeAddressFiling.vue@6af0a43ed247024f9cfc2cc46092f698e428d9f3 sp:/.~blank-line[61]
    // if this is a staff user clicking File and Pay (not Submit)
    // then detour via Staff Payment dialog
    if (this.isRoleStaff && !fromStaffPayment) {
      this.staffPaymentDialog = true
      return
    }

    this.filingPaying = true



[source] git:///Users/orest/hrono-eval/mirror/lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/.decorated_definition/worker/.block/.comment[6] sp:/.decorated_definition/worker/.block/.assignment[1] sp:/.decorated_definition/worker/.block/.if_statement[7] sp:/.decorated_definition/worker/.block/.comment[7]
logger.info(f"processing payment: {payment_token.id}")

    # setting the payment_completion_date, marks the filing as paid
    filing.payment_completion_date = datetime.now(timezone.utc)
    filing.payment_status_code = "COMPLETED"
    filing.status = Filing.Status.PAID
    filing.save()

    staff_review_required = ["continuationIn"]
    if filing.filing_type in staff_review_required:
        # 4.a. Create staff review for the filing
        create_staff_review(filing)
    else:
        # 4.b. Publish to filer Q, if the filing is not a FED (Effective date > now())
        # ##
        publish_to_filer(filing, payment_token)

    # None of these should bail as the filing has been marked PAID
    # 5. Publish to email Q
    # ##
    publish_to_emailer(filing)

    

[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/DEVELOPER_NOTES.md@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/.section/.paragraph[9] sp:/.section/.paragraph[11] sp:/.section/.paragraph[12]
It's the terminology we use to pay our partners. For example there is EJV disbursement for Ministry partners, we have AP Disbursement (EFT) for Non-Ministry Partners. We debit our internal GL (excluding service fees) and credit an external GL or bank account. 

7. How is the PAY-API spec updated?

Right now it's a manual process.

8. Where is the payment flow documentation? 

There are bits of it everywhere right now, but Louise is building out all of the documentation - will be uploaded to github shortly.

https://github.com/bcgov/sbc-pay/blob/main/docs/docs/architecture/FAS_Intgeration.md
https://github.com/bcgov-registries/documents/blob/main/pay/EJV.md
https://github.com/bcgov-registries/documents/blob/main/pay/PAD.md

Are great starting points.



[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/pay-queue/src/pay_queue/services/payment_reconciliations.py@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/reconcile_payments/.block/.string
"""Read the file and update payment details.

    1: Check to see if file has been processed already.
    2: Parse the file and create a dict per row for easy access.
    3: If the transaction is for invoice,
    3.1 : If transaction status is PAID, update invoice and payment statuses, publish to account mailer.
        For Online Banking invoices, publish message to the payment queue.
    3.2 : If transaction status is NOT PAID, update payment status, publish to account mailer and events to handle NSF.
    3.3 : If transaction status is PARTIAL, update payment and invoice status, publish to account mailer.
    4: If the transaction is On Account for Credit, apply the credit to the account.
    """
    msg = ce.data
    file_name: str = msg.get('fileName')
    

[source] git:///Users/orest/hrono-eval/mirror/business-filings-ui/tests/unit/StandaloneDirectorsFiling.spec.ts@6af0a43ed247024f9cfc2cc46092f698e428d9f3 sp:/.expression_statement[8]/.call_expression/.arguments/.arrow_function/.statement_block/.expression_statement[5]/.call_expression/.arguments/.binary_expression
('saves a new filing and redirects to Pay URL when this is a new filing and the File & Pay button ' +
    'is clicked - as a BCOMP', async () => 

[source] git:///Users/orest/hrono-eval/mirror/business-filings-ui/src/components/Dashboard/FilingHistoryList/FilingTemplate.vue@6af0a43ed247024f9cfc2cc46092f698e428d9f3 sp:/.~blank-line[3] sp:/.~blank-line[4] sp:/.~blank-line[5] sp:/.~blank-line[6]
        <slot name="actions">
          <HeaderActions
            :filing="filing"
            :index="index"
          />
        </slot>
      </div>
    </v-expansion-panel-header>

    <v-expansion-panel-content
      eager
      class="pt-5"
    >
      <slot name="body">
        <!-- is this a generic paid (not yet completed) filing? -->
        <div
          v-if="isStatusPaid || isStatusApproved"
          class="body-2"
        >
          <h4>Filing Pending</h4>

          <p>
            This {{ title }} is paid, but the filing has not been completed by the Business Registry
            yet. Some filings may take longer than expected.
          </p>

          <p v-if="fileNumber">
            Court Order Number: {{ fileNumber }}
          </p>



```

## where are the account membership roles checked

```
[summary] node://hrono/nodes/432/this-is-a-set-of-condensed-notes-on-the-pytest-suites-for-an@a2bc0ffc25921028c0ef032a7c9c3f549d7184bd138686e72c4f24f8e1ca33a2 sp:/Groupings/3.%20Auth%20validation%20%28%60check_auth%28%29%60%29
### 3. Auth validation (`check_auth()`)
It has three paths:
- **Basic roles:** Uses `one_of_roles`, `equals_role` and `disabled_roles`.
- **Staff path:** Covers the staff and create_accounts roles, plus the `system_required=True` edge case.
- **System path:** Covers the product_code='ALL' bypass, org membership, and entity affiliation by business_identifier.



[summary] node://hrono/nodes/359/what-this-is-a-set-of-condensed-notes-on-a-python-pytest-tes@a748fe242e29db5e8eb3d4487818e7bff871a193c9570abee6f050079ab207f5 sp:/Auth
## Auth

- `check_auth()` with `PUBLIC_USER_ROLE` has 13 parametrized cases. They combine org_member, entity_affiliated and role checks (equals_role, one_of_roles, disabled_roles).
- The expected outcomes are UnboundLocalError, Forbidden or OK.
- 4 standalone tests cover service accounts (by org_id and by business_identifier), product authorization and an entity with multiple affiliations. A fifth, the invalid CP test, is skipped.

## Caution:


[source] git:///Users/orest/hrono-eval/mirror/sbc-auth/auth-api/src/auth_api/services/authorization.py@e76103cf7604938dc6074f35a3024af42774f9e1 sp:/.decorated_definition/check_auth/.block/.if_statement/.else_clause/.block/.call
_check_for_roles(auth.get('orgMembership', None) if auth else None, kwargs)




[summary] node://hrono/nodes/150/these-condensations-are-fragments-of-an-openapi-spec-and-its@5014feb91923bafe344b56c73790d11e664a9b624088d7bed90fef648634bdb5 sp:/Authorization%20fixtures%20%28account%20id%20%271234%27%2C%20%22Mock%20Account%22%29/.list/.list_item[2]
- **Authorizations response schema example**
  - It is a `PREMIUM` account with ADMIN membership, `preferred_payment` PAD, and null BC Online IDs and business fields.
  - It lists a broad role set of about 15 permissions: remove_business, change_address, invite_members, reset_password, manage_statements, generate_invoice and others.



[source] git:///Users/orest/hrono-eval/mirror/sbc-auth/auth-api/src/auth_api/utils/role_validator.py@e76103cf7604938dc6074f35a3024af42774f9e1 sp:/status%20as%20http_status
from auth_api import status as http_status


def validate_roles(**role_args):
    

[source] git:///Users/orest/hrono-eval/mirror/sbc-auth/auth-api/src/auth_api/services/user.py@e76103cf7604938dc6074f35a3024af42774f9e1 sp:/.decorated_definition/User/.block/.decorated_definition[31]
@staticmethod
    def is_user_admin_or_coordinator(user, org_id: int) -> bool:
        """Check if user(userservice wrapper) provided is admin or coordinator for the given org id."""
        current_user_membership: MembershipModel = \
            MembershipModel.find_membership_by_user_and_org(user_id=user.identifier, org_id=org_id)

        if current_user_membership is None:
            return False

        if current_user_membership.status != Status.ACTIVE.value:
            return False

        return current_user_membership.membership_type_code in CLIENT_ADMIN_ROLES


[summary] node://hrono/nodes/265/what-this-is-a-set-of-condensed-summaries-of-a-keycloak-real@08cf7df86f25532c5c909975da04c2cdeeed6300ab3d0d5889f860a9357a973f sp:/Groups%20and%20defaults
## Groups and defaults
| Group | Realm roles |
|---|---|
| admins | canEdit, canView |
| users | canView |
| public_users | edit, public_user |
| account_holders | account_holder |

- Each group has empty attributes, clientRoles and subGroups.
- defaultRoles are offline_access and uma_authorization.
- defaultGroups is /users only.
- The only requiredCredential is password.



[source] git:///Users/orest/hrono-eval/mirror/sbc-auth/auth-api/src/auth_api/utils/user_context.py@e76103cf7604938dc6074f35a3024af42774f9e1 sp:/UserContext/.block/has_role sp:/UserContext/.block/is_staff sp:/UserContext/.block/is_staff_admin sp:/UserContext/.block/is_system sp:/UserContext/.block/is_bceid_user
def has_role(self, role_name: str) -> bool:
        """Return True if the user has the role."""
        return role_name in self._roles

    def is_staff(self) -> bool:
        """Return True if the user is staff user."""
        return Role.STAFF.value in self._roles if self._roles else False

    def is_staff_admin(self) -> bool:
        """Return True if the user is staff user."""
        return Role.STAFF_CREATE_ACCOUNTS.value in self._roles if self._roles else False

    def is_system(self) -> bool:
        """Return True if the user is system user."""
        return Role.SYSTEM.value in self._roles if self._roles else False

    def is_bceid_user(self) -> bool:
        """Return True if the user is BCEID user."""
        return self._login_source == LoginSource.BCEID.value

    

[source] git:///Users/orest/hrono-eval/mirror/sbc-auth/auth-web/src/components/auth/mixins/AccountMixin.vue@e76103cf7604938dc6074f35a3024af42774f9e1 sp:/.~blank-line[6]
  get isSbcStaffAccount (): boolean {
    return this.currentOrganization?.orgType === Account.SBC_STAFF
  }
}
</script>


[summary] node://hrono/nodes/473/this-is-a-set-of-condensed-notes-on-about-30-vue-components-@74669bf442ce68f3becf75114f2e7acdfb2f346c5e2717cb84dce76f60c536f0 sp:/Groupings/.list[3] sp:/Groupings/.list[4]
- **Success pages**: AccountCreationSuccessView (two variants, one with Home and team buttons and one a "pending" clock-icon page), NonBcscAccountCreationSuccessView and SetupAccountSuccessView.
- **PendingApprovalView**: three paths (GVM user, denied, pending).
- **Access-denied pages**: RestrictedProductView and two UnauthorizedView variants. One variant offers Terms of Use and Log out. The other offers Homepage and, for staff, Contact Support.

**5. Account management**
- **Deactivation flow**: confirmation checklist, then confirm, success and error modals.
- **Account settings page**: a role-gated navigation drawer, with Manage Account and Account Activity sections and two alert banners.

**6. Staff tools**


```

## how does the COLIN sync of filings work

```
[source] git:///Users/orest/hrono-eval/mirror/lear/.github/workflows/update-colin-filings-ci.yml@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/.document/.block_node/.block_mapping/name sp:/.document/.block_node/.block_mapping/on sp:/.document/.block_node/.block_mapping/defaults
name: Update Colin Filings Job CI

on:
  pull_request:
    types: [assigned, synchronize]
    paths:
      - "jobs/update-colin-filings/**"

defaults:
  run:
    shell: bash
    working-directory: ./jobs/update-colin-filings

jobs:
  

[summary] node://hrono/nodes/487/this-is-a-set-of-condensed-summaries-of-the-pytest-suite-for@0d16648da39a8440b944dcfea813ed6e57faa256571da90e4be65381425e05ae sp:/API%20endpoint%20tests/.list/.list_item sp:/API%20endpoint%20tests/.list/.list_item[1] sp:/API%20endpoint%20tests/.list/.list_item[2] sp:/API%20endpoint%20tests/.list/.list_item[3]
- **Comments.** Business-level and filing-level comments. The pattern is GET empty/single/multiple, POST requiring `STAFF_ROLE` (`BASIC_USER` gets 401), required-field 422s, and 404s.
- **Filings.** Business filings GET/POST (v1 and v2), the ledger search, and COLIN/NATS queue integration.
  - Filing types covered: alterations (BC↔BEN), court order, registrar's notation and order, and bootstrap IA drafts.
- **Documents and signatures.** `/documents/summary` and `/documents`, document signatures (v1 and v2), and the furnishing document endpoint with its `variant` param.
- **Internal and sync.** COLIN sync endpoints, and the future-effective and `bnmove` internal endpoints.


[summary] node://hrono/nodes/296/this-group-is-a-set-of-condensed-summaries-of-email-template@9958a63acfcbb933bc74c8168d0d401559c8fb84eaa4c92d8b534b2786561428 sp:/.section/.list[1]/.list_item/.paragraph
1. **Corporate filing confirmations** (the main group). Each lists its own attachments and follow-up documents:
   

[summary] node://hrono/nodes/292/this-group-condenses-a-python-filer-service-in-the-bc-regist@b248fd4bcb0948ede63bb92cfd1aeec35ea7388ebb768efe103833f1a38431dd sp:/Groupings/.list/.list_item sp:/Groupings/.list/.list_item[1] sp:/Groupings/.list/.list_item[2]
- **process_filing**: looks up the Filing by `filing_id` and skips it if COMPLETED. It flattens `legal_filings`, creates the versioning transaction, dispatches by filing type, saves `ColinEventId`, then runs affiliation and post-processing. Account-service calls are gated by `config.UPDATE_ENTITY`. It publishes `state=HISTORICAL` on dissolution and `state=ACTIVE` on putBackOn.
- **get_filing_types**: extracts the keys of `legal_filings['filing']` that exist in `Filing.FILINGS`.
- **Routing summary**: a second description of the same flow, covering registration, conversion, changeOfRegistration, dissolution, putBackOn and correction. It uses `versioning_manager` and `ColinEventId`.


[source] git:///Users/orest/hrono-eval/mirror/lear/jobs/update-colin-filings/update_colin_filings.py@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/run/.block/.string
"""Get filings that haven't been synced with colin and send them to the colin-api."""
    application = create_app()
    corps_with_failed_filing = []
    with application.app_context():
        try:
            # get updater-job token
            

[source] git:///Users/orest/hrono-eval/mirror/lear/.github/workflows/update-colin-filings-cd.yml@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/.document/.block_node/.block_mapping/jobs/.block_node/.block_mapping/update-colin-filings-cd-by-push/.flow_node
update-colin-filings-cd-by-push:
    runs-on: ubuntu-20.04

    if: github.event_name == 'push' && github.repository == 'bcgov/lear'
    environment:
      name: "dev"

    steps:
      

[summary] node://hrono/nodes/439/what-this-is-a-set-of-condensed-notes-on-the-test-suites-mos@4a8d446ad8b61ef6baf2350a3fe48eb635014d78fd2bd760aeaf1885cee31f9e sp:/Groupings/.list[2]
**3. Internal and task endpoints**
- **Internal filings (`/internal/filings`):** the COLIN-related tests: get, patch, colin_id, last_update and a future-effective COA.
- **Task list tests:** pending correction and `construct_task_list`, with a v1 and a v2 variant. A conversion-filing task test (v2) is also in the set.
- **Comments endpoint:** v1 and v2 variants, with 404/400/405 checks.

**4. Business, search and documents (v2)**


[source] git:///Users/orest/hrono-eval/mirror/lear/jobs/update-colin-filings/run.sh@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/
cd /opt/app-root
echo 'run update_colin_filings'
python update_colin_filings.py


[summary] node://hrono/nodes/55/what-this-is-a-set-of-condensed-summaries-of-jupyter-noteboo@0cd1ce541f3bed4f531f5096d2576c58ca1a6aae606d064e286dc2bc907e4e07 sp:/Groupings/.list/.list_item[2] sp:/Groupings/.list/.list_item[3]
- *Gazette notebooks (CP/XCP)*: "Filings Daily Stats" appears in two forms.
  - One inserts into `sent_to_gazette` and writes 4 files: COOP_GAZETTE_CHANGEOFNAME, DISSOLUTION, INCORPORATION and RESTORATION.
  - The other runs the 4 matching UPDATE statements that set `sent_to_gazette_date = now()`.
  - Its metadata variant records the kernelspec (Python 3.8.0, nbformat 4.2).
- *BC firms data extracts (SP/GP)*: A "Filings Daily Stats" notebook writes `data/from_openshift.txt`, with state code, legal type, identifier and name. A BCFN_MR notebook builds a fixed-width Master Record file, gzipped as `BCFN_MR_YYYYMMDD_[rowcount].gz`.


[source] git:///Users/orest/hrono-eval/mirror/lear/jobs/update-colin-filings/update_colin_filings.py@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/run/.block/.with_statement/.block/.try_statement/.block/.while_statement/.block/.for_statement/.block/.if_statement/.else_clause/.block/.assignment sp:/run/.block/.with_statement/.block/.try_statement/.block/.while_statement/.block/.for_statement/.block/.if_statement/.else_clause/.block/.if_statement
colin_ids = send_filing(application, token, filing, filing_id)
                        update = None
                        if colin_ids:
                            update = update_colin_id(application, token, filing_id, colin_ids)
                        

```

## how are fees calculated for a filing

```
[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/pay-api/src/pay_api/services/payment_service.py@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/_calculate_fees/.def sp:/_calculate_fees/.identifier sp:/_calculate_fees/.parameters
def _calculate_fees(corp_type, filing_info):
    """Calculate and return the fees based on the filing type codes."""
    fees = []
    service_fee_applied: bool = False
    

[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/pay-api/src/pay_api/resources/v1/fee.py@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/.decorated_definition/get_fee_by_corp_and_filing_type/.def sp:/.decorated_definition/get_fee_by_corp_and_filing_type/.identifier sp:/.decorated_definition/get_fee_by_corp_and_filing_type/.parameters
def get_fee_by_corp_and_filing_type(corp_type, filing_type_code):
    

[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/pay-api/src/pay_api/services/payment_service.py@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/_calculate_fees/.block/.return_statement
if service_fee_applied:
            fee.service_fees = 0
        elif fee.service_fees > 0:
            service_fee_applied = True

        if fee.variable:
            fee.fee_amount = Decimal(str(filing_type_info.get('fee', 0)))

        if filing_type_info.get('filingDescription'):
            fee.description = filing_type_info.get('filingDescription')

        fees.append(fee)
    return fees




[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/pay-api/src/pay_api/services/fee_schedule.py@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/.decorated_definition/FeeSchedule/.block/.decorated_definition[36]/find_by_corp_type_and_filing_type/.block/.string sp:/.decorated_definition/FeeSchedule/.block/.decorated_definition[36]/find_by_corp_type_and_filing_type/.block/.call sp:/.decorated_definition/FeeSchedule/.block/.decorated_definition[36]/find_by_corp_type_and_filing_type/.block/.if_statement sp:/.decorated_definition/FeeSchedule/.block/.decorated_definition[36]/find_by_corp_type_and_filing_type/.block/.assignment[1] sp:/.decorated_definition/FeeSchedule/.block/.decorated_definition[36]/find_by_corp_type_and_filing_type/.block/.if_statement[1]
"""Calculate fees for the filing by using the arguments."""
        current_app.logger.debug(f'<get_fees_by_corp_type_and_filing_type : {corp_type}, {filing_type_code}, '
                                 f'{valid_date}')
        user: UserContext = kwargs['user']

        if not corp_type and not filing_type_code:
            raise BusinessException(Error.INVALID_CORP_OR_FILING_TYPE)

        fee_schedule_dao = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type, filing_type_code, valid_date)

        if not fee_schedule_dao:
            raise BusinessException(Error.INVALID_CORP_OR_FILING_TYPE)

        fee_schedule = FeeSchedule()
        fee_schedule._dao = fee_schedule_dao  # pylint: disable=protected-access
        fee_schedule.quantity = kwargs.get('quantity')

        

[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/pay-api/tests/unit/api/test_fee.py@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/test_calculate_fees_for_service_fee/.def sp:/test_calculate_fees_for_service_fee/.identifier sp:/test_calculate_fees_for_service_fee/.parameters
def test_calculate_fees_for_service_fee(session, client, jwt, app):
    

[summary] node://hrono/nodes/185/this-group-is-a-set-of-condensed-notes-from-a-bc-cp-corporat@fa2e714e0b11e3ab8543470c04b13738c177db97fd9e2204bbc595b8c395a9ff sp:/.section sp:/Fee%20calculation%20schema
This group is a set of condensed notes from a BC/CP corporate-registry payment API. It covers one OpenAPI fee-schema response, several invoice and filing records, and one paginated statements response. Most of the records describe the same fee pattern.

## Fee calculation schema
**OpenAPI Fee response** has these fields: filingFees, filingType, filingTypeCode, futureEffectiveFees, priorityFees, serviceFees, tax (gst, pst) and total.
- CP/OTANN: filingFees 30, serviceFees 0, total 30.
- BC/BCINC: filingFees 350, serviceFees 1.5, total 351.5.
- BC/BCADD: filingFees 20, serviceFees 1.5, total 21.5.
- BC/BCINC with `priority=true&futureEffective=true`: filingFees 350, futureEffectiveFees 100, priorityFees 100, serviceFees 1.5, total 551.5.



[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/docs/databse-schema/tables/fee_item.html@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/html/body/div/div/section[1]/div/div[1]/table/tbody/tr[2]
<tr>
				 <td><span id="filing_fees">filing_fees</span></td>
				 <td>int4</td>
				 <td>10</td>
				 <td title=''></td>
				 <td title=''></td>
				 <td>null</td>
				 <td>
				  <table border='0' cellspacing='0' cellpadding='0'>
				  </table>				 
				 </td>
				 <td>
				  <table border='0' cellspacing='0' cellpadding='0'>
				  </table>					 
				 </td>
				 <td></td>
				</tr>
				

[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/pay-api/src/pay_api/services/payment_service.py@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/_calculate_fees/.block/.for_statement/.block/.call sp:/_calculate_fees/.block/.for_statement/.block/.assignment sp:/_calculate_fees/.block/.for_statement/.block/.comment
current_app.logger.debug(f"Getting fees for {filing_type_info.get('filingTypeCode')} ")
        fee: FeeSchedule = FeeSchedule.find_by_corp_type_and_filing_type(
            corp_type=corp_type,
            filing_type_code=filing_type_info.get('filingTypeCode', None),
            valid_date=filing_info.get('date', None),
            jurisdiction=None,
            is_priority=filing_type_info.get('priority'),
            is_future_effective=filing_type_info.get('futureEffective'),
            waive_fees=filing_type_info.get('waiveFees'),
            quantity=filing_type_info.get('quantity')
        )
        # If service fee is already applied, do not charge again.
        

[source] git:///Users/orest/hrono-eval/mirror/sbc-pay/pay-api/src/pay_api/services/fee_schedule.py@ac82a1c957ebabcfdf13b244a9e0dfbad1d81da0 sp:/.decorated_definition/FeeSchedule/.block/.decorated_definition[36]/find_by_corp_type_and_filing_type/.block/.if_statement[4] sp:/.decorated_definition/FeeSchedule/.block/.decorated_definition[36]/find_by_corp_type_and_filing_type/.block/.if_statement[5] sp:/.decorated_definition/FeeSchedule/.block/.decorated_definition[36]/find_by_corp_type_and_filing_type/.block/.call[1]
if kwargs.get('is_future_effective') and fee_schedule_dao.future_effective_fee and apply_filing_fees:
            fee_schedule.future_effective_fee = fee_schedule_dao.future_effective_fee.amount

        if kwargs.get('waive_fees'):
            fee_schedule.fee_amount = 0
            fee_schedule.priority_fee = 0
            fee_schedule.future_effective_fee = 0
            fee_schedule.service_fees = 0

        current_app.logger.debug('>get_fees_by_corp_type_and_filing_type')
        return fee_schedule

    

[summary] node://hrono/nodes/185/this-group-is-a-set-of-condensed-notes-from-a-bc-cp-corporat@fa2e714e0b11e3ab8543470c04b13738c177db97fd9e2204bbc595b8c395a9ff sp:/Fully%20waived%20filings
## Fully waived filings
These are two "Change of Director" (OTFDR) filings. Both have paymentMethod INTERNAL, quantity 1 and every fee at 0.
- CP1000006 (id 3348, corpTypeCode CP)
- BC1219964 (id 3347, corpTypeCode BC)



```

## what happens when a business is dissolved

```
[source] git:///Users/orest/hrono-eval/mirror/lear/jobs/involuntary-dissolutions/involuntary_dissolutions.py@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/stage_1_process/.block/.string
"""Initiate dissolution process for new businesses that meet dissolution criteria."""
    try:
        # check if batch has already run today
        

[source] git:///Users/orest/hrono-eval/mirror/lear/legal-api/report-templates/template-parts/dissolution/dissolutionStatement.html@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/div/div[2]/.text/.~line[1] sp:/div/div[2]/.text/.~line[2] sp:/div/div[2]/.text/.~line[3] sp:/div/div[2]/.text/.~line[4] sp:/div/div[2]/.text/.~line[6] sp:/div/div[2]/.text/.~line[7] sp:/div/div[2]/.text/.~line[8]
{% if business.legalType == 'CP' %}
            {% if dissolutionStatementType == '197NoAssetsNoLiabilities' %}
                The Cooperative Association has, by special resolution, voluntarily resolved to dissolve
                the Cooperative Association under section 197 of the Cooperative Association Act.
                The Cooperative Association has no assets and has no liabilities.
            {% else %}
                The Cooperative Association has, by special resolution, voluntarily resolved to dissolve the
                Cooperative Association under section 197 of the Cooperative Association Act. The Cooperative
                Association has no assets and has made provision for the payment of each of the Cooperative Association's


[source] git:///Users/orest/hrono-eval/mirror/lear/jobs/furnishings/src/furnishings/stage_processors/post_processor.py@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/XmlMeta/.block/.assignment/.dictionary/Furnishing.FurnishingName.CORP_DISSOLVED
Furnishing.FurnishingName.CORP_DISSOLVED: {
            'title': 'Dissolutions (B.C.)',
            'category': 'DISSOLUTIONS',
            'subcategory': 'B.C.',
            'corp_class': 'BC Company(s)',
            'description': (
                'The Registrar of Companies hereby gives notice the following companies were dissolved under '
                'section 317, 422 or 423 of the Business Corporations Act.'
            )
        },
        

[source] git:///Users/orest/hrono-eval/mirror/sbc-auth/auth-web/src/views/auth/staff/InvoluntaryDissolution.vue@e76103cf7604938dc6074f35a3024af42774f9e1 sp:/.~blank-line[1]/.~line[10] sp:/.~blank-line[1]/.~line[11] sp:/.~blank-line[1]/.~line[12] sp:/.~blank-line[1]/.~line[13]
    <!-- Automated Dissolution Section -->
    <section>
      <v-row>
        <v-col
          cols="12"
          lg="9"
        >
          <header>
            <h2>Automated Dissolution</h2>
            <p class="mt-2">
              You can set up a schedule to automate the involuntary dissolution process.
              The system will prioritize the oldest eligible businesses to move into D1 dissolution,
              automatically saving a list of businesses in each batch to the LAN.
              The schedule will run until there are no more businesses ready for D1 dissolution.
              To pause the schedule, enter a batch size of 0.
            </p>
          </header>
        </v-col>
      </v-row>
      <v-row>
        <v-col
          cols="12"
          lg="9"
        >


[source] git:///Users/orest/hrono-eval/mirror/business-filings-ui/src/resources/GP.ts@6af0a43ed247024f9cfc2cc46092f698e428d9f3 sp:/.export_statement/.lexical_declaration/BusinessConfigGp/.object/obligations/.object
{
        label: 'Dissolving a Sole Proprietorship or Partnership ',
        description: 'when a business is no longer required it needs to be dissolved.'
      }
    ]
  }

[source] git:///Users/orest/hrono-eval/mirror/business-filings-ui/src/resources/SP.ts@6af0a43ed247024f9cfc2cc46092f698e428d9f3 sp:/.export_statement/.lexical_declaration/BusinessConfigSp/.object/obligations/.object
{
        label: 'Dissolving a Sole Proprietorship or Partnership ',
        description: 'when a business is no longer required it needs to be dissolved.'
      }
    ]
  }

[source] git:///Users/orest/hrono-eval/mirror/lear/jobs/involuntary-dissolutions/involuntary_dissolutions.py@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/run/.block/.if_statement
"""Run the stage 1-3 methods for dissolving businesses."""
    if application is None:
        application = create_app()

    with application.app_context():
        

[source] git:///Users/orest/hrono-eval/mirror/business-filings-ui/src/components/dialogs/NotInGoodStandingDialog.vue@6af0a43ed247024f9cfc2cc46092f698e428d9f3 sp:/.~blank-line[2] sp:/.~blank-line[3]
        <template v-if="isDissolveMessage">
          <p class="warning-text">
            This business cannot be dissolved at this time because it is not in good standing
            with the Business Registry. There may be several reasons why a business is not in
            good standing, but the most common reason is an overdue annual report.
          </p>

          <p class="warning-text">
            Please file any overdue annual reports in your To Do list and try your voluntary
            dissolution again, or contact BC Registries staff:
          </p>
        </template>



[source] git:///Users/orest/hrono-eval/mirror/lear/jobs/furnishings/report-templates/noticeOfDissolutionCommencement.html@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/html/body/div/div/div[1]/div[17] sp:/html/body/div/div/div[1]/div[18]
<div class="mt-5">To request a delay of the dissolution, go to <a href="https://www.business.bcregistry.gov.bc.ca/{{ furnishing.businessIdentifier }}" class="break-url">business.bcregistry.gov.bc.ca/{{ furnishing.businessIdentifier }}</a> and request for a Delay of Dissolution or Cancellation under the To Do section. This must be completed prior to the dissolution of the company.</div>
          <div class="mt-5">If your company is dissolved under section 422(1)(a) of the Act, section 347 of the Act states the liability of each director, officer, shareholder and liquidator of a company that is dissolved continues and may be enforced as if the company had not been dissolved.</div>
          

[source] git:///Users/orest/hrono-eval/mirror/lear/legal-api/report-templates/noticeOfDissolutionCommencement.html@a30995be5c09afdc54018ba8eb3aad796509a7d9 sp:/html/body/div/div/div[1]/div[17] sp:/html/body/div/div/div[1]/div[18]
<div class="mt-5">To request a delay of the dissolution, go to <a href="https://www.business.bcregistry.gov.bc.ca/{{ furnishing.businessIdentifier }}" class="break-url">business.bcregistry.gov.bc.ca/{{ furnishing.businessIdentifier }}</a> and request for a Delay of Dissolution or Cancellation under the To Do section. This must be completed prior to the dissolution of the company.</div>
          <div class="mt-5">If your company is dissolved under section 422(1)(a) of the Act, section 347 of the Act states the liability of each director, officer, shareholder and liquidator of a company that is dissolved continues and may be enforced as if the company had not been dissolved.</div>
          

```


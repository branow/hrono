24 facts cite this leaf's files.

| prompt | words | facts conveyed | runs' range | detail share | contradicted | cited files named |
|---|---|---|---|---|---|---|
| `today` | 859 | 0.2 | 0.19-0.21 | 0.61 | 0 | 12/12 |
| `decisions` | 1325 | 0.23 | 0.23-0.23 | 0.58 | 0 | 12/12 |
| `core` | 333 | 0.21 | 0.21-0.21 | 0.08 | 0 | 5/12 |
| `core-states` | 504 | 0.19 | 0.15-0.23 | 0.38 | 0 | 10/12 |
| `core-states#2` | 607 | 0.27 | 0.27-0.27 | 0.25 | 0 | 10/12 |
| `(input)` | 2984 | 0.3 | 0.29-0.31 |  | 0 | 12/12 |

Per fact (score per prompt):

| # | fact | today | decisions | core | core-states | core-states#2 | (input) |
|---|---|---|---|---|---|---|---|
| 1 | The auth-web InvitationService posts new invitations to POST /invitations. The API's post_invitation endpoint … | 0 | 0 | 0 | 0 | 1 | 1 |
| 2 | create_invitation picks the invitation type and the required login source from the org's access type: ANONYMOU… | 0 | 0 | 0 | 0 | 0 | 0 |
| 3 | send_invitation builds a '<orgName>/validatetoken/<loginSource>/<token>' URL and calls publish_to_mailer. publ… | 0 | 0 | 0 | 1 | 1 | 1 |
| 4 | validate_token rejects tokens older than TOKEN_EXPIRY_PERIOD days (7 days by default) and invitations already … | 0 | 0 | 0 | 0 | 0 | 0 |
| 5 | accept_invitation creates a Membership whose status depends on the org and user. GOVM orgs get ACTIVE immediat… | 0 | 0 | 0 | 0 | 0 | 0 |
| 6 | After acceptance, the user is added to Keycloak groups through KeycloakService.join_users_group and join_accou… | 1 | 1 | 1 | 1 | 1 | 1 |
| 7 | Permissions.build_all_permission_cache loads every row into the Flask cache keyed by (org_status, membership_t… | 2 | 2 | 2 | 1 | 2 | 2 |
| 8 | Permissions.get_permissions_for_membership treats every org status except NSF_SUSPENDED, PENDING_STAFF_REVIEW … | 0 | 0 | 0 | 0 | 0 | 0 |
| 9 | Server-side role checks inside services use check_auth with one_of_roles, disabled_roles or equals_role agains… | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | Affiliation.is_authorized lets staff through. For SP/GP firms it checks the supplied party name against the en… | 1 | 1 | 1 | 0 | 1 | 2 |
| 11 | A successful affiliation saves the Affiliation model, marks the entity's passcode as claimed (except for SP/GP… | 1 | 1 | 1 | 0 | 1 | 1 |
| 12 | Org.create_org decides whether staff review is needed. It is needed for GOVN accounts, and for EXTRA_PROVINCIA… | 0 | 0 | 0 | 0 | 0 | 0 |
| 13 | When an unverified BCeID user accepts an ADMIN invitation, Invitation._create_affidavit_review_task creates a … | 0 | 0 | 0 | 0 | 0 | 1 |
| 14 | Staff resolve tasks through PUT /tasks/<id>, which is limited to the STAFF role. It calls Task.update_task, wh… | 0 | 0 | 0 | 0 | 0 | 0 |
| 15 | For ORG tasks, Org.approve_or_reject approves or rejects the affidavit through AffidavitService when the actio… | 0 | 0 | 0 | 0 | 0 | 0 |
| 16 | For USER tasks, Task._update_bceid_admin sets the user to ACTIVE or INACTIVE and the membership to ACTIVE or R… | 0 | 0 | 0 | 0 | 0 | 0 |
| 17 | Putting a task on HOLD is allowed for ORG tasks only when the action is AFFIDAVIT_REVIEW (otherwise it raises … | 0 | 0 | 0 | 0 | 0 | 0 |
| 18 | On the server, the rule exists only in Membership.update_membership, which serves PATCH /orgs/<id>/members/<me… | 0 | 0 | 0 | 0 | 0 | 0 |
| 19 | get_owner_count counts every ADMIN in org.members, the relationship on the Org model, without filtering by mem… | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | Membership.deactivate_membership, which serves DELETE /orgs/<id>/members/<membership_id>, has no last-admin ch… | 0 | 0 | 0 | 0 | 0 | 0 |
| 21 | Both membership paths call Membership._add_or_remove_group after saving. It removes the user from the Keycloak… | 1 | 1 | 1 | 0 | 1 | 1 |
| 22 | Both paths also publish REMOVE_TEAM_MEMBER activities via ActivityLogPublisher, and update_membership sends TE… | 0 | 1 | 1 | 0 | 1 | 1 |
| 23 | Services record actions by calling ActivityLogPublisher.publish_activity with an Activity dataclass (org_id, a… | 1 | 2 | 1 | 2 | 2 | 2 |
| 24 | publish_activity fills in actor_id from the JWT user and remoteAddr, wraps the data in a SimpleCloudEvent of t… | 2 | 2 | 2 | 2 | 2 | 2 |

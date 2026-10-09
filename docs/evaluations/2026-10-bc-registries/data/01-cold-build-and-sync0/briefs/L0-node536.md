<!-- leaf 536, 21 members -->

**What this is:** A Jenkins CI/CD deployment kit for OpenShift (the `lear` repo, FreshworksStudio). It has a setup procedure, build and deploy templates, runtime manifests, cross-namespace RBAC, and a plugin list. Several pieces are truncated or incomplete.

## Setup procedure
- **Jenkins setup** has three steps:
  1. Create the roles: `jq '{"kind":"List","items":.objects}' _jenkins.role.json | oc create -f -`.
  2. Build the image with `./build.sh`.
  3. Deploy with `./deploy.sh`.

## Build-side templates
These all share the parameters `NAME`, `NAME_SUFFIX` and `VERSION`, plus the Git settings `SOURCE_REPOSITORY_URL`, `GIT_REF` (default `develop`) and `SOURCE_CONTEXT_DIR` (default `devops/jenkins`). The template's `objects` section is cut off.
- **Template "Jenkins":** non-bindable.
- **ImageStreams:**
  - `jenkins-2-rhel7`: tag v3.11, pulled from `registry.access.redhat.com`.
  - `${NAME}-base`.
  - `${NAME}`.
- **BuildConfigs:** both use the same resources (limits cpu=1/memory=2.5Gi, requests cpu=500m/memory=1Gi) and the same ConfigChange and ImageChange triggers.
  - `${NAME}-base` is a Dockerfile build from `jenkins-2-rhel7:v3.11`. It outputs `${NAME}-base:${VERSION}` and has a 1200s deadline.
  - `${NAME}${NAME_SUFFIX}` is a Source-strategy build from `${NAME}-base:${VERSION}`. It outputs `${NAME}:${VERSION}` and runs serially.

## Deployment-side resources
- **Template "Jenkins - Deployment":** parameters `NAME`, `NAME_SUFFIX` and `VERSION`. It is cut off mid-structure.
- **Storage and secrets:**
  - PVC `jenkins-data-store`: 10Gi, ReadWriteOnce, `gluster-block`.
  - Secret `github-credentials`: basic-auth with empty fields.
- **Configuration and identity:**
  - ConfigMap `jenkins`: init scripts, the `lear` multibranch project, and the BCDevOps shared library.
  - ServiceAccount `jenkins`: carries an OAuth redirect annotation to the `jenkins` Route.
  - RoleBinding `jenkins_edit`: grants the ServiceAccount the `edit` role.
- **DeploymentConfig `jenkins`:**
  - **Strategy and triggers:** Recreate strategy, 1 replica, ImageChange trigger on `jenkins:${VERSION}`, and a ConfigChange trigger.
  - **Container:**
    - OAuth and Kubernetes env vars.
    - `JAVA_OPTS` with a Vancouver timezone.
    - CPU limit 4 and memory limit 6Gi.
    - Data mounted at `/var/lib/jenkins`.
  - **Probes:** liveness on `/login:8080` with a 420s initial delay and 30 allowed failures. Readiness on the same path with no initial delay and 3 allowed failures.
  - **Pod settings:** restartPolicy Always, 30s grace period, and ServiceAccount `jenkins`.
  - **Status:** all counters are 0.
- **Networking:**
  - Service `jenkins-jnlp`: 50000→50000.
  - Service `jenkins`: 80→8080.
  - Route `jenkins`: edge TLS, redirect on insecure, 4m HAProxy timeout.

## RBAC across environments
A separate role-binding template creates `jenkins_edit` in `zcd4ou-dev`, `zcd4ou-test` and `zcd4ou-prod`. Each binds the `jenkins` ServiceAccount from `zcd4ou-tools` to `edit`. Its parameters are defined but unused.

## Plugins
The plugin list has 100+ entries. The `blueocean-*` plugins are mostly at 1.16.0. Others include `workflow-cps:2.68`, `kubernetes:1.15.4`, `git:3.10.0` and `jira:3.0.7`.

## Caution:
- `build.sh` needs a manual PR number edit before every run. If you forget, you ship a stale build.
- In the Jenkins template, `NAME`, `NAME_SUFFIX` and `VERSION` all have `displayName: "Name"`, which is confusing. The template is also non-bindable.
- Every `${...}` value is a template parameter that must be substituted before applying. Applying the resources directly fails.
- The "Jenkins - Deployment" template and the DeploymentConfig are truncated, so their full logic can't be assessed.
- The Secret `github-credentials` has empty username and password. Fill them in before deploying, or the checkout breaks.
- The `gluster-block` storage class must exist, or the PVC stays pending.
- The Jenkins container has an empty `image` field and won't start until it's populated.
- `JAVA_OPTS` ends with an incomplete CSP value. `CONTAINER_CORE_LIMIT=5` is numeric, and some orchestrators need a string.
- The Recreate strategy causes downtime during rollouts.
- The pod `securityContext` is empty, so no restrictions apply. `serviceAccount` and `serviceAccountName` are redundant.
- The liveness probe waits 420s and then tolerates about 5 minutes of failures. The readiness probe fails fast (30s) and gates traffic.
- The status counters are all 0, which means the deployment hasn't run or failed. No condition is shown to explain why.
- The ConfigMap hard-codes BCDevOps repo URLs on `master`, so using forks requires editing it.
- The OAuth redirect annotation is OpenShift-specific and must be removed for vanilla Kubernetes.
- The Route `host` is empty, so any hostname is accepted. Insecure traffic is redirected to HTTPS with no unencrypted fallback.
- The ServiceAccount in the `jenkins_edit` RoleBinding has no explicit namespace, so it assumes the default one.
- The three `jenkins_edit` bindings share a name across namespaces. That's allowed, but they depend on the cross-namespace `zcd4ou-tools` reference.
- The `blueocean-*` plugins are clustered at 1.16.0, so check compatibility before upgrading selectively. `jackson2-api:2.9.8` is outdated.

## Members

- lear: devops/jenkins/README.md
- lear: devops/jenkins/_jenkins.bc.json
- lear: devops/jenkins/_jenkins.bc.json
- lear: devops/jenkins/_jenkins.bc.json
- lear: devops/jenkins/_jenkins.bc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.dc.json
- lear: devops/jenkins/_jenkins.role.json
- lear: devops/jenkins/plugins.txt

<!-- leaf 283, 18 members -->

This group is a set of condensed notes on deployment configuration for the "entity-filer" component (APP_NAME bcros). Most notes describe an OpenShift/Kubernetes template made of a Template, ConfigMap, DeploymentConfig, Service and ImageStream. One note covers a Firebase hosting config for a separate SPA. Nearly all of the OpenShift snippets are truncated.

## Firebase hosting (separate from the rest)
- Site "business-filings-dev", public dir "dist".
- Ignores `**/devops/**`, `**/.*/` and `**/node_modules/**`.
- A single rewrite sends every path (`**`) to `/index.html`, as an SPA needs.

## OpenShift template: parameters and values
- **Identity and app:**
  - APP_NAME=bcros
  - COMP_NAME=entity-filer
  - APP_FILE=pay_filer.py
  - DATABASE_NAME=lear
  - SUFFIX (required, no default)
- **External services:**
  - SENTRY_DSN (a placeholder)
  - PAYMENT_SVC_URL=http://pay-api.l4ygcl-dev.svc/api/v1/payments
  - NATS_SERVERS=nats://nats-streaming.hak2zo-dev.svc:4222
- **NATS settings (all required, all with defaults):**
  - NATS_CLUSTER_ID="test-cluster"
  - NATS_CLIENT_NAME="entity.filing.payment.worker"
  - NATS_SUBJECT="entity.filing.payment" (payment token receiver)
  - NATS_FILER_SUBJECT="entity.filing.filer" (filing processing)
  - NATS_QUEUE="filing-worker"
- **Image and resources:**
  - IMAGE_NAMESPACE="gl2uos-tools"
  - CPU_REQUEST=100m, CPU_LIMIT=750m
  - MEMORY_REQUEST=100Mi, MEMORY_LIMIT=200Mi
  - REPLICA_MIN=REPLICA_MAX=1
  - DB_SECRET_ACCESS="lear_db_access"
- **Template header (repeated in several fragments):** kind Template, apiVersion v1, name `${COMP_NAME}-${SUFFIX}`. The description is "Deployment template for a legal api service." and the tags are `${COMP_NAME}`. The parameters list is cut off.

## Cluster objects
- **ImageStream:** shared=true.
- **Service:** `${COMP_NAME}-${SUFFIX}`, ClusterIP, port 8080/TCP to targetPort 8080, sessionAffinity None.
- **ConfigMap:** `${COMP_NAME}-${SUFFIX}-config`, label app=`${COMP_NAME}-${SUFFIX}`.
  - Keys: APP_FILE, DATABASE_HOST, DATABASE_NAME, DB_PORT, JWT_OIDC_JWKS_CACHE_TIMEOUT="300", PAYMENT_SVC_URL, SENTRY_DSN, and the NATS_* settings.
  - All values are template variables except the JWT timeout.
- **DeploymentConfig** (several truncated fragments): name and labels `${COMP_NAME}-${SUFFIX}`, Rolling strategy with the rollingParams contents omitted, and a `containerName` fragment of `${COMP_NAME}`.
- **Container:**
  - Image: `docker-registry.default.svc:5000/${IMAGE_NAMESPACE}/${COMP_NAME}:${SUFFIX}`.
  - Probes: liveness `/healthz` and readiness `/readyz`, both on port 7070, with initialDelay 60s, period 10s, failureThreshold 3 and timeout 1s.
  - Resources: taken from the CPU and memory template parameters.
  - Ports: two identical entries, containerPort 8080/TCP.

## Container environment variables
- **Secret refs:** DATABASE_USERNAME and DATABASE_PASSWORD come from secret `${DB_SECRET_ACCESS}`, using keys "username" and "password".
- **ConfigMap refs:** every other variable comes from `${COMP_NAME}-${SUFFIX}-config` through `valueFrom.configMapKeyRef`, with the key matching the variable name. These are DATABASE_NAME, DATABASE_HOST, DATABASE_PORT (key DB_PORT), JWT_OIDC_JWKS_CACHE_TIMEOUT, PAYMENT_SVC_URL, APP_FILE, SENTRY_DSN, NATS_SERVERS, NATS_CLUSTER_ID, NATS_CLIENT_NAME, NATS_SUBJECT, NATS_FILER_SUBJECT and NATS_QUEUE.
- The env list is partial and ends on a trailing comma.

## Caution:
- **Firebase:** the `**` rewrite also catches static assets. If an asset is missing or misnamed in `dist/`, the request returns `index.html`, which breaks the asset load and can cause 404 loops.
- **Template variables:** `${COMP_NAME}` and `${SUFFIX}` must be substituted at deploy time, and an incomplete definition may cause parsing errors. If left unsubstituted, they stay as literal strings and ConfigMap lookups fail at runtime. SUFFIX has no default.
- **Truncated snippets:** the Template parameters list, DeploymentConfig spec, rollingParams, containers and env list are all cut off.
- **Placeholder value:** SENTRY_DSN uses `account.sentry.ioo`, which is not a real domain.
- **NATS defaults:** these parameters are marked required but ship with defaults. They must be overridden per environment, or the subjects will collide across environments.
- **Hardcoded replicas:** REPLICA_MIN and REPLICA_MAX are both "1", so there is no autoscaling or HA.
- **Typo:** the displayName for DB_SECRET_ACCESS is "DB_SECRET_ACCCESS" (triple C), copied verbatim from the source.
- **Session affinity:** sessionAffinity None means no stickiness, so requests may reach different pods.
- **ConfigMap key syntax:** `"DB_PORT": "${DATABASE_PORT"` is missing its closing brace, so it renders as a literal string.
- **Probes:** a 1s timeout is aggressive, and slow startup could cause failures before readiness succeeds.
- **Duplicate port:** the repeated 8080/TCP port entry is likely a copy-paste error.
- **Mixed reference types:** the env block mixes secretKeyRef and configMapKeyRef.
- **Inconsistent ConfigMap name:** the DATABASE_PORT env var uses `${DATABASE_PORT}-${SUFFIX}-config` as the ConfigMap name, where the others use `${COMP_NAME}`.
- **Runtime requirements:** the ConfigMap name and keys must exist at runtime, or the pod fails to start.
- **Namespace collisions:** SUFFIX is likely environment-specific (dev/test/prod). Deployments that share a namespace risk name collisions.

## Members

- business-filings-ui: firebase.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_entity-filer.dc.json
- lear: devops/openshift/_legal-api.dc.json
- lear: devops/openshift/_legal-api.dc.json
- lear: devops/openshift/_legal-api.dc.json

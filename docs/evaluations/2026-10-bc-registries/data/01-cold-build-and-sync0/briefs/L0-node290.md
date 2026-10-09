<!-- leaf 290, 9 members -->

This is a set of condensed notes on OpenShift templates from what looks like a BC Gov (Artifactory-backed) project. Most describe BuildConfig templates that build small Python services from Git. One covers resource parameters, and one covers deployment parameters.

## BuildConfig templates (Python Docker builds)

All of these share one pattern:
- **Objects:** an ImageStream plus a BuildConfig that uses the Docker strategy with an inline Dockerfile.
- **Source:** Git, set by `${GIT_REPO_URL}`, `${GIT_REF}` and `${SOURCE_CONTEXT_DIR}`.
- **Base image:** `docker-remote.artifacts.developer.gov.bc.ca/python:3.8.5-buster`.
- **Build steps:** workdir `/opt/app-root`, `pip==20.1.1`, `requirements.txt` install, then (in most) `pip install .`.
- **Environment:** `PYTHONPATH=/opt/app-root/src`.
- **Pull and trigger:** pull secret `artifactory-creds`, `runPolicy: Serial`, and a `ConfigChange` trigger.
- **Output:** `${NAME}:${OUTPUT_IMAGE_TAG}`. The CPU/memory limits and requests are template variables.

Variations by service (entrypoint and details):
- **Email reminder:** `CMD ["python", "/opt/app-root/email_reminder.py"]`, exposes 8080.
- **Pay filer (`pay_filer.py`):** runs as user 1001. The pip upgrade and `EXPOSE 8080` lines are commented out. This service appears twice in the notes, with identical content.
- **BN service:** `bn_service.py`, runs as UID 1001, exposes 8080.
- **Email service:** `email_service.py`, exposes 8080. The notes say it also uses `pip install .`.
- **Filer service:** `filer_service.py`, user 1001, exposes 8080, with `pip install .`.
- **Generic Python 3.8 template:** `app.py`, user 1001. It runs `pip install .` as an editable install after `requirements.txt`.

## Deployment and resource parameters

- **Resource-only parameter set:**
  - `PERSISTENT_VOLUME_CLASS`: netapp-file-standard (optional).
  - `CPU_REQUEST`: 10m.
  - `CPU_LIMIT`: 250m.
  - `MEMORY_REQUEST`: 10Mi.
  - `MEMORY_LIMIT`: 512Mi.
  - All except the volume class are required.
- **Deployment parameters for `account-mailer`** (all required):
  - NAME: `account-mailer`
  - TAG: `dev`
  - ROLE: `queue`
  - NAMESPACE: `6e0e49`
  - IMAGE_NAMESPACE: `tools`
  - IMAGE_REGISTRY: `image-registry.openshift-image-registry.svc:5000`
  - MIN_REPLICAS and MAX_REPLICAS: both `"1"`
  - CPU: 10m request, 500m limit
  - Memory: 10Mi request, 1Gi limit

## Caution:
- **Old pins:** pip is pinned to 20.1.1 and the base image is Python 3.8.5-buster, both from 2020. The base image is archived and EOL. Check whether the pin is an intentional freeze or legacy debt before upgrading. The old pip may also conflict with newer package requirements.
- **Registry path:** the `-remote` suffix in the registry path means an Artifactory proxy.
- **PYTHONPATH mismatch (pay filer):** `PYTHONPATH` points to `src/`, but the main script is at `/opt/app-root/pay_filer.py`, not in `src/`.
- **Inline Dockerfile:** the Dockerfile is embedded in the YAML, and the pip version is hardcoded there.
- **Double install (generic template):** pip install runs twice, once for `requirements.txt` and once for the package. `pullSecret` covers only the base image pull, not the Git source clone.
- **Resource units:** units are millicores (m) and Mi/Gi. Mismatched units, or request and limit swapped, will fail deployment.
- **No scaling:** MIN_REPLICAS and MAX_REPLICAS are both the string `"1"`, so there is no scaling.

## Members

- lear: jobs/email-reminder/k8s/templates/bc.yaml
- lear: queue_services/business-pay/k8s/templates/bc.yaml
- lear: queue_services/entity-bn/k8s/templates/bc.yaml
- lear: queue_services/entity-emailer/k8s/templates/bc.yaml
- lear: queue_services/entity-emailer/k8s/templates/tracker-db.yaml
- lear: queue_services/entity-filer/k8s/templates/bc.yaml
- lear: queue_services/entity-pay/k8s/templates/bc.yaml
- sbc-auth: queue_services/account-mailer/openshift/templates/bc.yaml
- sbc-auth: queue_services/account-mailer/openshift/templates/dc.yaml

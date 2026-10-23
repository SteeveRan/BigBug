---
name: helm
description: Helm 3 chart development, scaffolding, templating, debugging, OCI registries, post-renderers, and production operations. Use when creating Helm charts, packaging Kubernetes applications, debugging Helm deployments, managing releases, working with chart dependencies, or when the user mentions Helm, helm install, helm upgrade, Chart.yaml, values.yaml, helm template, or OCI registry.
---

# Helm

Covers the full lifecycle: chart creation, templating, dependency management, validation, OCI distribution, debugging, and release operations.

## Chart structure

```text
mychart/
  Chart.yaml
  values.yaml
  values.schema.json       # optional JSON Schema validation
  charts/                   # dependencies
  crds/                     # CRDs (applied before templates)
  templates/
    NOTES.txt
    _helpers.tpl
    deployment.yaml
    service.yaml
    ingress.yaml
    configmap.yaml
    secret.yaml
    hpa.yaml
    tests/
      test-connection.yaml
  .helmignore
```

## Chart.yaml

```yaml
apiVersion: v2
name: myapp
description: A production-grade web application
type: application
version: 1.0.0
appVersion: "2.0.1"
kubeVersion: ">=1.30.0"

maintainers:
  - name: DevOps Team
    email: devops@example.com

dependencies:
  - name: postgresql
    version: "16.x.x"
    repository: "oci://registry-1.docker.io/bitnamicharts"
    condition: postgresql.enabled
```

## values.yaml

Organize hierarchically; document every field with comments.

```yaml
replicaCount: 3

image:
  repository: myregistry.io/myapp
  tag: ""
  pullPolicy: IfNotPresent

imagePullSecrets: []

serviceAccount:
  create: true
  annotations: {}
  name: ""

podAnnotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "9090"

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 2000

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: [ALL]

service:
  type: ClusterIP
  port: 80
  targetPort: 8080

ingress:
  enabled: false
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: myapp.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: myapp-tls
      hosts: [myapp.example.com]

resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: false
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

nodeSelector: {}
tolerations: []

affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/name
                operator: In
                values: [myapp]
          topologyKey: kubernetes.io/hostname

postgresql:
  enabled: false
```

## Template helpers (`_helpers.tpl`)

```yaml
{{- define "myapp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "myapp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "myapp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "myapp.labels" -}}
helm.sh/chart: {{ include "myapp.chart" . }}
{{ include "myapp.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "myapp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "myapp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "myapp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "myapp.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
```

## Key template patterns

**Conditional resource:**

```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
...
{{- end }}
```

**Config checksum (force pod restart on config change):**

```yaml
annotations:
  checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

**Iterate over env list:**

```yaml
env:
{{- range .Values.env }}
- name: {{ .name }}
  value: {{ .value | quote }}
{{- end }}
```

**Safe defaults:**

```yaml
image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
replicas: {{ .Values.replicaCount | default 3 }}
```

## Validation workflow

Always follow this progression:

```bash
# 1. Static lint
helm lint ./mychart --strict

# 2. Render templates locally
helm template myapp ./mychart --debug --values values.yaml

# 3. Server-side dry-run (resolves lookup functions against the real API)
helm install myapp ./mychart \
  --namespace prod \
  --values values.yaml \
  --dry-run=server --debug

# 4. Install
helm install myapp ./mychart \
  --namespace prod \
  --values values.yaml \
  --atomic --wait

# 5. Post-deploy tests
helm test myapp --namespace prod --logs
```

Use `--dry-run=server` (not the bare `--dry-run`) when templates contain `lookup` calls that need to resolve against live cluster state.

## Common commands

**Inspect a deployed release:**

```bash
helm get manifest myapp -n prod
helm get values myapp -n prod --all
helm status myapp -n prod --show-resources
```

**Upgrade:**

```bash
helm upgrade myapp ./mychart -f values.yaml
helm upgrade --install myapp ./mychart
helm upgrade myapp ./mychart --atomic --timeout 5m
```

**Rollback:**

```bash
helm history myapp -n prod
helm rollback myapp 3 -n prod --cleanup-on-fail
```

**Dependencies:**

```bash
helm dependency list ./mychart
helm dependency update ./mychart
helm dependency build ./mychart
```

**Repositories:**

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm search repo postgresql
helm show values bitnami/postgresql
```

## OCI registry workflow

OCI is the preferred distribution method. No `helm repo add` required.

```bash
# Authenticate
helm registry login registry.example.com -u <user>

# Push a packaged chart
helm package ./mychart
helm push mychart-1.0.0.tgz oci://registry.example.com/charts

# Pull
helm pull oci://registry.example.com/charts/mychart --version 1.0.0

# Install directly from OCI
helm install myapp oci://registry.example.com/charts/mychart --version 1.0.0

# Template, show, upgrade all work with oci:// refs
helm show values oci://registry.example.com/charts/mychart --version 1.0.0
```

OCI dependencies in `Chart.yaml`:

```yaml
dependencies:
- name: redis
  version: "18.x.x"
  repository: "oci://registry-1.docker.io/bitnamicharts"
```

## Post-renderers

Post-renderers transform rendered manifests before Helm applies them. Common use case: injecting labels/annotations via Kustomize without forking the chart.

```bash
helm install myapp ./mychart --post-renderer ./kustomize-labels.sh
helm upgrade myapp ./mychart --post-renderer ./kustomize-labels.sh
helm template myapp ./mychart --post-renderer ./kustomize-labels.sh
```

The executable receives rendered YAML on stdin and must emit valid YAML on stdout. Chain multiple renderers with pipes: `renderer1 | renderer2`.

## Multi-environment layout

```text
mychart/
  values.yaml
  values-dev.yaml
  values-staging.yaml
  values-prod.yaml
```

```bash
helm install myapp ./mychart -f values-prod.yaml -n production
```

## Hooks

**Pre-install/pre-upgrade job (e.g., DB migration):**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "myapp.fullname" . }}-migration
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "0"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: migration
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
        command: ["./migrate.sh"]
```

**Test pod:**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: {{ include "myapp.fullname" . }}-test
  annotations:
    "helm.sh/hook": test
spec:
  containers:
  - name: curl
    image: curlimages/curl:latest
    command: ['curl']
    args: ['{{ include "myapp.fullname" . }}:{{ .Values.service.port }}/health']
  restartPolicy: Never
```

## Debugging reference

| Symptom | Likely cause | Fix |
|:--------|:-------------|:----|
| `error converting YAML to JSON` | Indentation error | Use `{{- ... }}` for whitespace chomping |
| `nil pointer evaluating interface` | Missing value | Add `\| default "value"` |
| `cannot unmarshal string into Go value of type int` | Wrong value type | Use `\| int` in template |
| `resource that already exists` | Conflicting release | Uninstall conflicting release or adopt resource |
| `ImagePullBackOff` | Wrong image name or missing pull secret | Fix image ref; create `imagePullSecrets` |
| `no matches for kind` | CRD not installed | `kubectl apply -f crds/` first |
| `timed out waiting for the condition` | Readiness probe failure or slow start | Increase `--timeout`; review probes |
| `pre-upgrade hooks failed` | Hook job failed | Delete failed job; retry with `--no-hooks` |

**Context safety** -- always pass `--kube-context` and `-n` explicitly to avoid targeting the wrong cluster:

```bash
helm --kube-context=prod-cluster status myapp -n prod
kubectl --context=prod-cluster get pods -n prod
```

**Verbose output for template errors:**

```bash
helm template myapp ./mychart --debug 2>&1 | head -100
```

## Values schema validation

```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["replicaCount", "image"],
  "properties": {
    "replicaCount": { "type": "integer", "minimum": 1 },
    "image": {
      "type": "object",
      "required": ["repository"],
      "properties": {
        "repository": { "type": "string" },
        "tag":        { "type": "string"  }
      }
    }
  }
}
```

## Best practices

- Use semantic versioning for both `version` and `appVersion`.
- Always define `resources` requests and limits.
- Never commit secrets to `values.yaml`; use Vault, Sealed Secrets, or External Secrets.
- Pin dependency versions explicitly.
- Include `NOTES.txt` with post-install usage instructions.
- Use `values.schema.json` to catch misconfiguration early.
- Add `checksum/config` annotations to force restarts on ConfigMap changes.
- Use `--atomic` for upgrades in CI to auto-rollback on failure.
- Prefer OCI registries over classic Helm repos for chart distribution.
- Use `--dry-run=server` when templates use `lookup` to validate against real cluster state.

## Anti-patterns

- Hardcoded values in templates instead of `.Values.*` references.
- Missing resource limits (causes unbounded resource consumption).
- Plain-text secrets in `values.yaml` or committed chart files.
- Relying on implicit `kubectl` context without `--context`.
- Deeply nested `_helpers.tpl` logic that makes templates unreadable.
- Using bare `--dry-run` with `lookup`-heavy templates -- the lookups return empty without `--dry-run=server`.

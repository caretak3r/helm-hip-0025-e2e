{{- /* slow-ready Deployment for lifecycle tests: (dict "root" $ "name" "x") */ -}}
{{- define "e2e.workload.lifecycle" -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .name }}
  annotations:
    rev: {{ .root.Values.global.rev | quote }}
spec:
  replicas: 1
  selector:
    matchLabels: {app: {{ .name }}}
  template:
    metadata:
      labels: {app: {{ .name }}}
      annotations:
        rev: {{ .root.Values.global.rev | quote }}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
        - name: web
          image: {{ .root.Values.image }}
          imagePullPolicy: IfNotPresent
          readinessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: {{ .root.Values.readyDelay }}
            periodSeconds: 1
{{- end -}}

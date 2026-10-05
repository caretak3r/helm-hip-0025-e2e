{{- /* slow-ready Deployment: (dict "root" $ "name" "x") */ -}}
{{- define "e2e.workload.basic" -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .name }}
spec:
  replicas: 1
  selector:
    matchLabels: {app: {{ .name }}}
  template:
    metadata:
      labels: {app: {{ .name }}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
        - name: web
          image: {{ .root.Values.deployment.image }}
          imagePullPolicy: IfNotPresent
          readinessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: {{ .root.Values.deployment.readyDelay }}
            periodSeconds: 1
{{- end -}}

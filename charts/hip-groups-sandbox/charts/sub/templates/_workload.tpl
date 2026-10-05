{{- define "e2e.workload.sub" -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .name }}
  annotations:
    {{- with .group }}
    helm.sh/resource-group: {{ . }}
    {{- end }}
    {{- with .deps }}
    helm.sh/depends-on/resource-groups: {{ toJson . | quote }}
    {{- end }}
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
          image: {{ .root.Values.image }}
          imagePullPolicy: IfNotPresent
          readinessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: {{ .root.Values.readyDelay }}
            periodSeconds: 1
{{- end -}}

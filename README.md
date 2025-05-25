# lets-encrypt-cert-manager-istio-controller
Let's Encrypt Cert Manager Istio controller

This controller adds istio gateway and virtual service when detects ingress created by cert manager needed
for Let's Encrypt http01 resolver.

When Cert Manager creates an ingress (which is set to use port 80 and point back to the let's encrypt's
resolver) if you are using Istio - we need a gateway and a virtual service to route traffic from istio-ingress
to the solver service. This controller creates these two from the ingress created:

Gateway:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: temp-{name}-istio-ingress-gateway
  namespace: istio-system
  ownerReferences:
    ...
spec:
  selector:
    app: istio-ingress
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - {hostname}
```

VirtualService:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: temp-{name}-virtual-service
  namespace: istio-system
  ownerReferences:
    ...
spec:
  hosts:
  - {hostname}
  gateways:
  - temp-{name}-istio-ingress-gateway
  http:
  - route:
    - destination:
        host: {service-name}.istio-system.svc.cluster.local
        port:
          number: {service-port}
    match:
    - uri:
        prefix: {secret-path}
```

where:
- {name} is name of ingress k8s object (usually in a form of `cm-acme-http-solver-xxxxx`)
- {hostname} is hostname from the ingress
- {service-name} and {service-port} are from the service the ingress selects
- {secret-path} is from the path from the ingress (usually in the form of `/.well-known/acme-challenge/xxxxxxxxxxxx`)

and owner reference is set back to ingress itself. That allows the moment ingress is removed gateway and
virtual service are removed automatically by Kubernetes, too.

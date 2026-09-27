# TEST workload backend contract for API Gateway

The separate API Gateway repository owns the public HTTP API, routes, VPC link,
ACM certificate, its Route 53 validation CNAMEs,
custom-domain mapping and public DNS. The service owns
the ECS/Fargate, internal ALB, dedicated VPC-link security group and DocumentDB workload. This contract creates no
gateway resource and does not claim that the gateway repository is bootstrapped.

The trusted service workload result observer must authenticate its accepted
workload receipt and a fresh native checkpoint, then call
`poc_gateway_backend.project_gateway_backend`. Publish the returned nonsecret
descriptor with that authenticated result. A preview, arbitrary JSON document,
Pulumi output copied manually, or this pure projector alone is not authority.
The accepted-workload observer and authenticated publication remain unimplemented;
there is no usable live descriptor yet.

The closed `poc-api-gateway-backend/v1` descriptor contains:

| Field | Meaning |
| --- | --- |
| `account_id`, `region` | Exact admitted service TEST coordinates. |
| `integration_type` | `HTTP_PROXY`. |
| `connection_type` | `VPC_LINK`. |
| `listener_arn` | Native HTTPS ALB listener ARN, bound to the native ALB ARN. |
| `vpc_id` | Native service VPC ID. |
| `subnet_ids` | Both distinct native private application subnet IDs in that VPC. |
| `alb_security_group_id` | Native ALB security group, for network admission checks. This is distinct from the VPC-link security group. |
| `vpc_link_security_group_id` | Service-owned native security group in the same VPC, consumed by the gateway-owned VPC link. |
| `tls_server_name` | Explicit FQDN from the admitted domain contract, whose certificate ARN matches the native HTTPS listener. No hostname default. |
| `certificate_arn` | Exact regional ACM ARN resolved from the fixed gateway-owned SSM parameter and matched to native HTTPS listener inputs and outputs. The gateway owns this certificate; the service consumes it. |
| `request_parameters` | `{"overwrite:path":"$request.path"}` preserves the application path without a gateway stage prefix. |

The gateway consumer must verify the service result issuer, source/release and
checkpoint bindings before consuming this descriptor. It must reject missing or
extra fields, a wrong version/account/region, incomplete subnet coordinates and
any mismatch with its approved deployment contract. The HTTP API, VPC link and
ALB must be in the same AWS account. Configure the integration URI from
`listener_arn` and `tlsConfig.serverNameToVerify` from `tls_server_name`; do not
substitute an ALB DNS name or infer a PrivateLink endpoint service.

Deployment order is explicit: the gateway certificate phase creates the ACM
certificate and DNS validation records and publishes its ARN as a nonsecret SSM
String at `/vilnacrm/test/user-service/gateway-certificate-arn`; the service then
resolves and admits the issued certificate ARN and creates its HTTPS listener;
the gateway route phase consumes
the authenticated service descriptor. Service capability admission independently
requires an issued, unexpired regional certificate with the exact approved FQDN
in its SANs and TLS server-auth usage. No ARN is guessed and a pending or missing
certificate rejects workload admission. The ALB is internal in the two application subnets. It has only the HTTPS
listener; its sole inline ingress rule permits TCP 443 from the service-owned
VPC-link security group. That group has no ingress and allows HTTPS egress only
to application subnet CIDRs. The gateway attaches this existing group to its
VPC link and never adds standalone rules to the service's inline-managed groups.
No public ALB listener or direct internet ingress is accepted.
The service deployment observer needs a separately installed bootstrap #219
`ssm:GetParameter` grant scoped to
`arn:aws:ssm:eu-central-1:891377212104:parameter/vilnacrm/test/user-service/gateway-certificate-arn`.
It never requests decryption. The parameter ARN, positive version and resolved
certificate ARN are bound into the generated workload projection and replay
identity. Changed parameter versions or values require a fresh plan.

API Gateway VPC links support this ALB listener integration directly:
[AWS HTTP API private integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-private.html).

Generated `apiBaseUrl` and `apiUrl` are both `https://` plus the admitted public
gateway FQDN; `corsAllowOrigin` is anchored to that exact origin. Private ALB DNS
is never advertised as the application URL. The saved-plan network gate remains
fail-closed while complete resource semantics and accepted-state authentication
are unfinished; the native descriptor checks do not independently authorize apply.

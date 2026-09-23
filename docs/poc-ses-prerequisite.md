# TEST SES prerequisite and readiness

The registry phase owns eleven resources: its original seven-resource graph,
one SESv2 domain identity and three Easy DKIM CNAME records. Both phases retain
the same resource names, parent, provider and inputs. Other stacks and the ordinary
`UserServiceStack` composition do not register these resources.

The closed `mail_identity` declaration binds the identity to
`user.vilnacrmtest.com`, TEST account `891377212104`, region `eu-central-1`, and
existing public Route53 zone `Z04999481RZ4UQK2NANVH` (`vilnacrmtest.com`). The
workload sender retains its reviewed mailbox local-part and must use exactly this
domain. The existing `ses+api://default?region=eu-central-1` runtime contract and
task-role authentication remain unchanged. No SMTP credentials or DKIM private
key material is generated, accepted as input, stored or injected.

The pinned provider returns its unused, empty BYODKIM output field as a Pulumi
secret. Only this output may retain an opaque native ciphertext envelope;
plaintext must be empty. Inputs still forbid BYODKIM, and native observation must
confirm Easy DKIM with matching tokens. The observer never decrypts this field
or includes it in a receipt. Only the strictly validated public tokens are
explicitly unsecreted before deriving CNAME inputs.

The saved-plan validator accepts only the pinned provider's observed Check
metadata and checkpoint outputs. SES, ECR and Route53 raw bridge metadata must
match exact public structures; ECR encryption remains AES256, and every optional
Route53 routing setting remains empty or false. Timeout/schema metadata is fixed.
Unknown fields or changed metadata reject. The native-engine regression runs AWS
7.23.0 against synthetic loopback endpoints and checks persisted output shapes;
this is not evidence about the shared live checkpoint.

Registry plans require `--refresh --show-sames`. The gate validates each refresh
pre-event against the original checkpoint and requires exactly one later `same`
event per existing resource. It permits only the pinned provider's empty
`__defaults` recheck changes, preserving all substantive inputs. Later provider
outputs must match the original checkpoint except the three validated SES
verification status fields; their key presence remains fixed. Native SES checks,
not preview telemetry, determine readiness. Missing final `same` IDs and outputs
are validated using the original values in memory. The checkpoint and its
ciphertext are never rewritten from preview data.

The identity uses RSA-2048 Easy DKIM. The resource names use fixed indexes over
the sorted three provider tokens; record names and targets are derived together.
`allow_overwrite=False` prevents adopting existing records. Native observation
checks the exact public zone, identity type, signing configuration, tags, tokens,
and three CNAME values against the privately observed checkpoint. An existing
unowned identity, permission denial, missing record or different token rejects.
Only the SES native `NotFoundException` represents an absent identity.

The prerequisite receipt permits pending SES verification after ownership and DNS
creation succeed. Workload observation separately requires the native identity's
`VerifiedForSendingStatus=true`, Easy DKIM `SigningEnabled=true` and
`Status=SUCCESS`. A contract field or old checkpoint verification flag cannot
satisfy this gate. All existing image, capability and saved-plan stops remain in
place; successful SES verification alone cannot authorize workload execution.

Only the already-supported metadata baseline to complete prerequisite transition
is admitted. An old seven-resource ECR checkpoint or a partially completed SES/DNS
apply is rejected and needs separate authenticated reconciliation. This patch
does not infer state shape from AWS resource absence and does not authorize a
historical receipt/schema migration. Shared state, the protected native plan,
SES delivery and DNS propagation still require the protected preview/apply flow.

## Required bootstrap capability

No permissions are created by the service. The bootstrap-owned role policies,
boundaries and guards must all allow the same narrow capability before execution:

| Role/path | Actions | Resource |
| --- | --- | --- |
| Preview, drift, completion and apply reads | `ses:GetEmailIdentity`, `ses:ListTagsForResource` | `arn:aws:ses:eu-central-1:891377212104:identity/user.vilnacrmtest.com` |
| Apply creation | `ses:CreateEmailIdentity`, `ses:TagResource` | Same exact identity ARN; require baseline request tags and tag keys |
| Preview, drift, completion and apply reads | `route53:GetHostedZone`, `route53:ListResourceRecordSets` | `arn:aws:route53:::hostedzone/Z04999481RZ4UQK2NANVH` |
| Apply creation | `route53:ChangeResourceRecordSets` | Same exact zone ARN; conditions below |
| Apply change waiter | `route53:GetChange` | `arn:aws:route53:::change/*` |

For record writes use `ForAllValues:StringLike` on
`route53:ChangeResourceRecordSetsNormalizedRecordNames` with
`*._domainkey.user.vilnacrmtest.com`, and `ForAllValues:StringEquals` on
`route53:ChangeResourceRecordSetsRecordTypes=[CNAME]` and
`route53:ChangeResourceRecordSetsActions=[CREATE]`. Include `Null=false` for these
multivalue condition keys. No zone listing or SES identity listing is used, so
this path requires no list action with `Resource="*"`.

Pulumi AWS `7.23.0` pins Terraform AWS upstream commit
`4981ec2b44ea4892c1ee4f0c1ed23b761a55f44d`. Its
[SES resource](https://github.com/hashicorp/terraform-provider-aws/blob/4981ec2b44ea4892c1ee4f0c1ed23b761a55f44d/internal/service/sesv2/email_identity.go)
also implements `DeleteEmailIdentity`, `PutEmailIdentityConfigurationSetAttributes`
and `PutEmailIdentityDkimSigningAttributes`; its
[tag adapter](https://github.com/hashicorp/terraform-provider-aws/blob/4981ec2b44ea4892c1ee4f0c1ed23b761a55f44d/internal/service/sesv2/tags_gen.go)
implements `UntagResource`. These update/delete actions are unnecessary for the
closed create-or-same PoC transition and should remain denied. Tagged creation
does require `ses:TagResource`, as documented by the
[SES API-to-IAM mapping](https://docs.aws.amazon.com/service-authorization/latest/reference/list_sesv2.html).
The pinned
[Route53 record implementation](https://github.com/hashicorp/terraform-provider-aws/blob/4981ec2b44ea4892c1ee4f0c1ed23b761a55f44d/internal/service/route53/record.go)
supports updates/deletes too, but this graph does not admit them. See AWS's
[record permission conditions](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-permissions.html)
for the required multivalue operators and normalized names.

SES sandbox recipient restrictions and the centrally owned task role's scoped
`ses:SendEmail` grant remain separate live-delivery prerequisites. This change
does not request production access, verify recipients or claim delivery success.

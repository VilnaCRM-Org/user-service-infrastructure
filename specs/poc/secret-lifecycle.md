# PoC generated secret lifecycle

Desired workload source declares each secret's name, encryption-key ARN and
service ownership. The key ARN must resolve from reviewed platform metadata
before workload admission. Secret values, generated ARN suffixes and version IDs
are not desired inputs: first creation cannot know those AWS-generated values.

`poc_secret_observation.validate_secret_observation` checks metadata supplied by
the trusted result observer. Every purpose must have an exact matching name,
account, region, key and owner. Extra fields, including secret values, fail.
After the first accepted workload, updates and rollback must preserve the exact
ARN and version from its authenticated prior receipt. Desired secret names and
keys remain immutable across workload transitions. Rotation needs a separate
reviewed protocol.

This is source validation only. The helper neither queries AWS nor authenticates
a receipt. The observer must resolve the actual `AWSCURRENT` version from AWS,
never a caller-selected historical version. The trusted controller must supply the native current observation and
require the authenticated previous observation whenever an accepted workload
exists. Missing evidence must not select first-creation mode. This binding must
be wired before workload deployment; passing these tests does not prove live
secret generation or persistence. Registry-only execution cannot emit a secret
observation.

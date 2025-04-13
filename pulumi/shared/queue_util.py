import pulumi
import pulumi_aws as aws
import json

def create_queue(name: str, dead_letter_queue: aws.sqs.Queue = None, max_receive_count: int = 5, opts: pulumi.ResourceOptions = None) -> aws.sqs.Queue:
    redrive_policy = None
    if dead_letter_queue:
        redrive_policy = dead_letter_queue.arn.apply(lambda arn: json.dumps({
            "deadLetterTargetArn": arn,
            "maxReceiveCount": max_receive_count
        }))
    return aws.sqs.Queue(
        name,
        visibility_timeout_seconds=30,
        redrive_policy=redrive_policy,
        opts=opts
    )

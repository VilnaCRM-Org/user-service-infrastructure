import pulumi
from pulumi import ResourceOptions
from components.sqs_queues import SqsQueuesComponent

class MessageBrokerComponent(pulumi.ComponentResource):
    def __init__(self, name: str, opts: ResourceOptions = None):
        super().__init__("custom:feature:MessageBrokerComponent", name, None, opts)

        # Create the SQS queues (main queue and DLQ).
        self.sqs_queues = SqsQueuesComponent(name, opts=ResourceOptions(parent=self))

        self.register_outputs({
            "main_queue_url": self.sqs_queues.main_queue.url,
            "dlq_url": self.sqs_queues.dlq.url
        })

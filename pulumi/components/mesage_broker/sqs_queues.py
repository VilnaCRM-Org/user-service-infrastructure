import pulumi
import pulumi_aws as aws
from shared import queue_util

class SqsQueuesComponent(pulumi.ComponentResource):
    def __init__(self, name: str, tags: dict = None, opts: pulumi.ResourceOptions = None):
        """
        Creates two queues: a main queue and a dead-letter queue (DLQ) using shared queueutil.
        """
        super().__init__("custom:component:SqsQueuesComponent", name, {}, opts)
        self.dlq = queueutil.create_queue(f"{name}-dlq", opts=pulumi.ResourceOptions(parent=self))
        self.main_queue = queueutil.create_queue(f"{name}-queue", dead_letter_queue=self.dlq, opts=pulumi.ResourceOptions(parent=self))
        self.register_outputs({
            "main_queue_url": self.main_queue.url,
            "dlq_url": self.dlq.url
        })

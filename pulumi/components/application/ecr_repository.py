import pulumi
import pulumi_aws as aws

class EcrRepositoryComponent(pulumi.ComponentResource):
    def __init__(self, name: str, image_tag_mutability: str = "MUTABLE", tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:EcrRepositoryComponent", name, {}, opts)
        self.repo = aws.ecr.Repository(
            f"{name}-repo",
            image_tag_mutability=image_tag_mutability,
            tags=tags or {"Name": f"{name}-repo"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "repository_url": self.repo.repository_url,
            "repository_id": self.repo.id
        })

import aws_cdk as cdk
from constructs import Construct


class PipelineStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, storage, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # TODO: Step Functions + Lambdas — Sprint 2 Task 22
        pass
import aws_cdk as cdk
from constructs import Construct


class CicdStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # TODO: CI/CD pipeline — Sprint 2 Task 38
        pass
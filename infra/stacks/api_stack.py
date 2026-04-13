import aws_cdk as cdk
from constructs import Construct


class ApiStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, storage, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # TODO: API Gateway — Sprint 2 Task 20
        pass
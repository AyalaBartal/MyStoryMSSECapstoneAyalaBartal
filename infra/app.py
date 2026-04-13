import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.api_stack import ApiStack
from stacks.pipeline_stack import PipelineStack
from stacks.cicd_stack import CicdStack

app = cdk.App()

env = cdk.Environment(
    account="691304835962",
    region="us-east-1"
)

storage = StorageStack(app, "MyStoryStorage", env=env)
pipeline = PipelineStack(app, "MyStoryPipeline", storage=storage, env=env)
api = ApiStack(app, "MyStoryApi", storage=storage, pipeline=pipeline, env=env)
cicd = CicdStack(app, "MyStoryCicd", env=env)

app.synth()
from pipelines.pipeline_manager import PipelineManager

_pipeline_manager = PipelineManager()


def get_pipeline_manager():
    return _pipeline_manager

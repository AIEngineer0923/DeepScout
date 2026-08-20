from deepscout_research.usage.recorder import metadata_from_ai_message
from langchain_core.messages import AIMessage


def test_metadata_from_ai_message_usage_metadata() -> None:
    message = AIMessage(
        content="ok",
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )
    metadata = metadata_from_ai_message(message)
    assert metadata["input_tokens"] == 10
    assert metadata["output_tokens"] == 5

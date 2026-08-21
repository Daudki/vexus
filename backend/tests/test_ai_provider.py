import pytest

from app.ai.provider import (
    AIProviderError,
    NullProvider,
    build_anthropic_request,
    parse_anthropic_response,
)


def test_build_anthropic_request_has_correct_shape():
    payload = build_anthropic_request("system prompt", "user prompt", model="test-model")

    assert payload["model"] == "test-model"
    assert payload["messages"] == [{"role": "user", "content": "user prompt"}]
    assert "system prompt" in payload["system"]
    assert "observed_facts" in payload["system"]  # schema instructions are appended


def test_parse_valid_response():
    raw = {
        "content": [
            {
                "type": "text",
                "text": (
                    '{"observed_facts": ["Device X appeared at 14:32"], '
                    '"inferences": ["Device X may be unauthorized"], '
                    '"hypotheses": ["Could be a guest device"], '
                    '"recommendations": ["Verify ownership"], '
                    '"confidence": 0.82}'
                ),
            }
        ]
    }

    response = parse_anthropic_response(raw)

    assert response.observed_facts == ["Device X appeared at 14:32"]
    assert response.inferences == ["Device X may be unauthorized"]
    assert response.confidence == 0.82


def test_parse_response_with_multiple_text_blocks_concatenates():
    raw = {
        "content": [
            {"type": "text", "text": '{"observed_facts": [], "inferences": [], '},
            {"type": "text", "text": '"hypotheses": [], "recommendations": [], "confidence": 0.5}'},
        ]
    }

    response = parse_anthropic_response(raw)
    assert response.confidence == 0.5


def test_parse_response_missing_content_key_raises():
    with pytest.raises(AIProviderError, match="Unexpected Anthropic API response shape"):
        parse_anthropic_response({"not_content": []})


def test_parse_response_invalid_json_raises():
    raw = {"content": [{"type": "text", "text": "not valid json at all"}]}
    with pytest.raises(AIProviderError, match="not valid JSON"):
        parse_anthropic_response(raw)


def test_parse_response_wrong_schema_raises():
    # confidence must be a number, not a string
    raw = {"content": [{"type": "text", "text": '{"confidence": "high"}'}]}
    with pytest.raises(AIProviderError, match="did not match the required schema"):
        parse_anthropic_response(raw)


def test_parse_response_no_text_blocks_raises():
    raw = {"content": [{"type": "image", "source": {}}]}
    with pytest.raises(AIProviderError, match="no text content"):
        parse_anthropic_response(raw)


def test_parse_response_partial_schema_uses_defaults():
    # Model is allowed to omit fields it has nothing to say for (e.g. no hypotheses)
    raw = {"content": [{"type": "text", "text": '{"observed_facts": ["fact one"]}'}]}
    response = parse_anthropic_response(raw)

    assert response.observed_facts == ["fact one"]
    assert response.hypotheses == []
    assert response.confidence == 0.0


def test_null_provider_never_raises_and_flags_unconfigured():
    provider = NullProvider()
    response = provider.generate("system", "user")

    assert response.confidence == 0.0
    assert response.observed_facts == []
    assert "not configured" in response.recommendations[0]

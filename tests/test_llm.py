import pytest
from unittest.mock import MagicMock, patch
from src.llm.groq.gpt_oss_120b.client import GPTOSS120BClient

@patch('src.llm.groq.base_client.Groq')
def test_groq_client_init(mock_groq):
    with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
        from src.config import Config
        Config.GROQ_API_KEY = 'test-key'
        client = GPTOSS120BClient()
        assert client.model == "openai/gpt-oss-120b"
        mock_groq.assert_called_once_with(api_key='test-key')

@patch('src.llm.groq.base_client.Groq')
def test_groq_chat_no_stream(mock_groq):
    mock_instance = mock_groq.return_value
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = "Mock response"
    mock_instance.chat.completions.create.return_value = mock_completion
    
    client = GPTOSS120BClient()
    result_gen = client.chat([{"role": "user", "content": "hi"}], stream=False)
    results = list(result_gen)
    
    assert len(results) == 1
    assert results[0] == mock_completion

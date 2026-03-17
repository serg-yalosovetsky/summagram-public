import pytest
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_generate_text(client, mock_inference_service):
    payload = {
        "prompt": "Tell me a joke",
        "system_prompt": "You are a comedian",
        "max_tokens": 100,
        "temperature": 0.8,
    }
    response = client.post("/generate", json=payload)
    assert response.status_code == 200
    assert response.json()["text"] == "Mocked AI response"

    # Check if service was called with correct params
    mock_inference_service.generate_text.assert_called_with(
        prompt="Tell me a joke",
        system_prompt="You are a comedian",
        max_tokens=100,
        temperature=0.8,
    )


@pytest.mark.asyncio
async def test_analyze_image(client, mock_inference_service):
    with patch("os.path.exists", return_value=True):
        payload = {"image_path": "/tmp/test.jpg", "prompt": "What is this?"}
        response = client.post("/analyze-image", json=payload)
        assert response.status_code == 200
        assert "description" in response.json()
        mock_inference_service.analyze_image.assert_called_with(
            "/tmp/test.jpg", "What is this?"
        )


@pytest.mark.asyncio
async def test_analyze_video(client, mock_inference_service):
    with patch("os.path.exists", return_value=True):
        # The endpoint calls service.analyze_video(request)
        mock_inference_service.analyze_video = AsyncMock(
            return_value={
                "summary": "A video of a cat",
                "transcript": "Meow",
                "segments": [],
                "metadata": {},
            }
        )
        payload = {
            "video_path": "/tmp/cat.mp4",
            "adaptive_fps": True,
            "use_scene_detection": False,
        }
        response = client.post("/analyze-video", json=payload)
        assert response.status_code == 200
        assert response.json()["analysis"]["summary"] == "A video of a cat"


@pytest.mark.asyncio
async def test_transcribe_audio(client, mock_inference_service):
    with patch("os.path.exists", return_value=True):
        mock_inference_service.transcribe_audio = AsyncMock(
            return_value={
                "transcript": "Hello world",
                "language": "en",
                "duration": 10.5,
                "language_probability": 0.99,
                "transcription_confidence": 0.95,
            }
        )

        payload = {"audio_path": "/tmp/test.mp3"}
        response = client.post("/transcribe-audio", json=payload)
        assert response.status_code == 200
        assert response.json()["transcript"] == "Hello world"


@pytest.mark.asyncio
async def test_openai_embeddings(client, mock_inference_service):
    mock_inference_service.get_embeddings = AsyncMock(return_value=[[0.1, 0.2]])

    payload = {"input": "This is a test", "model": "text-embedding-3-small"}
    response = client.post("/v1/embeddings", json=payload)
    assert response.status_code == 200
    assert "data" in response.json()
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_openai_chat_completions(client, mock_inference_service):
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert "choices" in response.json()
    assert response.json()["choices"][0]["message"]["content"] == "Mocked AI response"

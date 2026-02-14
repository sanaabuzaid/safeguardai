import logging
import os

from crewai.tools import BaseTool
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger('safety')

SUPPORTED_AUDIO_FORMATS = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm', '.ogg'}

SAFEGUARD_IMAGE_URL_PREFIX = "SAFEGUARD_IMAGE_URL:"


def _init_openai() -> OpenAI:
    try:
        return OpenAI(api_key=settings.OPENAI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialise OpenAI client in tools.py: {e}")
        return None


openai_client = _init_openai()


def transcribe_audio_file(audio_file_path: str) -> str:
    if not openai_client:
        logger.error("transcribe_audio_file: OpenAI client not initialised")
        return ""
    if not os.path.exists(audio_file_path):
        logger.error(f"transcribe_audio_file: File not found | path={audio_file_path}")
        return ""
    _, ext = os.path.splitext(audio_file_path.lower())
    if ext not in SUPPORTED_AUDIO_FORMATS:
        logger.error(f"transcribe_audio_file: Unsupported format | ext={ext}")
        return ""
    try:
        with open(audio_file_path, 'rb') as f:
            transcript = openai_client.audio.transcriptions.create(
                model='whisper-1',
                file=f,
            )
        text = (transcript.text or '').strip()
        logger.info(
            f"transcribe_audio_file: OK | path={audio_file_path} | length={len(text)} chars"
        )
        return text
    except Exception as e:
        logger.error(f"transcribe_audio_file: Failed | path={audio_file_path} | error={e}")
        return ""


class SafetyImageTool(BaseTool):
    name: str = "Generate Safety Image"
    description: str = """Generates a professional safety image (photorealistic).

    Use this tool ONLY when the worker explicitly asks to see something visually.
    Trigger phrases: 'show me', 'picture of', 'photo', 'illustrate',
                     'visual guide', 'draw', 'image of', 'figure of'

    Input  : A clear description of what safety image to generate
    Output : URL of the generated image (include the full URL in your reply)

    Do NOT use this for regular text safety questions."""

    def _run(self, description: str) -> str:
        if not openai_client:
            logger.error("SafetyImageTool: OpenAI client not initialised")
            return (
                "TOOL ERROR: Image generation is unavailable. "
                "Provide the safety information as text instead."
            )
        cfg = settings.SAFEGUARDAI
        model = cfg['DALLE_MODEL']
        size = cfg['DALLE_SIZE']
        quality = cfg['DALLE_QUALITY']

        prompt = (
            f"Professional photograph of {description} for workplace safety training. "
            "Style: real camera photo, documentary or training manual quality. "
            "Natural lighting, real materials and textures, authentic industrial or workplace setting. "
            "Single clear subject in frame. "
            "Do not include: illustrations, cartoons, CGI, 3D renders, diagrams, infographics, or any text or labels in the image."
        )

        try:
            response = openai_client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
            )
            image_url = response.data[0].url
            logger.info(
                f"SafetyImageTool: Image generated | description='{description[:50]}'"
            )
            return (
                f"Safety image generated successfully.\n"
                f"{SAFEGUARD_IMAGE_URL_PREFIX}{image_url}"
            )
        except Exception as e:
            logger.error(f"SafetyImageTool: Image generation failed | error={e}")
            return (
                "TOOL ERROR: Image generation failed. "
                "Provide the safety information as text instead."
            )


safety_image_tool = SafetyImageTool()

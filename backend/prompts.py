from typing import Any


class Prompts:
    DEFAULT_IMAGE_DESCRIBE = (
        "Describe this image in detail, focusing on facts and visible elements."
    )

    IMAGE_ANALYSIS_TEMPLATE = (
        "Analyze the image and produce a concise structured analysis. "
        "Focus on visible facts only. "
        "Determine whether the image is a meme or a portrait, and identify five useful semantic tags. "
        "Return data matching the provided JSON schema only."
    )

    TRANSCRIPT_CLEANUP = (
        "You are an expert transcript editor. Improve readability of the transcript.\n"
        "Rules:\n"
        "1. Remove filler words, stammers, and false starts when they do not add meaning.\n"
        "2. Fix punctuation and capitalization.\n"
        "3. Preserve the original meaning, wording style, and important terminology.\n"
        "4. Do not add new information or rephrase for style beyond cleanup.\n"
        "5. Output ONLY the cleaned transcript text.\n\n"
        "Transcript:\n"
        "{text}"
    )

    AUDIO_TRANSLATION = (
        "Translate the following text into natural, fluent {target_language}. "
        "Preserve the original meaning, tone, and special terms. "
        "Output ONLY the translated text.\n\n"
        "Text to translate:\n"
        "{text}"
    )

    # Stage 1: Intent extraction (structured JSON output).
    SESSION_INTENT_PROMPT = (
        "Extract structured intent from the user's latest message.\n\n"
        "Rules:\n"
        "- Analyze only the current user message unless explicit resolved context is provided separately.\n"
        "- Extract person_name whenever any person or chat is explicitly mentioned.\n"
        "- Normalize person_name to nominative case with leading capital letter when possible.\n"
        "- Determine query_type from these values only:\n"
        "  person_chat, search_from_person, last_any, search_text, search_media, summarize_unread.\n"
        "- For topical searches, set search_query to concise topical keywords that describe the target content.\n"
        "- Do not include meta-question phrasing in search_query.\n"
        "- For time phrases, extract time_amount and time_unit.\n"
        "- If the user specifies an exact count, set limit accordingly; otherwise use the default.\n"
        "- If no person or chat is mentioned, set person_name to null.\n\n"
        "Return data matching the provided JSON schema only."
    )

    # Slim intent classifier — used when entities and time are pre-resolved.
    INTENT_SLIM = (
        "Classify the user's chat-history request using the pre-resolved entities and time information.\n\n"
        "Rules:\n"
        "- Do not extract or modify person names.\n"
        "- Set query_type using only the allowed enum values.\n"
        "- Set search_query to concise topical keywords only.\n"
        "- Never include person names in search_query.\n"
        "- Do not include meta-question wording.\n\n"
        "Return data matching the provided JSON schema only."
    )

    # Stage 3: Answer synthesis (compile tool result into user-facing reply).
    SESSION_SYNTHESIS_PROMPT = (
        "You are an assistant helping the user analyze retrieved chat history. {session_context}\n\n"
        "Important identity rules:\n"
        "- You are NOT the user.\n"
        "- Messages marked as [Me] were written by the user.\n"
        "- Messages marked with another person's name were written by that person.\n"
        "- Never speak as if you are the user or the contact.\n"
        "- Do not merge the user's viewpoint with the contact's viewpoint.\n\n"
        "The user asked a question. You have fetched chat data. "
        "Compile a helpful, concise answer grounded only in the retrieved messages.\n\n"
        "When replying about a message with media:\n"
        "- If the tool result includes media type, download URL, or description, include them clearly.\n"
        "- For non-text messages, mention the download URL and the description.\n\n"
        "When answering questions like 'What did [person] ask/assign/send me?':\n"
        "- List ONLY messages FROM that person.\n"
        "- Quote the original message text with date/time.\n"
        "- If you found only the user's replies, say: 'I found your replies but not the original question.'\n"
        "- Do NOT summarize the user's long replies as if they were the other person's request.\n"
    )

    # Image Analysis - Stage 1: Classification
    STAGE_1_CLASSIFY = (
        "Analyze this image. Classify it by responding with EXACTLY ONE of the following words: "
        "Selfie, Meme, Generic, or Document. Do not add any punctuation or extra text."
    )

    # Image Analysis - Stage 2: Description
    STAGE_2_DESCRIBE = (
        "Provide a detailed, factual description of the main subjects, actions, and environment in this image. "
        "Focus purely on visual details without making assumptions."
    )

    # Image Analysis - Stage 3: OCR
    STAGE_3_OCR = (
        "Extract all visible text from this image as faithfully as possible. "
        "Preserve line breaks when they are visually clear. "
        "Return ONLY the extracted text. "
        "If no readable text is visible, return exactly: [NO_TEXT]"
    )

    # Image Analysis - Stage 4: Synthesis
    STAGE_4_SYNTHESIS = (
        "You are synthesizing multimodal image analysis results.\n\n"
        "Inputs:\n"
        "- image type classification\n"
        "- OCR text\n"
        "- factual visual description\n\n"
        "Tasks:\n"
        "1. Detect the primary language of the visible text or, if no text is present, the most likely language context.\n"
        "2. Identify concise analysis flags such as UI, document-like content, branding, or sensitive content when clearly visible.\n"
        "3. Produce exactly five semantic tags representing the core content.\n"
        "4. Keep all fields concise, factual, and grounded in the provided inputs.\n\n"
        "Return data matching the provided JSON schema only."
    )

    # Video Analysis
    VIDEO_FRAME_DESCRIBE = (
        "Describe the activity, subjects, and setting in this video frame accurately. "
        "Focus on what's visible and any significant changes from typical scenes. "
        "Keep it concise but informative."
    )

    # Video Temporal Fusion - Step 1: Align visual and audio into a unified chronology
    VIDEO_FUSION_STEP_1_TIMELINE = (
        "You are an expert video analyst. Align the ordered visual logs with the audio transcript "
        "into a single chronological timeline.\n\n"
        "Visual Logs:\n{visual_logs}\n\n"
        "Audio Transcript:\n{transcript}\n\n"
        "Create a bulleted list of events in chronological order. "
        "For each event, combine visual evidence with matching audio topics or quotes when clearly aligned. "
        "Include approximate timestamps. "
        "Do not invent events that are unsupported by either the visual logs or the transcript."
    )

    # Video Temporal Fusion - Step 2: Extract summaries and segments from the chronology
    VIDEO_FUSION_STEP_2_SUMMARY = (
        "Analyze the integrated video chronology and synthesize a final structured result.\n\n"
        "Requirements:\n"
        "1. Write a concise overview of the full video.\n"
        "2. Produce a readable transcript-style narrative based strictly on the chronology.\n"
        "3. Split the video into logical chronological segments with valid start and end times.\n"
        "4. Extract key metadata such as people, topics, places, or notable entities when clearly supported.\n"
        "5. Stay grounded in the chronology only; do not invent unseen content.\n\n"
        "Return data matching the provided JSON schema only."
    )

    @staticmethod
    def build_chat_prompt(messages: list[Any], system_prompt_override: str = "") -> str:
        """
        Formats a list of messages into a single prompt string using ChatML format.
        Assumes messages have 'role' and 'content' attributes.
        No trailing newline after the final assistant turn to avoid tokenization issues
        with leading whitespace in some models.
        """
        prompt = ""
        has_system = False

        for msg in messages:
            role = getattr(msg, "role", "").lower()
            if not role and isinstance(msg, dict):
                role = msg.get("role", "").lower()
            
            content = getattr(msg, "content", "")
            if not content and isinstance(msg, dict):
                content = msg.get("content", "")

            match role:
                case "system":
                    has_system = True
                    content = (
                        system_prompt_override
                        if system_prompt_override
                        else content
                    )
                    prompt += f"<|im_start|>system\n{content}<|im_end|>\n"
                case "user":
                    prompt += f"<|im_start|>user\n{content}<|im_end|>\n"
                case "assistant":
                    prompt += f"<|im_start|>assistant\n{content}<|im_end|>\n"
                case "tool_result":
                    # Tool results are usually injected as a system message in pure ChatML
                    prompt += f"<|im_start|>system\n<tool_result>\n{content}\n</tool_result><|im_end|>\n"
                case _:
                    prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"

        if not has_system and system_prompt_override:
            prompt = (
                f"<|im_start|>system\n{system_prompt_override}<|im_end|>\n" + prompt
            )

        prompt += "<|im_start|>assistant\n"
        return prompt

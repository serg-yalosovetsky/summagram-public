from typing import Any


class Prompts:
    DEBT_EXTRACTION_TEMPLATE = (
        "Extract debt information from the following text and output valid JSON. "
        "Include a concise 'description' summarizing the debt and the exact 'context' quote from the text:\n{text}"
    )

    INTERVIEW_EXTRACTION_TEMPLATE = (
        "Extract interview details from the following text and output valid JSON. "
        "Include a concise 'description' with the context and the exact 'context' quote from the text:\n{text}"
    )

    TOPUP_EXTRACTION_TEMPLATE = (
        "Extract service top-up reminders from the following text and output valid JSON. "
        "Include a concise 'description' of the requirement and the exact 'context' quote from the text:\n{text}"
    )

    CHAT_ANALYSIS_TEMPLATE = (
        "Analyze the following chat metadata and messages to generate a description and tags.\n"
        "Title: {title}\n"
        "Image Description: {image_description}\n"
        "Messages (First 50, Last 50, My Messages):\n{messages}\n\n"
        "Provide a JSON object with:\n"
        "- description: A summary of what this chat is about.\n"
        "- tags: A list of 5-10 tags categorization this chat (topics, tone, importance).\n"
        "Return ONLY the JSON object."
    )

    CONTACT_ANALYSIS_TEMPLATE = (
        "Analyze the following contact information to generate a profile.\n"
        "Name: {name}\n"
        "My Messages to them:\n{my_messages}\n"
        "Shared Chats: {shared_chats}\n"
        "Image Description: {image_description}\n\n"
        "Provide a JSON object with:\n"
        "- description: A summary of who this contact is and their relationship to me.\n"
        "- interests: A list of their apparent interests.\n"
        "- tags: A list of tags to categorize them (relationship, profession, etc).\n"
        "- address: Inferred address or location if mentioned (optional, null if unknown).\n"
        "Return ONLY the JSON object."
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
            role = msg.role.lower()
            match role:
                case "system":
                    has_system = True
                    content = (
                        system_prompt_override
                        if system_prompt_override
                        else msg.content
                    )
                    prompt += f"<|im_start|>system\n{content}<|im_end|>\n"
                case "user":
                    prompt += f"<|im_start|>user\n{msg.content}<|im_end|>\n"
                case "assistant":
                    prompt += f"<|im_start|>assistant\n{msg.content}<|im_end|>\n"
                case "tool_result":
                    prompt += f"<|im_start|>system\n<tool_result>\n{msg.content}\n</tool_result><|im_end|>\n"
                case _:
                    prompt += f"<|im_start|>{role}\n{msg.content}<|im_end|>\n"

        if not has_system and system_prompt_override:
            prompt = (
                f"<|im_start|>system\n{system_prompt_override}<|im_end|>\n" + prompt
            )

        prompt += "<|im_start|>assistant\n"
        return prompt

    @staticmethod
    def get_debt_extraction_prompt(text: str) -> str:
        return Prompts.DEBT_EXTRACTION_TEMPLATE.format(text=text)

    @staticmethod
    def get_interview_extraction_prompt(text: str) -> str:
        return Prompts.INTERVIEW_EXTRACTION_TEMPLATE.format(text=text)

    @staticmethod
    def get_topup_extraction_prompt(text: str) -> str:
        return Prompts.TOPUP_EXTRACTION_TEMPLATE.format(text=text)

    @staticmethod
    def get_chat_analysis_prompt(
        title: str, image_description: str, messages: str
    ) -> str:
        return Prompts.CHAT_ANALYSIS_TEMPLATE.format(
            title=title, image_description=image_description, messages=messages
        )

    @staticmethod
    def get_contact_analysis_prompt(
        name: str, my_messages: str, shared_chats: str, image_description: str
    ) -> str:
        return Prompts.CONTACT_ANALYSIS_TEMPLATE.format(
            name=name,
            my_messages=my_messages,
            shared_chats=shared_chats,
            image_description=image_description,
        )

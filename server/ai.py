import logging
import asyncio
from typing import Optional, List, Dict, Any

from google import genai
from google.genai import types as genai_types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    settings,
    MAX_AI_ITERATIONS,
    AI_THINKING_BUDGET,
)
from server.database import (
    get_profile,
    save_chat_message,
    get_latest_summary,
    get_unsummarized_messages,
    get_emotional_memories,
)
from server.models import UserProfile, ChatHistory
from server.relationship_logic import check_for_level_up
from server.ai_tools import ToolService, ALL_TOOLS_DECLARATIONS
from server.prompt_service import PromptService
from utils.circuit_breaker import gemini_circuit_breaker

logger = logging.getLogger(__name__)

class AIResponseGenerator:
    def __init__(self, user_id: int, gemini_client: genai.Client):
        self.user_id = user_id
        self.client = gemini_client
        self.tool_service = ToolService(user_id, gemini_client)
        self.prompt_service = None # Will be initialized after loading user profile
        self.user_profile = None

    async def _load_context(self):
        """Loads user profile and initializes prompt service."""
        self.user_profile = await get_profile(self.user_id)
        if not self.user_profile:
            # Should not happen if auth middleware works, but safety first
            raise ValueError(f"User profile not found for {self.user_id}")
        self.prompt_service = PromptService(self.user_profile)

    async def generate_response(self, user_message: str, image_data: Optional[dict] = None) -> Dict[str, Any]:
        """
        Main entry point for generating AI response.
        Orchestrates the conversation flow, tool execution, and memory management.
        Returns:
            Dict with 'text' and 'image_base64' keys.
        """
        if not self.client:
            return {"text": "Извини, я сейчас не могу отвечать (AI client not initialized).", "image_base64": None}

        await self._load_context()

        # 1. Load Context (History, Memories, Summary)
        chat_history_objs = await get_unsummarized_messages(self.user_id)
        chat_summary = await get_latest_summary(self.user_id)
        emotional_memories = await get_emotional_memories(self.user_id, limit=5)

        # 2. Prepare System Instruction & History
        system_instruction = self.prompt_service.get_system_instruction(emotional_memories, chat_summary)
        formatted_history = self.prompt_service.prepare_chat_history(chat_history_objs)
        
        # 3. Prepare User Message
        user_content_parts = self.prompt_service.format_user_message(user_message, image_data)

        # 4. Iterative Generation Loop (Thinking & Tools)
        final_response_text = ""
        final_image_b64 = None
        
        # Config for generation
        config = genai_types.GenerateContentConfig(
            tools=[genai_types.Tool(function_declarations=ALL_TOOLS_DECLARATIONS)],
            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True), # We handle it manually for control
            system_instruction=system_instruction,
            thinking_config=genai_types.ThinkingConfig(include_thoughts=True, budget_token_count=AI_THINKING_BUDGET) if AI_THINKING_BUDGET > 0 else None
        )

        current_history = formatted_history
        current_message_parts = user_content_parts
        
        for iteration in range(MAX_AI_ITERATIONS):
            try:
                response = await self._call_gemini_api_with_retry(
                    model=settings.gemini_model_name,
                    contents=current_history + [genai_types.Content(role="user", parts=current_message_parts)],
                    config=config
                )
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                return {"text": "Что-то пошло не так с моей связью с космосом... Попробуй позже.", "image_base64": None}

            if not response.candidates:
                 return {"text": "...", "image_base64": None}

            candidate = response.candidates[0]
            
            # Handle Text Response
            if candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text:
                         final_response_text += part.text

            # Handle Function Calls
            function_calls = [part.function_call for part in candidate.content.parts if part.function_call]
            
            if not function_calls:
                break # No more tools to call, we are done

            # Execute Tools
            tool_outputs = []
            for function_call in function_calls:
                result, image_b64 = await self.tool_service.execute_tool(function_call)
                
                if image_b64:
                    final_image_b64 = image_b64
                    final_response_text += f"\n[Изображение отправлено]"
                
                tool_outputs.append(
                    genai_types.Part.from_function_response(
                        name=function_call.name,
                        response={"result": result}
                    )
                )

            # Update history for next iteration
            # Add model's function call
            current_history.append(genai_types.Content(role="user", parts=current_message_parts)) # Add previous user msg to history
            current_history.append(candidate.content) # Add model response (with function call)
            
            # Prepare next user message (which is actually tool output)
            current_message_parts = tool_outputs

        # 5. Post-processing (Background tasks)
        asyncio.create_task(self._background_tasks(final_response_text))

        return {"text": final_response_text, "image_base64": final_image_b64}

    async def _background_tasks(self, response_text: str):
        """Runs background tasks after response generation."""
        try:
            # 1. Save Model Response
            await save_chat_message(self.user_id, 'model', response_text)

            # 2. Check for Level Up
            new_level = await check_for_level_up(self.user_id)
            if new_level:
                logger.info(f"User {self.user_id} leveled up to {new_level}!")
            
            # 3. Summarization (if needed)
            # Logic for summarization remains similar, can be extracted too if needed
            pass 
        except Exception as e:
            logger.error(f"Background task error: {e}")

    @gemini_circuit_breaker.call
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def _call_gemini_api_with_retry(self, model, contents, config):
        return await self.client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )

async def generate_ai_response(
    user_id: int, 
    message: str, 
    image_data: Optional[dict] = None,
    gemini_client: genai.Client = None
) -> Dict[str, Any]:
    """
    Wrapper function to be called from routes.
    """
    generator = AIResponseGenerator(user_id, gemini_client)
    return await generator.generate_response(message, image_data)

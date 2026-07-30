from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from azure.identity import AzureCliCredential, get_bearer_token_provider
import os

load_dotenv()

MODELS = {
    "gpt-5.1": os.getenv("MODEL_GPT", "gpt-5.1"),
    "mistral": os.getenv("MODEL_MISTRAL", "Mistral-Large-3"),
    "deepseek": os.getenv("MODEL_DEEPSEEK", "DeepSeek-V4-Flash"),
}

# Azure RBAC token provider — uses az login credentials
_token_provider = get_bearer_token_provider(
    AzureCliCredential(), "https://ai.azure.com/.default"
)


def get_llm(model_name: str = "gpt-5.1"):
    return ChatOpenAI(
        base_url=os.getenv("AZURE_OPENAI_ENDPOINT", "https://ankishar-4407-resource.services.ai.azure.com/openai/v1"),
        api_key=_token_provider,
        model=MODELS[model_name],
        temperature=0,
    )
"""Amazon Bedrock service - LLM invocation and Knowledge Base retrieval."""

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class BedrockService:
    """Wrapper for Amazon Bedrock runtime and Knowledge Base operations."""

    def __init__(self) -> None:
        self._runtime = boto3.client(
            "bedrock-runtime", region_name=settings.AWS_REGION
        )
        self._agent_runtime = boto3.client(
            "bedrock-agent-runtime", region_name=settings.AWS_REGION
        )

    def invoke_model(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        """Invoke the configured Bedrock model and return the text response.

        Uses the Anthropic Claude messages API body format to call the model
        specified in ``settings.BEDROCK_MODEL_ID``.

        Parameters
        ----------
        prompt      : Full prompt string sent to the model.
        max_tokens  : Maximum tokens in the response.
        temperature : Sampling temperature (0.0 = deterministic).

        Returns
        -------
        str
            The model's text output.

        Raises
        ------
        RuntimeError
            Wrapping the original ``ClientError`` with context.
        """
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
        )
        try:
            response = self._runtime.invoke_model(
                modelId=settings.BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            result = json.loads(response["body"].read())
            return result["content"][0]["text"]
        except ClientError as exc:
            logger.error(
                "BedrockService.invoke_model failed: %s",
                exc.response["Error"]["Code"],
                exc_info=True,
            )
            raise RuntimeError(
                f"Bedrock invoke_model failed: {exc.response['Error']['Message']}"
            ) from exc

    def _generation_model_arn(self) -> str:
        """Build the model ARN used by Knowledge Base RetrieveAndGenerate.

        In ap-southeast-2 most current models (including Amazon Nova) are only
        available through a cross-region inference profile, not an on-demand
        ``foundation-model`` ARN. If ``BEDROCK_MODEL_ID`` already carries a
        region prefix (e.g. ``apac.``/``au.``/``global.``) it is treated as an
        inference profile ID; otherwise the ``apac.`` prefix is applied. The
        account ID is resolved at runtime via STS.
        """
        model_id = settings.BEDROCK_MODEL_ID
        region = settings.AWS_REGION
        account = boto3.client(
            "sts", region_name=region
        ).get_caller_identity()["Account"]

        prefixes = ("apac.", "au.", "us.", "eu.", "global.")
        if model_id.startswith(prefixes):
            profile_id = model_id
        else:
            profile_id = f"apac.{model_id}"

        return (
            f"arn:aws:bedrock:{region}:{account}"
            f":inference-profile/{profile_id}"
        )

    def retrieve_and_generate(
        self,
        question: str,
        knowledge_base_id: str,
        category_filter: str | None = None,
    ) -> dict[str, Any]:
        """Query Bedrock Knowledge Base with retrieve-and-generate.

        Calls the ``RetrieveAndGenerate`` API and normalizes the response into
        a dict with ``answer`` (str) and ``citations`` (list of dicts with
        ``documentName``, ``documentId``, ``snippet``, ``relevanceScore``).

        Parameters
        ----------
        question          : Natural-language question.
        knowledge_base_id : The Bedrock Knowledge Base ID.
        category_filter   : Optional metadata filter on document category.

        Returns
        -------
        dict[str, Any]
            Keys: ``answer`` (str), ``citations`` (list[dict]).

        Raises
        ------
        RuntimeError
            Wrapping the original ``ClientError`` with context.
        """
        kwargs: dict[str, Any] = {
            "input": {"text": question},
            "retrieveAndGenerateConfiguration": {
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": knowledge_base_id,
                    "modelArn": self._generation_model_arn(),
                },
            },
        }

        if category_filter:
            kb_config = kwargs["retrieveAndGenerateConfiguration"][
                "knowledgeBaseConfiguration"
            ]
            kb_config["retrievalConfiguration"] = {
                "vectorSearchConfiguration": {
                    "filter": {
                        "equals": {"key": "category", "value": category_filter}
                    }
                }
            }

        try:
            response = self._agent_runtime.retrieve_and_generate(**kwargs)
            output = response.get("output", {}).get("text", "")
            citations_raw = response.get("citations", [])
            citations = [
                {
                    "documentName": ref.get("location", {})
                    .get("s3Location", {})
                    .get("uri", "")
                    .split("/")[-1],
                    "documentId": ref.get("metadata", {}).get(
                        "x-amz-bedrock-kb-source-uri", ""
                    ),
                    "snippet": ref.get("content", {}).get("text", ""),
                    "relevanceScore": ref.get("score", 0.0),
                }
                for citation in citations_raw
                for ref in citation.get("retrievedReferences", [])
            ]
            return {"answer": output, "citations": citations}
        except ClientError as exc:
            logger.error(
                "BedrockService.retrieve_and_generate failed: %s",
                exc.response["Error"]["Code"],
                exc_info=True,
            )
            raise RuntimeError(
                f"Bedrock retrieve_and_generate failed: "
                f"{exc.response['Error']['Message']}"
            ) from exc

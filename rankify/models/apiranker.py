from typing import List
from rankify.models.base import BaseRanking
from rankify.dataset.dataset import Document, Context
from rankify.utils.pre_defind_models import (
    URL,
    API_DOCUMENT_KEY_MAPPING,
    API_RETURN_DOCUMENTS_KEY_MAPPING,
    API_RESULTS_KEY_MAPPING,
    API_SCORE_KEY_MAPPING
)
import requests
import json
import copy
from tqdm import tqdm  # Import tqdm for progress tracking

class APIRanker(BaseRanking):
    """
    A ranking model that leverages external API-based ranking services.

    Attributes
    ----------
    model_name : str
        The model used for ranking by the API provider.
    api_key : str
        The API key to access the ranking service.
    api_provider : str
        The name of the API provider (e.g., 'cohere', 'jina', 'voyage').
    url : str
        The API endpoint URL.
    headers : dict
        The headers required for making API requests.
    """

    def __init__(self, method: str, model_name: str, api_key: str, **kwargs):
        """
        Initializes an APIRanker instance.

        Parameters
        ----------
        method : str
            The ranking method.
        model_name : str
            The model name for the API provider.
        api_key : str
            The API key for the service.

        Raises
        ------
        ValueError
            If the specified API provider is not supported.

        Examples
        --------
        Using `Reranking` class to call APIRanker:
        
        >>> from rankify.models.reranking import Reranking
        >>> question = Question("Who discovered gravity?")
        >>> contexts = [
        ...     Context(text="Gravity was discovered by Newton", id=1),
        ...     Context(text="Newton was a physicist", id=2)
        ... ]
        >>> document = Document(question=question, contexts=contexts)
        >>> model = Reranking(method='apiranker', model_name='cohere', api_key='your-api-key')
        >>> ranked_docs = model.rank([document])
        """
        self.model_name = URL[model_name]['model_name']
        self.api_key = api_key
        self.api_provider = model_name.lower()
        self.url = URL[model_name]['url']
        
        if not self.url:
            raise ValueError(f"Unsupported API provider: {self.api_provider}")

        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def rank(self, documents: List[Document]) -> List[Document]:
        """
        Reranks the contexts within each document based on their relevance to the document's query.

        Parameters
        ----------
        documents : list of Document
            The documents whose contexts need to be ranked.

        Returns
        -------
        list of Document
            The documents with reordered contexts.

        Examples
        --------
        Using different API models:
        
        >>> from rankify.models.reranking import Reranking
        >>> question = Question("When was the light bulb invented?")
        >>> contexts = [
        ...     Context(text="Thomas Edison invented the light bulb in 1879", id=1),
        ...     Context(text="Electricity was discovered earlier", id=2)
        ... ]
        >>> document = Document(question=question, contexts=contexts)
        >>> model = Reranking(method='apiranker', model_name='voyage', api_key='your-api-key')
        >>> ranked_docs = model.rank([document])
        
        >>> model = Reranking(method='apiranker', model_name='jina', api_key='your-api-key')
        >>> ranked_docs = model.rank([document])
        
        >>> model = Reranking(method='apiranker', model_name='mixedbread.ai', api_key='your-api-key')
        >>> ranked_docs = model.rank([document])
        """
        for doc in tqdm(documents, desc="Reranking Documents"):
            query = doc.question.question
            payload = self._format_payload(query, doc.contexts)
            response = requests.post(self.url, headers=self.headers, data=payload)
            response_data = response.json()
            self._parse_response(response_data, doc)
        
        return documents

    def _format_payload(self, query: str, contexts: List[Context]) -> str:
        """
        Prepares the payload for the API request for a single document.

        Parameters
        ----------
        query : str
            The query string.
        contexts : list of Context
            The contexts of a single document.

        Returns
        -------
        str
            The JSON payload.
        """
        top_key = "top_n" if self.api_provider not in ["voyage", "mixedbread.ai"] else "top_k"
        documents_key = API_DOCUMENT_KEY_MAPPING.get(self.api_provider, "documents")
        return_documents_key = API_RETURN_DOCUMENTS_KEY_MAPPING.get(self.api_provider, "return_documents")

        payload = {
            "model": self.model_name,
            "query": query,
            documents_key: [context.text for context in contexts],
            top_key: len(contexts),
            return_documents_key: True,
        }
        return json.dumps(payload)

    def _parse_response(self, response: dict, document: Document) -> None:
        """
        Parses the API response and assigns scores to each context in the document.

        Parameters
        ----------
        response : dict
            The API response data.
        document : Document
            The document whose contexts are being ranked.

        Returns
        -------
        None
        """
        results_key = API_RESULTS_KEY_MAPPING.get(self.api_provider, "results")
        score_key = API_SCORE_KEY_MAPPING.get(self.api_provider, "relevance_score")
        
        results = response.get(results_key, response)

        # Create a list to hold the reordered contexts
        reordered_contexts = []

        print(results, self.api_provider)
        # Map each result to a context
        for result in results:
            # Extract text and score
            
            if self.api_provider == "voyage":
                text = result.get("document", {})
            else:
                text = result.get("document", {}).get("text", "")
            
            score = result.get(score_key, 0.0)

            # Find the matching context in the original list
            matching_context = next((context for context in document.contexts if context.text == text), None)
            if matching_context:
                # Update score and add to reordered list
                matching_context.score = score
                reordered_contexts.append(matching_context)

        # Assign reordered contexts directly from the API response order
        document.reorder_contexts = reordered_contexts
